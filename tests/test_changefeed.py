from fpl_toolkit.changefeed import build_change_feed, capture_decision_state


def _player(player_id=1, name="Player", position="MID", *, role="MEDIUM", availability=100, minutes=70, recommendation="HOLD", waiver=None, fixture_phase="scheduled"):
    phase = {
        "scheduled": {"started": False, "finished": False},
        "active": {"started": True, "finished": False},
        "finished": {"started": True, "finished": True},
    }[fixture_phase]
    row = {
        "player_id": player_id,
        "player": name,
        "club": "AAA",
        "team_code": 1,
        "position": position,
        "status": "a",
        "chance_next_round": availability,
        "news": "",
        "fixtures": [{"gameweek": 1, "matches": [phase]}],
        "intelligence": {
            "availability_score": availability,
            "expected_minutes": minutes,
            "role_evidence": role,
            "health_trend": "stable",
            "recommendation": recommendation,
            "roster_score": 70,
            "stash_score": 68,
        },
    }
    if waiver:
        row["replacement"] = waiver
    return row


def _report(my_player=None, available=None, lineup_role="START", toughest=3, h2h="EVEN"):
    my_player = my_player or _player()
    available = available or []
    lineup = {
        "formation": "4-4-2",
        "starters": [my_player] if lineup_role == "START" else [],
        "bench": [my_player] if lineup_role == "BENCH" else [],
        "reserve_goalkeeper": None,
    }
    return {
        "generated_at": "2026-08-21T12:00:00+00:00",
        "current_gameweek": 1,
        "decision_gameweek": 1,
        "my_squad": [my_player],
        "available_players": available,
        "recommended_lineup": lineup,
        "schedule_planner": {"weakest_gameweek": toughest},
        "h2h_matchup": {"available": True, "matchup": {"signal": h2h, "start_score_edge": 0.0}},
    }


def test_decision_state_tracks_actionable_and_scoring_gameweeks_separately():
    report = _report()
    report["decision_gameweek"] = 2
    report["gameweek_phase"] = "LIVE"

    state = capture_decision_state(report)

    assert state["gameweek"] == 2
    assert state["scoring_gameweek"] == 1
    assert state["scoring_phase"] == "LIVE"


def test_change_feed_surfaces_material_role_availability_and_lineup_changes():
    before = _report(_player(role="MEDIUM", availability=100, minutes=70), lineup_role="BENCH")
    previous = capture_decision_state(before)
    current = _report(_player(role="HIGH", availability=75, minutes=82), lineup_role="START")

    feed = build_change_feed(previous, current)
    kinds = {item["kind"] for item in feed["items"]}

    assert feed["baseline"] is False
    assert "lineup_change" in kinds
    assert "availability" in kinds
    assert "role_change" in kinds
    assert 1 in feed["changed_player_ids"]


def test_change_feed_persists_new_transfer_evidence():
    previous = capture_decision_state(_report())
    moved = _player()
    moved["transfer_intel"] = {
        "record_id": "player-exit",
        "status": "deal_agreed",
        "action": "EXIT AGREED",
        "destination": {"club": "Al-Hilal"},
        "summary": "A reliable source reports an agreed exit.",
        "blocks_acquisition": True,
    }
    current = _report(moved)

    feed = build_change_feed(previous, current)
    transfer = next(item for item in feed["items"] if item["kind"] == "transfer_update")

    assert transfer["priority"] == "critical"
    assert transfer["badge"] == "TRANSFER"
    assert "Al-Hilal" in transfer["detail"]


def test_change_feed_surfaces_waiver_upgrade_and_opponent_drop_without_manager_identity():
    old_free = _player(
        2,
        "Free Agent",
        "FWD",
        waiver={"action": "KEEP ROSTER", "drop_player": "Owned Fwd", "combined_delta": 1.0},
    )
    new_free = _player(
        2,
        "Free Agent",
        "FWD",
        waiver={"action": "SWAP NOW", "drop_player": "Owned Fwd", "combined_delta": 12.4},
    )
    previous = capture_decision_state(_report(available=[old_free]))
    current = _report(available=[new_free])
    activity = [{
        "type": "drop",
        "player_id": 2,
        "player": "Free Agent",
        "club": "AAA",
        "from_owner": "secret-id",
        "from_owner_name": "Secret Manager",
        "to_owner": None,
    }]

    feed = build_change_feed(previous, current, activity)
    kinds = {item["kind"] for item in feed["items"]}
    text = str(feed)

    assert "waiver_change" in kinds
    assert "opponent_drop" in kinds
    assert "Secret Manager" not in text
    assert "secret-id" not in text


def test_change_feed_suppresses_small_score_noise_and_tracks_planner_or_h2h_shift():
    previous = capture_decision_state(_report(toughest=2, h2h="EDGE"))
    current = _report(toughest=3, h2h="TRAIL")
    current["h2h_matchup"]["matchup"]["start_score_edge"] = -4.2

    feed = build_change_feed(previous, current)
    kinds = [item["kind"] for item in feed["items"]]

    assert kinds.count("planning_change") == 1
    assert kinds.count("h2h_change") == 1
    assert not any(kind in {"minutes_change", "availability", "role_change"} for kind in kinds)


def test_change_feed_refreshes_an_older_decision_state_schema_without_noise():
    previous = capture_decision_state(_report())
    previous.pop("schema_version")

    feed = build_change_feed(previous, _report(_player(minutes=45, fixture_phase="active")))

    assert feed["baseline"] is True
    assert feed["items"] == []
    assert "refreshed" in feed["note"]


def test_change_feed_suppresses_live_match_model_churn_but_keeps_availability_changes():
    old_player = _player(
        minutes=60,
        waiver={"action": "CONSIDER", "drop_player": "Owned Def", "combined_delta": 5.0},
    )
    new_player = _player(
        role="HIGH",
        availability=50,
        minutes=45,
        waiver={"action": "KEEP ROSTER", "drop_player": "Owned Def", "combined_delta": -2.0},
        fixture_phase="active",
    )
    previous = capture_decision_state(_report(old_player, lineup_role="BENCH"))
    current = _report(new_player, lineup_role="START")
    current["schedule_planner"]["weakest_gameweek"] = 4
    current["h2h_matchup"]["matchup"]["signal"] = "TRAIL"

    feed = build_change_feed(previous, current)
    kinds = [item["kind"] for item in feed["items"]]

    assert kinds == ["availability"]


def test_change_feed_keeps_opponent_drops_during_a_schema_refresh():
    previous = capture_decision_state(_report())
    previous.pop("schema_version")
    activity = [{"type": "drop", "player_id": 2, "player": "Free Agent", "club": "AAA"}]

    feed = build_change_feed(previous, _report(available=[_player(2, "Free Agent")]), activity)

    assert feed["baseline"] is True
    assert [item["kind"] for item in feed["items"]] == ["opponent_drop"]


def test_change_feed_starts_a_clean_baseline_when_the_gameweek_rolls_over():
    previous_report = _report(_player(minutes=70), toughest=2, h2h="EDGE")
    previous = capture_decision_state(previous_report)
    current = _report(_player(role="HIGH", minutes=40), toughest=4, h2h="TRAIL")
    current["current_gameweek"] = 2
    current["decision_gameweek"] = 2

    feed = build_change_feed(previous, current)

    assert [item["kind"] for item in feed["items"]] == ["gameweek_rollover"]
    assert feed["summary"]["info"] == 1
    assert feed["changed_player_ids"] == []


def test_change_feed_announces_a_final_gameweek_result_once():
    before = _report(_player(fixture_phase="active"))
    before["outcome_diagnostics"] = {"current": {"gameweek": 1, "phase": "LIVE"}}
    previous = capture_decision_state(before)
    current = _report(_player(fixture_phase="finished"))
    current["outcome_diagnostics"] = {"current": {
        "gameweek": 1,
        "phase": "FINAL",
        "forecast": {"recommended": {"projected_total": 50.5}},
        "actual": {
            "official_points": 48,
            "recommended_points": 52,
            "h2h_my_points": 48,
            "h2h_opponent_points": 45,
        },
    }}

    feed = build_change_feed(previous, current)

    result = next(item for item in feed["items"] if item["kind"] == "gameweek_result")
    assert result["title"] == "GW1 result captured"
    assert "48–45" in result["detail"]


def test_change_feed_keeps_material_updates_after_an_unchanged_collection():
    before = _report(_player(availability=100))
    current = _report(_player(availability=50))
    first_feed = build_change_feed(capture_decision_state(before), current)
    current["change_feed"] = first_feed
    persisted_state = capture_decision_state(current)

    stable = _report(_player(availability=50))
    stable["generated_at"] = "2026-08-21T16:00:00+00:00"
    second_feed = build_change_feed(persisted_state, stable)

    assert [item["event_id"] for item in second_feed["items"]] == [
        item["event_id"] for item in first_feed["items"]
    ]
    assert second_feed["new_item_ids"] == []
    assert second_feed["items"][0]["status"] == "active"
    assert second_feed["cycle_started_at"] == first_feed["cycle_started_at"]


def test_change_feed_resolves_an_older_update_when_the_same_signal_changes_again():
    before = _report(_player(availability=100))
    current = _report(_player(availability=50))
    first_feed = build_change_feed(capture_decision_state(before), current)
    current["change_feed"] = first_feed
    persisted_state = capture_decision_state(current)

    improved = _report(_player(availability=100))
    improved["generated_at"] = "2026-08-21T16:00:00+00:00"
    second_feed = build_change_feed(persisted_state, improved)
    availability = [item for item in second_feed["items"] if item["kind"] == "availability"]

    assert len(availability) == 2
    assert {item["status"] for item in availability} == {"active", "resolved"}
    assert next(item for item in availability if item["status"] == "active")["title"].endswith("improved")


def test_change_feed_archives_the_completed_decision_cycle_on_rollover():
    before = _report(_player(availability=100))
    current = _report(_player(availability=50))
    first_feed = build_change_feed(capture_decision_state(before), current)
    current["change_feed"] = first_feed
    persisted_state = capture_decision_state(current)

    next_cycle = _report(_player(availability=50))
    next_cycle["generated_at"] = "2026-08-22T12:00:00+00:00"
    next_cycle["decision_gameweek"] = 2
    rolled = build_change_feed(persisted_state, next_cycle)

    assert rolled["cycle_gameweek"] == 2
    assert rolled["archive"][0]["gameweek"] == 1
    assert rolled["archive"][0]["items"][0]["kind"] == "availability"
    assert [item["kind"] for item in rolled["items"]] == ["gameweek_rollover"]


def test_change_feed_marks_a_claimed_free_agent_as_recent_and_resolves_the_drop():
    free_agent = _player(2, "Free Agent")
    previous = capture_decision_state(_report(available=[free_agent]))
    dropped = build_change_feed(previous, _report(available=[free_agent]), [{
        "type": "drop", "player_id": 2, "player": "Free Agent", "club": "AAA",
    }])
    dropped_report = _report(available=[free_agent])
    dropped_report["change_feed"] = dropped
    dropped_state = capture_decision_state(dropped_report)

    claimed = build_change_feed(dropped_state, _report(), [{
        "type": "add", "player_id": 2, "player": "Free Agent", "club": "AAA",
    }])
    free_pool_events = [item for item in claimed["items"] if item["stream"] == "free_pool:player:2"]

    assert len(free_pool_events) == 2
    assert all(item["status"] == "resolved" for item in free_pool_events)
    assert any(item["kind"] == "opponent_add" for item in free_pool_events)
