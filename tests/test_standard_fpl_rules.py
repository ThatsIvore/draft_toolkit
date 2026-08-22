import pytest

from fpl_toolkit.standard_fpl_rules import (
    RULES_2026_27,
    StandardFplRulesError,
    evaluate_single_transfer,
    rules_for_season,
    rules_summary,
    season_from_bootstrap,
    validate_squad_legality,
)


POSITIONS = ["GKP"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3


def _legal_squad():
    return [
        {
            "player_id": index,
            "player": f"P{index}",
            "position": position,
            "team_id": ((index - 1) % 5) + 1,
            "now_cost": 5.0,
            "purchase_price": 5.0,
            "selling_price": 5.0,
        }
        for index, position in enumerate(POSITIONS, start=1)
    ]


def _incoming(**overrides):
    player = {
        "player_id": 99,
        "player": "Incoming",
        "position": "DEF",
        "team_id": 6,
        "now_cost": 5.5,
    }
    player.update(overrides)
    return player


def test_2026_27_rules_are_explicit_and_season_versioned():
    rules = rules_for_season("2026-27")
    assert rules is RULES_2026_27
    assert rules.position_limits == {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
    assert rules.initial_budget_tenths == 1000
    assert rules.max_players_per_club == 3
    assert rules.max_banked_free_transfers == 5
    assert rules.extra_transfer_cost_points == 4
    assert rules_summary(rules)["initial_budget"] == 100.0

    with pytest.raises(StandardFplRulesError, match="No Standard FPL rules"):
        rules_for_season("2027-28")

    assert season_from_bootstrap(
        {"events": [{"id": 1, "deadline_time": "2026-08-14T17:30:00Z"}]}
    ) == "2026-27"


def test_squad_legality_checks_shape_uniqueness_and_club_quota():
    legal = validate_squad_legality(_legal_squad())
    assert legal["is_legal"] is True
    assert legal["issues"] == []

    wrong_shape = _legal_squad()
    wrong_shape[2]["position"] = "MID"
    invalid = validate_squad_legality(wrong_shape)
    assert invalid["is_legal"] is False
    assert "position_shape" in {row["code"] for row in invalid["issues"]}

    club_heavy = _legal_squad()
    for row in club_heavy[:4]:
        row["team_id"] = 1
    invalid = validate_squad_legality(club_heavy)
    assert "club_quota" in {row["code"] for row in invalid["issues"]}


def test_single_transfer_uses_selling_price_bank_and_free_allowance():
    squad = _legal_squad()
    squad[2]["selling_price"] = 5.0
    result = evaluate_single_transfer(
        squad,
        _incoming(now_cost=5.5),
        outgoing_player_id=3,
        bank_tenths=5,
        free_transfers=2,
        transfers_made=0,
    )

    assert result["is_legal"] is True
    assert result["money"] == {
        "bank_before_tenths": 5,
        "selling_price_tenths": 50,
        "incoming_cost_tenths": 55,
        "bank_after_tenths": 0,
    }
    assert result["transfer_allowance"]["uses_free_transfer"] is True
    assert result["transfer_allowance"]["free_transfers_remaining_after"] == 1
    assert result["transfer_allowance"]["incremental_cost_points"] == 0
    assert result["resulting_squad_legality"]["is_legal"] is True
    assert result["advisory_only"] is True


def test_single_transfer_reports_incremental_hit_and_chip_override():
    squad = _legal_squad()
    hit = evaluate_single_transfer(
        squad,
        _incoming(now_cost=5.0),
        outgoing_player_id=3,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=1,
    )
    assert hit["is_legal"] is True
    assert hit["transfer_allowance"]["uses_free_transfer"] is False
    assert hit["transfer_allowance"]["incremental_cost_points"] == 4

    wildcard = evaluate_single_transfer(
        squad,
        _incoming(now_cost=5.0),
        outgoing_player_id=3,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=1,
        active_chip="wildcard",
    )
    assert wildcard["is_legal"] is True
    assert wildcard["transfer_allowance"]["chip_makes_transfers_free"] is True
    assert wildcard["transfer_allowance"]["banked_transfers_preserved"] is True
    assert wildcard["transfer_allowance"]["free_transfers_remaining_after"] == 1
    assert wildcard["transfer_allowance"]["incremental_cost_points"] == 0


def test_single_transfer_rejects_position_budget_ownership_and_club_errors():
    squad = _legal_squad()
    squad[2]["selling_price"] = 4.5
    mismatch = evaluate_single_transfer(
        squad,
        _incoming(position="MID", now_cost=5.0),
        outgoing_player_id=3,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=0,
    )
    mismatch_codes = {row["code"] for row in mismatch["issues"]}
    assert "position_mismatch" in mismatch_codes
    assert "insufficient_funds" in mismatch_codes

    already_owned = evaluate_single_transfer(
        squad,
        dict(squad[3]),
        outgoing_player_id=3,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=0,
    )
    assert "incoming_already_owned" in {row["code"] for row in already_owned["issues"]}

    club_quota = evaluate_single_transfer(
        squad,
        _incoming(team_id=1, now_cost=4.5),
        outgoing_player_id=3,
        bank_tenths=0,
        free_transfers=1,
        transfers_made=0,
    )
    assert "club_quota" in {row["code"] for row in club_quota["issues"]}
    assert club_quota["is_legal"] is False


def test_single_transfer_requires_current_private_financial_state():
    result = evaluate_single_transfer(
        _legal_squad(),
        _incoming(now_cost=None),
        outgoing_player_id=3,
        bank_tenths=0,
        free_transfers=6,
        transfers_made=-1,
    )
    codes = {row["code"] for row in result["issues"]}
    assert "missing_incoming_cost" in codes
    assert "invalid_free_transfers" in codes
    assert "invalid_transfers_made" in codes
    assert result["transfer_allowance"]["incremental_cost_points"] is None
