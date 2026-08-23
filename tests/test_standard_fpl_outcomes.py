from fpl_toolkit.standard_fpl_outcomes import (
    build_transfer_outcomes,
    standard_gameweek_phase,
)


def _candidate(*, cost=0):
    return {
        "action": "CONSIDER" if cost == 0 else "HIT REVIEW",
        "confidence": "HIGH",
        "outgoing": {"player_id": 1, "player": "Owned", "position": "MID"},
        "incoming": {"player_id": 2, "player": "Target", "position": "MID"},
        "heuristic": {"score": 12.0, "deltas": {}},
        "transfer_allowance": {"incremental_cost_points": cost},
    }


def _decision(recommendation="CONSIDER", *, cost=0):
    return {
        "is_available": True,
        "recommendation": recommendation,
        "summary": f"{recommendation} summary",
        "candidate": _candidate(cost=cost),
    }


def _fixtures(gameweek, *, started=False, finished=False):
    return [{"event": gameweek, "started": started, "finished": finished}]


def _players(outgoing_points=0, incoming_points=0):
    return [
        {"player_id": 1, "event_points": outgoing_points},
        {"player_id": 2, "event_points": incoming_points},
    ]


def test_standard_gameweek_phase_covers_scheduled_live_and_final():
    assert standard_gameweek_phase(_fixtures(2), 2) == "SCHEDULED"
    assert standard_gameweek_phase(_fixtures(2, started=True), 2) == "LIVE"
    assert standard_gameweek_phase(_fixtures(2, started=True, finished=True), 2) == "FINAL"


def test_first_pre_deadline_transfer_decision_is_frozen():
    first = build_transfer_outcomes(
        None,
        _decision("CONSIDER"),
        _players(),
        _fixtures(2),
        scoring_gameweek=1,
        decision_gameweek=2,
        generated_at="2026-08-23T10:00:00+00:00",
    )
    changed = _decision("HOLD")
    second = build_transfer_outcomes(
        {"transfer_outcomes": first},
        changed,
        _players(),
        _fixtures(2),
        scoring_gameweek=1,
        decision_gameweek=2,
        generated_at="2026-08-24T10:00:00+00:00",
    )

    forecast = second["current"]["forecast"]
    assert forecast["recommendation"] == "CONSIDER"
    assert forecast["captured_at"] == "2026-08-23T10:00:00+00:00"
    assert forecast["calibration_eligible"] is True


def test_final_transfer_outcome_compares_matching_gameweek_points_and_hit():
    first = build_transfer_outcomes(
        None,
        _decision("CONSIDER", cost=4),
        _players(),
        _fixtures(2),
        scoring_gameweek=1,
        decision_gameweek=2,
        generated_at="2026-08-23T10:00:00+00:00",
    )
    final = build_transfer_outcomes(
        {"transfer_outcomes": first},
        _decision("HOLD"),
        _players(outgoing_points=2, incoming_points=9),
        _fixtures(2, started=True, finished=True) + _fixtures(3),
        scoring_gameweek=2,
        decision_gameweek=3,
        generated_at="2026-08-30T10:00:00+00:00",
    )

    result = final["history"][-1]
    assert result["forecast"]["gameweek"] == 2
    assert result["actual"]["recommendation_delta"] == 3.0
    assert result["evaluation"]["complete"] is True
    assert result["evaluation"]["comparison_result"] == "BETTER"


def test_hold_outcome_credits_avoided_hit_without_claiming_team_causality():
    first = build_transfer_outcomes(
        None,
        _decision("HOLD", cost=4),
        _players(),
        _fixtures(2),
        scoring_gameweek=1,
        decision_gameweek=2,
        generated_at="2026-08-23T10:00:00+00:00",
    )
    final = build_transfer_outcomes(
        {"transfer_outcomes": first},
        _decision("HOLD"),
        _players(outgoing_points=5, incoming_points=7),
        _fixtures(2, started=True, finished=True) + _fixtures(3),
        scoring_gameweek=2,
        decision_gameweek=3,
        generated_at="2026-08-30T10:00:00+00:00",
    )

    result = final["history"][-1]
    assert result["actual"]["recommendation_delta"] == 2.0
    assert result["evaluation"]["comparison_result"] == "BETTER"
    assert "does not prove" in result["evaluation"]["note"]


def test_missed_gameweek_snapshot_never_uses_later_event_points():
    first = build_transfer_outcomes(
        None,
        _decision("CONSIDER"),
        _players(),
        _fixtures(2),
        scoring_gameweek=1,
        decision_gameweek=2,
        generated_at="2026-08-23T10:00:00+00:00",
    )
    later = build_transfer_outcomes(
        {"transfer_outcomes": first},
        _decision("HOLD"),
        _players(outgoing_points=1, incoming_points=15),
        _fixtures(2, started=True, finished=True) + _fixtures(4),
        scoring_gameweek=3,
        decision_gameweek=4,
        generated_at="2026-09-06T10:00:00+00:00",
    )

    result = later["history"][-1]
    assert result["actual"] is None
    assert result["evaluation"]["calibration_eligible"] is False
    assert "missed" in result["evaluation"]["reason"]


def test_missing_player_points_fail_closed_instead_of_becoming_zero():
    first = build_transfer_outcomes(
        None,
        _decision("CONSIDER"),
        _players(),
        _fixtures(2),
        scoring_gameweek=1,
        decision_gameweek=2,
        generated_at="2026-08-23T10:00:00+00:00",
    )
    result = build_transfer_outcomes(
        {"transfer_outcomes": first},
        _decision("HOLD"),
        [{"player_id": 1, "event_points": 4}],
        _fixtures(2, started=True, finished=True) + _fixtures(3),
        scoring_gameweek=2,
        decision_gameweek=3,
        generated_at="2026-08-30T10:00:00+00:00",
    )["history"][-1]

    assert result["actual"] is None
    assert result["evaluation"]["complete"] is False
    assert result["evaluation"]["calibration_eligible"] is False
    assert "unavailable" in result["evaluation"]["reason"]
