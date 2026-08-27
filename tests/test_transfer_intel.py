from datetime import datetime, timezone

from fpl_toolkit.injury_stash import build_injury_stash_dashboard
from fpl_toolkit.intelligence import attach_intelligence, is_hard_inactive
from fpl_toolkit.optimizer import player_start_score
from fpl_toolkit.privacy import sanitize_public_report
from fpl_toolkit.report import build_report
from fpl_toolkit.standard_fpl_transfers import rank_single_transfers
from fpl_toolkit.transfer_intel import attach_transfer_intel, load_transfer_intel


NOW = datetime(2026, 8, 27, 13, 0, tzinfo=timezone.utc)


def player(player_id=55, name="Watkins", team_id=2, owner=None, status="a"):
    return {
        "player_id": player_id,
        "player": name,
        "club": "AVL",
        "team_id": team_id,
        "team_code": 7,
        "position": "FWD",
        "status": status,
        "owner_entry_id": owner,
        "chance_next_round": None,
        "news": "",
        "minutes": 2700,
        "starts": 30,
        "total_points": 160,
        "points_per_game": "5.3",
        "goals_scored": 15,
        "assists": 8,
        "expected_goal_involvements": "20.0",
        "fixtures": fixture_run(2, 4),
    }


def fixture_run(team_id, difficulty):
    return [
        {
            "gameweek": gameweek,
            "matches": [{
                "opponent": f"T{team_id + gameweek}",
                "venue": "H",
                "difficulty": difficulty,
                "started": False,
                "finished": False,
            }],
        }
        for gameweek in range(2, 6)
    ]


def record(**overrides):
    base = {
        "id": "test-move",
        "player": "Watkins",
        "player_ids": [55],
        "status": "deal_agreed",
        "move_kind": "exit_league",
        "source_tier": "reliable_report",
        "reported_at": "2026-08-27T10:00:00Z",
        "expires_at": "2026-09-03T00:00:00Z",
        "destination": {"club": "Al-Hilal", "league": "Saudi Pro League", "team_id": None},
        "role_outlook": "projected_starter",
        "summary": "Deal agreed.",
        "sources": [{"label": "Source", "url": "https://example.com/report"}],
    }
    base.update(overrides)
    return base


def test_agreed_exit_blocks_selection_and_acquisition():
    [enriched] = attach_transfer_intel(
        [player()], {"2": fixture_run(2, 4)}, records=[record()], now=NOW
    )
    [scored] = attach_intelligence([enriched])

    assert enriched["transfer_intel"]["action"] == "EXIT AGREED"
    assert enriched["transfer_intel"]["blocks_selection"] is True
    assert enriched["transfer_intel"]["blocks_acquisition"] is True
    assert is_hard_inactive(enriched) is True
    assert scored["intelligence"]["availability_score"] == 0.0
    assert player_start_score(scored, 2)["start_score"] < 10


def test_agreed_exit_is_removed_from_the_claimable_pool():
    [enriched] = attach_transfer_intel(
        [player()], {"2": fixture_run(2, 4)}, records=[record()], now=NOW
    )
    report = build_report(
        "1",
        "1",
        {"league": {"name": "Test"}, "league_entries": []},
        {"events": []},
        [enriched],
        [],
        4,
        [2, 3, 4, 5],
    )

    assert report["available_players"] == []
    assert report["summary"]["available_count"] == 0


def test_agreed_exit_is_removed_from_standard_transfer_candidates():
    [enriched] = attach_transfer_intel(
        [player()], {"2": fixture_run(2, 4)}, records=[record()], now=NOW
    )
    outgoing = player(999, "Outgoing", team_id=3)
    outgoing["is_owned"] = True
    ranking = rank_single_transfers(
        [enriched, outgoing],
        [outgoing],
        2,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=0,
    )

    assert ranking["evaluated_pairs"] == 0
    assert ranking["candidates"] == []


def test_talks_are_visible_but_do_not_change_scores():
    rumour = record(
        status="talks",
        move_kind="within_league",
        source_tier="rumour",
        destination={"club": "Sunderland", "league": "Premier League", "team_id": 20},
        role_outlook="uncertain",
    )
    [enriched] = attach_transfer_intel(
        [player()], {"2": fixture_run(2, 4), "20": fixture_run(20, 2)}, records=[rumour], now=NOW
    )
    [scored] = attach_intelligence([enriched])

    assert enriched["transfer_intel"]["action"] == "RUMOUR WATCH"
    assert enriched["transfer_intel"]["blocks_selection"] is False
    assert enriched["transfer_intel"]["blocks_acquisition"] is False
    assert scored["intelligence"]["availability_score"] == 100.0


def test_confirmed_internal_move_can_be_an_early_pickup():
    confirmed = record(
        status="confirmed",
        move_kind="within_league",
        source_tier="official_club",
        destination={"club": "Good Fixtures FC", "league": "Premier League", "team_id": 9},
        role_outlook="strong_rotation",
    )
    destination = fixture_run(9, 2)
    [enriched] = attach_transfer_intel(
        [player()], {"2": fixture_run(2, 4), "9": destination}, records=[confirmed], now=NOW
    )

    assert enriched["transfer_intel"]["action"] == "EARLY PICKUP"
    assert enriched["transfer_intel"]["destination_fixture_score"] == 80.0
    assert enriched["transfer_intel"]["fixture_delta"] == 40.0
    assert enriched["fixtures"] == destination


def test_agreed_internal_move_can_flag_early_pickup_without_overriding_availability():
    agreed = record(
        move_kind="within_league",
        source_tier="reliable_report",
        destination={"club": "Good Fixtures FC", "league": "Premier League", "team_id": 9},
        role_outlook="projected_starter",
    )
    current = fixture_run(2, 4)
    [enriched] = attach_transfer_intel(
        [player()], {"2": current, "9": fixture_run(9, 2)}, records=[agreed], now=NOW
    )
    [scored] = attach_intelligence([enriched])

    assert enriched["transfer_intel"]["action"] == "EARLY PICKUP"
    assert enriched["transfer_intel"]["blocks_selection"] is False
    assert enriched["transfer_intel"]["blocks_acquisition"] is False
    assert enriched["fixtures"] == current
    assert scored["intelligence"]["availability_score"] == 100.0


def test_expired_record_has_no_effect():
    expired = record(expires_at="2026-08-27T11:00:00Z")
    [enriched] = attach_transfer_intel(
        [player()], {"2": fixture_run(2, 4)}, records=[expired], now=NOW
    )

    assert "transfer_intel" not in enriched


def test_availability_dashboard_includes_opponent_exit_and_free_early_pickup():
    opponent = player(owner="opponent", status="o")
    [opponent] = attach_transfer_intel(
        [opponent], {"2": fixture_run(2, 4)}, records=[record()], now=NOW
    )
    early = player(77, "Early", team_id=3)
    early["transfer_intel"] = {
        "action": "EARLY PICKUP",
        "status": "confirmed",
        "move_kind": "within_league",
        "source_tier": "official_club",
        "destination": {"club": "Target", "league": "Premier League", "team_id": 9},
        "destination_fixture_score": 80.0,
        "current_fixture_score": 40.0,
        "fixture_delta": 40.0,
        "role_outlook": "projected_starter",
        "feed_synced": False,
        "blocks_selection": False,
        "blocks_acquisition": False,
        "summary": "Confirmed move into a strong run.",
        "sources": [{"label": "Club", "url": "https://example.com/club"}],
        "expires_at": "2026-09-03T00:00:00Z",
    }

    dashboard = build_injury_stash_dashboard([], [early], tracked_players=[opponent, early])

    assert dashboard["summary"]["transfer_alerts"] == 2
    assert dashboard["summary"]["early_pickups"] == 1
    assert [row["player"] for row in dashboard["early_pickups"]] == ["Early"]
    watkins = next(row for row in dashboard["transfer_watch"] if row["player"] == "Watkins")
    assert watkins["context"] == "OWNED ELSEWHERE"
    assert watkins["dashboard_action"] == "EXIT AGREED"


def test_packaged_transfer_records_validate():
    records = load_transfer_intel()

    assert {record["player"] for record in records} >= {"Watkins", "Delap", "N.Jackson", "Grealish"}


def test_public_transfer_cards_strip_owner_identity_fields():
    public = sanitize_public_report({
        "injury_stash": {
            "transfer_watch": [{
                "player_id": 55,
                "player": "Watkins",
                "owner_entry_id": "private-opponent",
                "owner_name": "Private Opponent",
            }],
            "early_pickups": [],
        }
    })

    card = public["injury_stash"]["transfer_watch"][0]
    assert "owner_entry_id" not in card
    assert "owner_name" not in card
