from copy import deepcopy

from fpl_toolkit.league_activity import completed_player_points, evaluate_transfers, freeze_transfer, public_transfer_reviews
from fpl_toolkit.opponent_profile import build_manager_profiles, update_manager_history
from fpl_toolkit.privacy import sanitize_public_report

LEAGUE = {"league_entries": [{"id": 9, "entry_id": 111, "entry_name": "Alpha", "player_first_name": "Secret"}]}
PLAYERS = [
    {"player_id": i, "player": name, "position": "DEF", "intelligence": {"roster_score": score},
     "fixtures": [{"gameweek": gw, "matches": []} for gw in range(5, 9)]}
    for i, name, score in [(1, "Incoming", 70), (2, "Outgoing", 50)]
]
CHANGES = [{"type": "add", "player_id": 1, "player": "Incoming", "to_owner": "9"},
           {"type": "drop", "player_id": 2, "player": "Outgoing", "from_owner": "111"}]


def history(changes=CHANGES):
    return update_manager_history(None, LEAGUE, PLAYERS, changes, captured_at="2026-09-01", gameweek=5)


def test_history_survives_unchanged_collection_and_uses_safe_labels():
    first = history()
    second = update_manager_history(first, LEAGUE, PLAYERS, [], captured_at="2026-09-02", gameweek=5)
    assert second["activity"] == first["activity"]
    assert len(second["managers"]["111"]["transactions"]) == 1
    report = sanitize_public_report({"league_activity": second["activity"], "transfer_reviews": public_transfer_reviews(second)})
    assert report["league_activity"][0]["from_team"] == "Free pool"
    assert report["league_activity"][0]["to_team"] == "Alpha"
    assert "111" not in str(report) and "Secret" not in str(report)


def test_migration_recovers_only_recorded_events_and_is_bounded():
    first = history()
    first.pop("activity")
    migrated = update_manager_history(first, LEAGUE, PLAYERS, [], captured_at="later", gameweek=6)
    assert len(migrated["activity"]) == 2
    assert migrated["activity"][0]["source"] == "retained manager record"
    assert "Unknown" in str(migrated["activity"])
    migrated["activity"] *= 300
    assert len(update_manager_history(migrated, LEAGUE, PLAYERS, [], captured_at="later", gameweek=6)["activity"]) == 500


def test_repeated_collection_is_idempotent_but_a_later_same_move_is_retained():
    first = history()
    repeat = update_manager_history(first, LEAGUE, PLAYERS, CHANGES, captured_at="2026-09-01", gameweek=5)
    assert len(repeat["activity"]) == 2
    assert len(repeat["managers"]["111"]["transactions"]) == 1
    later = update_manager_history(repeat, LEAGUE, PLAYERS, CHANGES, captured_at="2026-09-03", gameweek=5)
    assert len(later["managers"]["111"]["transactions"]) == 2


def completed_manager(started=True, gain=6):
    state = history()
    manager = state["managers"]["111"]
    for gw in range(5, 9):
        manager["lineups"][str(gw)] = {"squad_ids": [1, 3], "starter_ids": [1] if started else [3]}
    points = {gw: {"1": gain + 2, "2": 2} for gw in range(5, 9)}
    return state, manager, points


def test_four_final_rounds_compare_points_and_shrink_rating_with_one_sample():
    state, manager, points = completed_manager()
    evaluate_transfers(manager, {5: points[5]})
    profile = build_manager_profiles(LEAGUE, PLAYERS, None, state)["111"]["management"]
    assert profile["evaluated_transfers"] == 1
    assert profile["effective_transfer_windows"] == .25
    assert profile["transfer_points_adjustment"] == .04
    evaluate_transfers(manager, points)
    outcome = manager["transactions"][0]["outcome"]
    assert outcome["status"] == "complete"
    assert outcome["points_gain"] == 24
    assert outcome["incoming_started_points"] == 32
    profile = build_manager_profiles(LEAGUE, PLAYERS, None, state)["111"]["management"]
    assert profile["evaluated_transfers"] == 1
    assert 0 < profile["transfer_points_adjustment"] <= .16
    assert profile["evidence"] == "LOW"
    before = deepcopy(manager)
    evaluate_transfers(manager, points)
    assert manager == before


def test_acquisition_and_lineup_use_are_separate_and_expected_gain_is_not_rewarded_twice():
    for started in [True, False]:
        state, manager, points = completed_manager(started)
        if started:
            manager["transactions"][0]["expected_gains"] = {str(gw): 6 for gw in range(5, 9)}
        evaluate_transfers(manager, points)
        profile = build_manager_profiles(LEAGUE, PLAYERS, None, state)["111"]["management"]
        assert profile["transfer_points_adjustment"] == (0 if started else .16)
        if not started:
            assert manager["transactions"][0]["outcome"]["incoming_started_points"] == 0


def test_missing_points_unknown_lineups_and_resold_players_do_not_become_failures():
    state, manager, points = completed_manager()
    points[6].pop("2")
    evaluate_transfers(manager, points)
    assert manager["transactions"][0]["outcome"]["status"] == "pending"
    assert manager["transactions"][0]["outcome"]["observed_gameweeks"] == 3
    manager["lineups"]["6"]["squad_ids"] = [3, 4]
    evaluate_transfers(manager, points)
    assert manager["transactions"][0]["outcome"]["status"] == "stopped"
    assert build_manager_profiles(LEAGUE, PLAYERS, None, state)["111"]["management"]["transfer_points_adjustment"] == .04


def test_unbalanced_batch_and_legacy_records_do_not_affect_transfer_rating():
    state = history(CHANGES[:1])
    manager = state["managers"]["111"]
    assert not manager["transactions"][0]["eligible"]
    manager["transactions"].append({"value_delta": 100, "adds": [], "drops": []})
    profile = build_manager_profiles(LEAGUE, PLAYERS, None, state)["111"]["management"]
    assert profile["transfer_points_adjustment"] == 0


def test_negative_results_and_repeated_success_stay_within_transfer_budget():
    for gain in [-50, 50]:
        state, manager, points = completed_manager(gain=gain)
        evaluate_transfers(manager, points)
        manager["transactions"] *= 20
        profile = build_manager_profiles(LEAGUE, PLAYERS, None, state)["111"]["management"]
        assert profile["transfer_points_adjustment"] == (-.8 if gain < 0 else .8)


def test_completed_points_require_explicit_points_and_cross_feed_mapping():
    result = completed_player_points([(5, {"elements": [
        {"id": 11, "stats": {"total_points": 0}},
        {"id": 12, "stats": {}}, {"id": 13, "stats": {"total_points": 10}},
    ]})], {11: 1, 12: 2})
    assert result == {5: {"1": 0.0}}


def test_projection_is_frozen_and_missing_fixture_coverage_is_not_a_blank():
    players = {str(row["player_id"]): row for row in PLAYERS}
    frozen = freeze_transfer(PLAYERS[:1], PLAYERS[1:], players, 5)
    assert set(frozen["expected_gains"]) == {"5", "6", "7", "8"}
    missing = deepcopy(players)
    missing["1"]["fixtures"] = []
    assert freeze_transfer(PLAYERS[:1], PLAYERS[1:], missing, 5)["expected_gains"] == {}


def test_observed_reversal_stops_old_review_even_if_player_is_reacquired_before_deadline():
    state = history()
    reverse = [{"type": "drop", "player_id": 1, "from_owner": "111"},
               {"type": "add", "player_id": 2, "to_owner": "111"}]
    state = update_manager_history(state, LEAGUE, PLAYERS, reverse, captured_at="2026-09-02", gameweek=5)
    state = update_manager_history(state, LEAGUE, PLAYERS, CHANGES, captured_at="2026-09-03", gameweek=5)
    manager = state["managers"]["111"]
    assert manager["transactions"][0]["outcome"]["status"] == "stopped"
    assert manager["transactions"][1]["outcome"]["status"] == "stopped"
    assert manager["transactions"][2]["outcome"]["status"] == "pending"


def test_early_failures_lower_rating_and_short_observations_have_less_weight():
    from fpl_toolkit.opponent_profile import _management_profile
    success = {"evaluation_version": 1, "eligible": True, "outcome": {
        "status": "complete", "observed_gameweeks": 4,
        "excess_points_per_player_week": 3, "points_gain": 12}}
    failure = {"evaluation_version": 1, "eligible": True, "outcome": {
        "status": "stopped", "observed_gameweeks": 1,
        "excess_points_per_player_week": -9, "points_gain": -9}}
    positive = _management_profile({"transactions": [success]})
    mixed = _management_profile({"transactions": [success] + [failure] * 4})
    assert positive["transfer_points_adjustment"] > 0
    assert mixed["transfer_points_adjustment"] < 0
    assert mixed["effective_transfer_windows"] == 2
    assert mixed["evidence"] == "LOW"
