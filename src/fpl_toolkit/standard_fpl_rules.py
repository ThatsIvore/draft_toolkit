from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


class StandardFplRulesError(RuntimeError):
    pass


@dataclass(frozen=True)
class StandardFplRules:
    season: str
    initial_budget_tenths: int
    squad_size: int
    position_limits: dict[str, int]
    max_players_per_club: int
    max_banked_free_transfers: int
    extra_transfer_cost_points: int


RULES_2026_27 = StandardFplRules(
    season="2026-27",
    initial_budget_tenths=1_000,
    squad_size=15,
    position_limits={"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3},
    max_players_per_club=3,
    max_banked_free_transfers=5,
    extra_transfer_cost_points=4,
)

RULES_BY_SEASON = {RULES_2026_27.season: RULES_2026_27}
DEFAULT_RULES_SEASON = RULES_2026_27.season
FREE_TRANSFER_CHIPS = {"wildcard", "freehit", "free_hit"}


def rules_for_season(season: str = DEFAULT_RULES_SEASON) -> StandardFplRules:
    try:
        return RULES_BY_SEASON[season]
    except KeyError as exc:
        raise StandardFplRulesError(
            f"No Standard FPL rules are defined for season {season}. "
            "Add and verify a season-specific ruleset before continuing."
        ) from exc


def rules_summary(rules: StandardFplRules = RULES_2026_27) -> dict[str, Any]:
    return {
        "season": rules.season,
        "initial_budget": rules.initial_budget_tenths / 10.0,
        "squad_size": rules.squad_size,
        "position_limits": dict(rules.position_limits),
        "max_players_per_club": rules.max_players_per_club,
        "max_banked_free_transfers": rules.max_banked_free_transfers,
        "extra_transfer_cost_points": rules.extra_transfer_cost_points,
    }


def season_from_bootstrap(bootstrap: dict[str, Any]) -> str | None:
    events = bootstrap.get("events")
    if not isinstance(events, list):
        return None
    for event in events:
        if not isinstance(event, dict):
            continue
        deadline = event.get("deadline_time")
        if not isinstance(deadline, str) or not deadline:
            continue
        try:
            start_year = datetime.fromisoformat(deadline.replace("Z", "+00:00")).year
        except ValueError:
            continue
        return f"{start_year}-{str(start_year + 1)[-2:]}"
    return None


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def validate_squad_legality(
    squad: list[dict[str, Any]],
    rules: StandardFplRules = RULES_2026_27,
) -> dict[str, Any]:
    """Validate structural Standard FPL squad rules without evaluating player quality."""
    issues: list[dict[str, str]] = []
    if len(squad) != rules.squad_size:
        issues.append(
            _issue(
                "squad_size",
                f"Squad must contain {rules.squad_size} players; received {len(squad)}.",
            )
        )

    player_ids = [row.get("player_id") for row in squad]
    if any(player_id is None for player_id in player_ids):
        issues.append(_issue("missing_player_id", "Every squad row must contain player_id."))
    elif len(player_ids) != len(set(player_ids)):
        issues.append(_issue("duplicate_player", "Squad player IDs must be unique."))

    position_counts = {
        position: sum(1 for row in squad if row.get("position") == position)
        for position in rules.position_limits
    }
    unknown_positions = sorted(
        {
            str(row.get("position"))
            for row in squad
            if row.get("position") not in rules.position_limits
        }
    )
    if position_counts != rules.position_limits or unknown_positions:
        issues.append(
            _issue(
                "position_shape",
                f"Squad position counts must be {rules.position_limits}; received {position_counts}.",
            )
        )

    club_counts: dict[int, int] = {}
    missing_club = False
    for row in squad:
        team_id = row.get("team_id")
        if isinstance(team_id, bool) or not isinstance(team_id, int) or team_id <= 0:
            missing_club = True
            continue
        club_counts[team_id] = club_counts.get(team_id, 0) + 1
    if missing_club:
        issues.append(_issue("missing_club", "Every squad row must contain a positive team_id."))
    over_limit = sorted(
        team_id
        for team_id, count in club_counts.items()
        if count > rules.max_players_per_club
    )
    if over_limit:
        issues.append(
            _issue(
                "club_quota",
                f"No club may supply more than {rules.max_players_per_club} players; "
                f"over-limit team IDs: {over_limit}.",
            )
        )

    return {
        "model": "standard-fpl-squad-legality-v0.1",
        "season": rules.season,
        "is_legal": not issues,
        "issues": issues,
        "squad_size": len(squad),
        "position_counts": position_counts,
        "club_counts": club_counts,
    }


def _money_to_tenths(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    tenths = round(amount * 10)
    if amount <= 0 or abs(amount * 10 - tenths) > 1e-6:
        return None
    return int(tenths)


def _unique_issues(issues: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for issue in issues:
        if issue["code"] in seen:
            continue
        seen.add(issue["code"])
        unique.append(issue)
    return unique


def evaluate_single_transfer(
    squad: list[dict[str, Any]],
    incoming: dict[str, Any],
    outgoing_player_id: int,
    *,
    bank_tenths: int,
    free_transfers: int,
    transfers_made: int,
    active_chip: str | None = None,
    rules: StandardFplRules = RULES_2026_27,
) -> dict[str, Any]:
    """Evaluate one proposed transfer for rules, affordability and incremental hit cost."""
    issues: list[dict[str, str]] = []
    outgoing = next(
        (row for row in squad if row.get("player_id") == outgoing_player_id),
        None,
    )
    incoming_player_id = incoming.get("player_id")
    if outgoing is None:
        issues.append(_issue("outgoing_not_owned", "The outgoing player is not in the current squad."))
    if incoming_player_id is None:
        issues.append(_issue("incoming_missing_id", "The incoming player has no player_id."))
    elif any(row.get("player_id") == incoming_player_id for row in squad):
        issues.append(_issue("incoming_already_owned", "The incoming player is already in the squad."))

    if outgoing is not None and outgoing.get("position") != incoming.get("position"):
        issues.append(_issue("position_mismatch", "A single transfer must replace the same position."))

    selling_price_tenths = (
        _money_to_tenths(outgoing.get("selling_price")) if outgoing is not None else None
    )
    incoming_cost_tenths = _money_to_tenths(incoming.get("now_cost"))
    if selling_price_tenths is None:
        issues.append(
            _issue(
                "missing_selling_price",
                "The outgoing player's current selling price is required.",
            )
        )
    if incoming_cost_tenths is None:
        issues.append(_issue("missing_incoming_cost", "The incoming player's current cost is required."))

    if isinstance(bank_tenths, bool) or not isinstance(bank_tenths, int) or bank_tenths < 0:
        issues.append(_issue("invalid_bank", "Bank must be a non-negative integer in tenths."))
        bank_after_tenths = None
    elif selling_price_tenths is not None and incoming_cost_tenths is not None:
        bank_after_tenths = bank_tenths + selling_price_tenths - incoming_cost_tenths
        if bank_after_tenths < 0:
            issues.append(_issue("insufficient_funds", "The proposed transfer is not affordable."))
    else:
        bank_after_tenths = None

    valid_allowance = (
        not isinstance(free_transfers, bool)
        and isinstance(free_transfers, int)
        and 0 <= free_transfers <= rules.max_banked_free_transfers
    )
    valid_made = (
        not isinstance(transfers_made, bool)
        and isinstance(transfers_made, int)
        and transfers_made >= 0
    )
    if not valid_allowance:
        issues.append(
            _issue(
                "invalid_free_transfers",
                f"Free-transfer allowance must be between 0 and {rules.max_banked_free_transfers}.",
            )
        )
    if not valid_made:
        issues.append(_issue("invalid_transfers_made", "Transfers made must be a non-negative integer."))

    resulting_squad = None
    if outgoing is not None and incoming_player_id is not None:
        resulting_squad = [
            dict(incoming) if row.get("player_id") == outgoing_player_id else dict(row)
            for row in squad
        ]
        resulting_legality = validate_squad_legality(resulting_squad, rules)
        issues.extend(resulting_legality["issues"])
    else:
        resulting_legality = None

    normalized_chip = (active_chip or "").strip().lower()
    chip_makes_transfers_free = normalized_chip in FREE_TRANSFER_CHIPS
    if valid_allowance and valid_made:
        charged_before = max(0, transfers_made - free_transfers)
        charged_after = max(0, transfers_made + 1 - free_transfers)
        incremental_charged_transfers = charged_after - charged_before
        transfer_cost_points = (
            0
            if chip_makes_transfers_free
            else incremental_charged_transfers * rules.extra_transfer_cost_points
        )
        uses_free_transfer = not chip_makes_transfers_free and transfers_made < free_transfers
        free_transfers_remaining_after = (
            free_transfers
            if chip_makes_transfers_free
            else max(0, free_transfers - transfers_made - 1)
        )
    else:
        transfer_cost_points = None
        uses_free_transfer = None
        free_transfers_remaining_after = None

    issues = _unique_issues(issues)
    return {
        "model": "standard-fpl-single-transfer-legality-v0.1",
        "season": rules.season,
        "is_legal": not issues,
        "issues": issues,
        "outgoing_player_id": outgoing_player_id,
        "incoming_player_id": incoming_player_id,
        "money": {
            "bank_before_tenths": bank_tenths,
            "selling_price_tenths": selling_price_tenths,
            "incoming_cost_tenths": incoming_cost_tenths,
            "bank_after_tenths": bank_after_tenths,
        },
        "transfer_allowance": {
            "free_transfers": free_transfers,
            "transfers_made": transfers_made,
            "uses_free_transfer": uses_free_transfer,
            "free_transfers_remaining_after": free_transfers_remaining_after,
            "active_chip": active_chip,
            "chip_makes_transfers_free": chip_makes_transfers_free,
            "banked_transfers_preserved": chip_makes_transfers_free,
            "incremental_cost_points": transfer_cost_points,
        },
        "resulting_squad_legality": resulting_legality,
        "advisory_only": True,
    }
