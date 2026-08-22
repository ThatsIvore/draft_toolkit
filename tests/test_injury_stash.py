from fpl_toolkit.injury_stash import build_injury_stash_dashboard
from fpl_toolkit.report import build_report


def player(
    player_id,
    name,
    *,
    chance=75,
    stash=65,
    future=70,
    post_return=None,
    expected_return=None,
    return_gw=None,
    waiver="KEEP ROSTER",
    combined=-10,
    confidence="HIGH",
    recommendation="WATCH",
    news="Knock - 75% chance of playing",
):
    return {
        "player_id": player_id,
        "player": name,
        "position": "MID",
        "club": "TST",
        "team_code": 1,
        "chance_next_round": chance,
        "news": news,
        "fixtures": [
            {"gameweek": 2, "matches": [{"opponent": "EVE", "venue": "H", "difficulty": 2}]},
            {"gameweek": 3, "matches": [{"opponent": "MCI", "venue": "A", "difficulty": 5}]},
        ],
        "intelligence": {
            "injury_return_signal": "near-return" if chance >= 75 else "out",
            "health_trend": "stable",
            "expected_return": expected_return,
            "expected_return_gameweek": return_gw,
            "post_return_fixture_score": post_return,
            "future_fixture_score": future,
            "stash_fixture_score": post_return if post_return is not None else future * 0.65,
            "stash_score": stash,
            "recommendation": recommendation,
            "recommendation_reason": "Test recommendation.",
        },
        "replacement": {
            "action": waiver,
            "drop_player": "Owned MID",
            "combined_delta": combined,
            "confidence": confidence,
            "true_stash_candidate": True,
        },
    }


def test_dashboard_prioritizes_decisions_instead_of_listing_every_injury():
    squad = [player(1, "Owned concern", recommendation="HOLD")]
    monitor = player(2, "Monitor target")
    low_value = player(3, "Low value", stash=30, future=40, combined=-40)

    dashboard = build_injury_stash_dashboard(squad, [monitor, low_value])

    assert [row["player"] for row in dashboard["squad_health"]] == ["Owned concern"]
    assert [row["player"] for row in dashboard["stash_candidates"]] == ["Monitor target"]
    assert dashboard["stash_candidates"][0]["dashboard_action"] == "MONITOR"
    assert dashboard["summary"]["active_watch_count"] == 3
    assert dashboard["summary"]["decision_count"] == 2


def test_dashboard_surfaces_a_dated_return_and_its_fixture():
    returning = player(
        2,
        "Returning target",
        expected_return="2026-08-29",
        return_gw=2,
        post_return=80,
        waiver="STASH SWAP",
        combined=8,
    )

    dashboard = build_injury_stash_dashboard([], [returning])

    [candidate] = dashboard["stash_candidates"]
    [calendar] = dashboard["return_calendar"]
    assert candidate["dashboard_action"] == "STASH SWAP"
    assert calendar["expected_return_gameweek"] == 2
    assert calendar["return_fixture"] == {"gameweek": 2, "label": "EVE (H)", "difficulty": 2.0}
    assert dashboard["summary"]["act_now"] == 1


def test_dashboard_excludes_permanent_departures():
    departed = player(
        4,
        "Departed",
        chance=0,
        stash=90,
        future=90,
        waiver="STASH SWAP",
        combined=20,
        news="Has joined Another Club permanently",
    )

    dashboard = build_injury_stash_dashboard([], [departed])

    assert dashboard["summary"]["active_watch_count"] == 0
    assert dashboard["stash_candidates"] == []
    assert dashboard["return_calendar"] == []


def test_report_injury_count_excludes_permanent_departures():
    active = player(1, "Active injury", chance=0)
    departed = player(2, "Departed", chance=0, news="Has joined Another Club permanently")
    active["status"] = "a"
    departed["status"] = "a"

    report = build_report(
        "123",
        "456",
        {"league": {"name": "Test"}, "league_entries": []},
        {"events": [{"id": 1, "is_current": True}]},
        [active, departed],
        [],
        4,
        [1, 2, 3, 4],
    )

    assert report["summary"]["injured_or_doubtful_count"] == 1
    assert [row["player"] for row in report["injury_watch"]] == ["Active injury"]
