from fpl_toolkit.standard_fpl_transfers import (
    build_transfer_decision,
    rank_single_transfers,
    unavailable_single_transfer_ranking,
)


POSITIONS = ["GKP", "GKP", "DEF", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "MID", "FWD", "FWD", "FWD"]


def _player(
    player_id,
    position,
    team_id,
    *,
    score=50.0,
    confidence=80.0,
    owned=False,
    selling_price=5.0,
    now_cost=5.0,
):
    return {
        "player_id": player_id,
        "player": f"P{player_id}",
        "club": f"T{team_id}",
        "team_id": team_id,
        "position": position,
        "is_owned": owned,
        "selling_price": selling_price if owned else None,
        "now_cost": now_cost,
        "chance_next_round": 100,
        "fixtures": [
            {
                "gameweek": 2,
                "matches": [{"difficulty": 3}],
            }
        ],
        "intelligence": {
            "roster_score": score,
            "future_fixture_score": score,
            "availability_score": 100.0,
            "expected_minutes": 90.0,
            "floor_score": score,
            "upside_score": score,
            "sample_confidence": confidence,
        },
    }


def _squad():
    squad = [
        _player(
            index,
            position,
            ((index - 1) % 5) + 1,
            score=20.0 if index == 8 else 50.0,
            owned=True,
        )
        for index, position in enumerate(POSITIONS, start=1)
    ]
    return squad


def test_ranks_best_affordable_same_position_move_first():
    squad = _squad()
    strong_midfielder = _player(101, "MID", 6, score=85.0)
    modest_midfielder = _player(102, "MID", 6, score=58.0)

    report = rank_single_transfers(
        squad + [strong_midfielder, modest_midfielder],
        squad,
        2,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=0,
    )

    best = report["candidates"][0]
    assert report["is_available"] is True
    assert best["incoming"]["player_id"] == 101
    assert best["outgoing"]["player_id"] == 8
    assert best["action"] == "CONSIDER"
    assert best["confidence"] == "HIGH"
    assert best["transfer_allowance"]["uses_free_transfer"] is True
    assert best["transfer_allowance"]["incremental_cost_points"] == 0
    assert "projected FPL points" in report["note"]


def test_rejects_unaffordable_and_club_quota_pairs():
    squad = _squad()
    expensive_midfielder = _player(101, "MID", 6, score=90.0, now_cost=8.0)
    fourth_team_one_midfielder = _player(102, "MID", 1, score=80.0)

    report = rank_single_transfers(
        squad + [expensive_midfielder, fourth_team_one_midfielder],
        squad,
        2,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=0,
    )

    assert report["rejected_counts"]["insufficient_funds"] == 5
    assert report["rejected_counts"]["club_quota"] > 0
    assert all(
        candidate["incoming"]["player_id"] != 101
        for candidate in report["candidates"]
    )


def test_point_hit_is_separate_from_unchanged_heuristic_score():
    squad = _squad()
    incoming = _player(101, "MID", 6, score=85.0)
    players = squad + [incoming]

    free_report = rank_single_transfers(
        players,
        squad,
        2,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=0,
    )
    hit_report = rank_single_transfers(
        players,
        squad,
        2,
        bank_tenths=0,
        free_transfers=0,
        transfers_made=0,
    )

    free_candidate = free_report["candidates"][0]
    hit_candidate = hit_report["candidates"][0]
    assert hit_candidate["heuristic"]["score"] == free_candidate["heuristic"]["score"]
    assert hit_candidate["transfer_allowance"]["incremental_cost_points"] == 4
    assert hit_candidate["action"] == "HIT REVIEW"


def test_low_evidence_candidate_cannot_receive_consider_label():
    squad = _squad()
    incoming = _player(101, "MID", 6, score=95.0, confidence=20.0)

    report = rank_single_transfers(
        squad + [incoming],
        squad,
        2,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=0,
    )

    assert report["candidates"][0]["confidence"] == "LOW"
    assert report["candidates"][0]["action"] == "LOW PRIORITY"


def test_unavailable_state_requires_exact_private_team_state():
    report = unavailable_single_transfer_ranking()

    assert report["is_available"] is False
    assert report["candidates"] == []
    assert "selling prices" in report["reason"]


def test_clear_no_hit_upgrade_becomes_explained_consider_decision():
    squad = _squad()
    incoming = _player(101, "MID", 6, score=85.0)
    ranking = rank_single_transfers(
        squad + [incoming],
        squad,
        2,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=0,
    )

    decision = build_transfer_decision(ranking, free_transfers=1, transfers_made=0)

    assert decision["recommendation"] == "CONSIDER"
    assert decision["candidate"]["incoming"]["player_id"] == 101
    assert {row["code"] for row in decision["reasons"]} >= {
        "clear_heuristic_upgrade",
        "sufficient_evidence",
        "no_incremental_hit",
    }
    assert decision["advisory_only"] is True


def test_small_upgrade_becomes_hold_and_explains_banking():
    squad = _squad()
    incoming = _player(101, "MID", 6, score=23.0)
    ranking = rank_single_transfers(
        squad + [incoming],
        squad,
        2,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=0,
    )

    decision = build_transfer_decision(ranking, free_transfers=1, transfers_made=0)
    reason_codes = {row["code"] for row in decision["reasons"]}

    assert decision["recommendation"] == "HOLD"
    assert "below_upgrade_threshold" in reason_codes
    assert "bank_transfer" in reason_codes
    assert decision["banking"]["can_bank_if_unused"] is True


def test_hit_candidate_defaults_to_hold_without_treating_heuristic_as_points():
    squad = _squad()
    incoming = _player(101, "MID", 6, score=95.0)
    ranking = rank_single_transfers(
        squad + [incoming],
        squad,
        2,
        bank_tenths=0,
        free_transfers=0,
        transfers_made=0,
    )

    decision = build_transfer_decision(ranking, free_transfers=0, transfers_made=0)

    assert decision["recommendation"] == "HOLD"
    assert decision["candidate"]["action"] == "HIT REVIEW"
    assert "point_hit_review" in {row["code"] for row in decision["reasons"]}
    assert "not a points forecast" in decision["reasons"][0]["message"]


def test_hold_decision_surfaces_selling_value_risk():
    squad = _squad()
    squad[7]["now_cost"] = 5.5
    squad[7]["selling_price"] = 5.0
    incoming = _player(101, "MID", 6, score=21.0)
    ranking = rank_single_transfers(
        squad + [incoming],
        squad,
        2,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=0,
    )

    decision = build_transfer_decision(ranking, free_transfers=1, transfers_made=0)

    assert "selling_value_at_risk" in {row["code"] for row in decision["reasons"]}


def test_unavailable_ranking_produces_unavailable_decision():
    decision = build_transfer_decision(
        unavailable_single_transfer_ranking(),
        free_transfers=0,
        transfers_made=0,
    )

    assert decision["is_available"] is False
    assert decision["recommendation"] == "UNAVAILABLE"
    assert decision["candidate"] is None
