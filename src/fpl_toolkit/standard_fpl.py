from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .api import FantasyApiClient
from .baseline import baseline_lookup
from .config import StandardFplSettings
from .fixtures import attach_fixture_matrix, bootstrap_events, build_team_fixture_matrix, planning_gameweeks
from .intelligence import attach_intelligence
from .optimizer import recommend_lineup
from .report import current_gameweek
from .storage import read_json
from .standard_fpl_snapshot import load_private_snapshot, snapshot_to_picks_payload
from .standard_fpl_outcomes import build_transfer_outcomes
from .standard_fpl_rules import (
    rules_for_season,
    rules_summary,
    season_from_bootstrap,
    validate_squad_legality,
)
from .standard_fpl_transfers import (
    build_transfer_decision,
    rank_single_transfers,
    unavailable_single_transfer_ranking,
)


class StandardFplDataError(RuntimeError):
    pass


SQUAD_SHAPE = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
INTERNAL_OWNERSHIP_FIELDS = {"owner_entry_id", "owner_raw"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _money(value: Any) -> float | None:
    try:
        return round(float(value) / 10.0, 1)
    except (TypeError, ValueError):
        return None


def confirmed_squad_gameweek(bootstrap: dict[str, Any], requested: int | None = None) -> int:
    """Choose the newest Gameweek whose locked picks should be public."""
    events = [event for event in bootstrap_events(bootstrap) if event.get("id") is not None]
    event_ids = {int(event["id"]) for event in events}
    if requested is not None:
        if event_ids and requested not in event_ids:
            raise StandardFplDataError(f"Gameweek {requested} is not present in the current FPL season.")
        return int(requested)

    current = next((int(event["id"]) for event in events if event.get("is_current")), None)
    if current is not None:
        return current
    finished = [int(event["id"]) for event in events if event.get("finished") is True]
    if finished:
        return max(finished)
    next_gameweek = next((int(event["id"]) for event in events if event.get("is_next")), None)
    if next_gameweek and next_gameweek > 1:
        return next_gameweek - 1
    raise StandardFplDataError("No locked standard FPL squad is publicly available yet.")


def _picks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("picks")
    if not isinstance(rows, list):
        raise StandardFplDataError("The standard FPL picks response did not contain a picks list.")
    return [row for row in rows if isinstance(row, dict)]


def normalize_standard_player_pool(
    bootstrap: dict[str, Any],
    picks_payload: dict[str, Any],
    entry_id: str,
) -> list[dict[str, Any]]:
    """Map standard FPL players onto the toolkit's shared player contract."""
    teams = {
        int(team["id"]): team
        for team in bootstrap.get("teams", [])
        if isinstance(team, dict) and team.get("id") is not None
    }
    positions = {
        int(position["id"]): position
        for position in bootstrap.get("element_types", [])
        if isinstance(position, dict) and position.get("id") is not None
    }
    pick_by_id: dict[int, dict[str, Any]] = {}
    for pick in _picks(picks_payload):
        try:
            player_id = int(pick.get("element"))
        except (TypeError, ValueError):
            continue
        pick_by_id[player_id] = pick

    normalized: list[dict[str, Any]] = []
    for element in bootstrap.get("elements", []):
        if not isinstance(element, dict) or element.get("id") is None:
            continue
        player_id = int(element["id"])
        pick = pick_by_id.get(player_id)
        team = teams.get(int(element.get("team") or 0), {})
        position = positions.get(int(element.get("element_type") or 0), {})
        normalized.append({
            "player_id": player_id,
            "player": element.get("web_name") or element.get("second_name") or f"Player {player_id}",
            "club": team.get("short_name") or team.get("name"),
            "team_id": element.get("team"),
            "team_code": team.get("code"),
            "position": position.get("singular_name_short") or position.get("singular_name"),
            "status": element.get("status"),
            "owner_entry_id": entry_id if pick is not None else None,
            "owner_raw": entry_id if pick is not None else None,
            "is_owned": pick is not None,
            "pick_position": pick.get("position") if pick else None,
            "purchase_price": _money(pick.get("purchase_price")) if pick else None,
            "selling_price": _money(pick.get("selling_price")) if pick else None,
            "submitted_multiplier": pick.get("multiplier") if pick else None,
            "submitted_captain": bool(pick and pick.get("is_captain")),
            "submitted_vice_captain": bool(pick and pick.get("is_vice_captain")),
            "chance_next_round": element.get("chance_of_playing_next_round"),
            "news": element.get("news") or "",
            "news_added": element.get("news_added"),
            "event_points": element.get("event_points"),
            "total_points": element.get("total_points"),
            "minutes": element.get("minutes"),
            "starts": element.get("starts"),
            "goals_scored": element.get("goals_scored"),
            "assists": element.get("assists"),
            "clean_sheets": element.get("clean_sheets"),
            "bonus": element.get("bonus"),
            "expected_goal_involvements": element.get("expected_goal_involvements"),
            "form": element.get("form"),
            "points_per_game": element.get("points_per_game"),
            "expected_points_next": element.get("ep_next"),
            "now_cost": _money(element.get("now_cost")),
            "selected_by_percent": _number(element.get("selected_by_percent")),
            "transfers_in_event": element.get("transfers_in_event"),
            "transfers_out_event": element.get("transfers_out_event"),
            "cost_change_event": _money(element.get("cost_change_event")),
            "cost_change_start": _money(element.get("cost_change_start")),
        })
    return normalized


def validate_standard_squad(squad: list[dict[str, Any]]) -> None:
    if len(squad) != 15:
        raise StandardFplDataError(f"Expected 15 standard FPL picks, received {len(squad)}.")
    counts = {
        position: sum(1 for player in squad if player.get("position") == position)
        for position in SQUAD_SHAPE
    }
    if counts != SQUAD_SHAPE:
        raise StandardFplDataError(f"Unexpected standard FPL squad shape: {counts}.")


def confirmed_lineup(
    squad: list[dict[str, Any]],
    gameweek: int,
    picks_payload: dict[str, Any],
    source: str = "standard_fpl_locked_picks",
) -> dict[str, Any]:
    ordered = sorted(squad, key=lambda player: int(player.get("pick_position") or 99))
    starters = [dict(player) for player in ordered if int(player.get("pick_position") or 99) <= 11]
    bench = [dict(player) for player in ordered if int(player.get("pick_position") or 99) > 11]
    return {
        "gameweek": int(gameweek),
        "source": source,
        "is_exact": True,
        "active_chip": picks_payload.get("active_chip"),
        "automatic_subs": picks_payload.get("automatic_subs") or [],
        "event_points_total": (picks_payload.get("entry_history") or {}).get("points"),
        "starters": starters,
        "bench": bench,
    }


def _strip_internal_ownership(player: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in player.items() if key not in INTERNAL_OWNERSHIP_FIELDS}


def _strip_lineup_ownership(lineup: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(lineup)
    for key in ("starters", "bench", "squad"):
        rows = cleaned.get(key)
        if isinstance(rows, list):
            cleaned[key] = [_strip_internal_ownership(row) for row in rows if isinstance(row, dict)]
    reserve = cleaned.get("reserve_goalkeeper")
    if isinstance(reserve, dict):
        cleaned["reserve_goalkeeper"] = _strip_internal_ownership(reserve)
    return cleaned


def _captain_score(player: dict[str, Any]) -> dict[str, Any]:
    selection = player.get("selection") or {}
    availability = _number(selection.get("availability"), 100.0)
    minutes_score = min(100.0, _number(selection.get("expected_minutes")) / 90.0 * 100.0)
    upside = _number(selection.get("upside"))
    floor = _number(selection.get("floor"))
    fixture = _number(selection.get("next_fixture"))
    start_score = _number(selection.get("start_score"))
    raw = 0.30 * upside + 0.25 * fixture + 0.20 * minutes_score + 0.15 * floor + 0.10 * start_score
    availability_factor = 0.25 + 0.75 * max(0.0, min(100.0, availability)) / 100.0
    return {
        "captain_score": round(raw * availability_factor, 1),
        "availability": round(availability, 1),
        "expected_minutes": round(_number(selection.get("expected_minutes")), 1),
        "fixture_score": round(fixture, 1),
        "floor": round(floor, 1),
        "upside": round(upside, 1),
    }


def recommend_captaincy(recommended_lineup: dict[str, Any]) -> dict[str, Any]:
    if not recommended_lineup.get("is_valid"):
        return {
            "model": "standard-fpl-captain-v0.1",
            "is_valid": False,
            "captain": None,
            "vice_captain": None,
            "shortlist": [],
            "note": "Captaincy could not be evaluated without a legal Recommended XI.",
        }
    candidates = []
    for player in recommended_lineup.get("starters") or []:
        score = _captain_score(player)
        candidates.append({
            "player_id": player.get("player_id"),
            "player": player.get("player"),
            "club": player.get("club"),
            "position": player.get("position"),
            **score,
        })
    candidates.sort(
        key=lambda row: (row["captain_score"], row["upside"], row["expected_minutes"]),
        reverse=True,
    )
    captain = dict(candidates[0]) if candidates else None
    vice = dict(candidates[1]) if len(candidates) > 1 else None
    return {
        "model": "standard-fpl-captain-v0.1",
        "is_valid": bool(captain and vice),
        "captain": captain,
        "vice_captain": vice,
        "shortlist": candidates[:5],
        "note": "Captain Score is a transparent selection heuristic, not projected FPL points. No lineup is submitted.",
    }


def _entry_history(picks_payload: dict[str, Any], history: dict[str, Any], gameweek: int) -> dict[str, Any]:
    pick_history = picks_payload.get("entry_history")
    if isinstance(pick_history, dict):
        return pick_history
    for row in history.get("current") or []:
        if isinstance(row, dict) and int(row.get("event") or 0) == int(gameweek):
            return row
    return {}


def collect_standard_fpl(
    settings: StandardFplSettings,
    client: FantasyApiClient | None = None,
    previous_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a private, read-only Standard FPL Phase 1 proof-of-concept report."""
    client = client or FantasyApiClient()
    if previous_report is None:
        previous_path = Path(settings.output_path)
        if previous_path.exists():
            try:
                loaded_previous = read_json(previous_path)
            except (OSError, ValueError) as exc:
                raise StandardFplDataError(
                    f"Could not read the previous private Standard FPL report at {previous_path}."
                ) from exc
            if not isinstance(loaded_previous, dict) or loaded_previous.get("mode") != "standard_fpl":
                raise StandardFplDataError(
                    f"The previous private report at {previous_path} is not a Standard FPL report."
                )
            previous_report = loaded_previous
    bootstrap = client.bootstrap_static()
    rules = rules_for_season()
    detected_season = season_from_bootstrap(bootstrap)
    if detected_season is not None and detected_season != rules.season:
        raise StandardFplDataError(
            f"FPL bootstrap appears to be for {detected_season}, but the newest verified "
            f"Standard FPL ruleset is {rules.season}. Verify and add the new season before continuing."
        )
    fixtures = client.fixtures()
    entry = client.entry(settings.entry_id)
    history = client.entry_history(settings.entry_id)
    if previous_report is not None:
        previous_team_name = (previous_report.get("entry_context") or {}).get("team_name")
        if previous_team_name != entry.get("name"):
            previous_report = None

    planning_gws = planning_gameweeks(bootstrap, settings.planning_horizon, fixtures)
    scoring_gameweek = current_gameweek(bootstrap, planning_gws)
    if not planning_gws:
        raise StandardFplDataError("No actionable standard FPL planning Gameweek is currently available.")
    decision_gameweek = int(planning_gws[0])

    private_snapshot = None
    if settings.private_snapshot_path:
        known_player_ids = {
            int(row["id"])
            for row in bootstrap.get("elements", [])
            if isinstance(row, dict) and row.get("id") is not None
        }
        private_snapshot = load_private_snapshot(
            settings.private_snapshot_path,
            known_player_ids=known_player_ids,
        )
        if private_snapshot["decision_gameweek"] != decision_gameweek:
            raise StandardFplDataError(
                "The private snapshot is for Gameweek "
                f"{private_snapshot['decision_gameweek']}, but the next actionable Gameweek is "
                f"{decision_gameweek}. Capture a fresh snapshot."
            )
        source_gameweek = decision_gameweek
        picks_payload = snapshot_to_picks_payload(private_snapshot)
    else:
        source_gameweek = confirmed_squad_gameweek(bootstrap, settings.squad_gameweek)
        picks_payload = client.entry_picks(settings.entry_id, source_gameweek)

    players = normalize_standard_player_pool(bootstrap, picks_payload, settings.entry_id)
    fixture_matrix = build_team_fixture_matrix(
        fixtures,
        bootstrap,
        settings.planning_horizon,
        gameweeks=planning_gws,
    )
    players = attach_fixture_matrix(players, fixture_matrix)
    baseline_path = Path(settings.performance_baseline_path)
    baseline_rows = read_json(baseline_path) if baseline_path.exists() else []
    players = attach_intelligence(
        players,
        my_entry_id=settings.entry_id,
        performance_baseline=baseline_lookup(baseline_rows),
        current_gameweek=scoring_gameweek,
    )
    squad = [player for player in players if player.get("is_owned")]
    validate_standard_squad(squad)
    squad_legality = validate_squad_legality(squad, rules)

    official = confirmed_lineup(
        squad,
        source_gameweek,
        picks_payload,
        source=(
            "standard_fpl_private_snapshot"
            if private_snapshot is not None
            else "standard_fpl_locked_picks"
        ),
    )
    recommended = recommend_lineup(squad, decision_gameweek)
    recommended["mode"] = "standard_fpl"
    recommended["note"] = (
        "Toolkit recommendation only; this is not the submitted standard FPL lineup, "
        "and Start Score is not projected FPL points."
    )
    captaincy = recommend_captaincy(recommended)
    output_squad = [_strip_internal_ownership(player) for player in squad]
    official = _strip_lineup_ownership(official)
    recommended = _strip_lineup_ownership(recommended)
    event_history = _entry_history(picks_payload, history, source_gameweek)
    squad_is_current_for_decision = private_snapshot is not None or source_gameweek == decision_gameweek
    if private_snapshot is not None:
        transfer_state = private_snapshot["transfers"]
        active_chip = next(
            (
                str(chip.get("name"))
                for chip in private_snapshot["chips"]
                if chip.get("status") == "active" and chip.get("name")
            ),
            None,
        )
        single_transfer_candidates = rank_single_transfers(
            players,
            squad,
            decision_gameweek,
            bank_tenths=transfer_state["bank_tenths"],
            free_transfers=transfer_state["free_transfers"],
            transfers_made=transfer_state["transfers_made"],
            active_chip=active_chip,
            rules=rules,
        )
        transfer_decision = build_transfer_decision(
            single_transfer_candidates,
            free_transfers=transfer_state["free_transfers"],
            transfers_made=transfer_state["transfers_made"],
            max_banked_free_transfers=rules.max_banked_free_transfers,
        )
        financial_snapshot = {
            "gameweek": decision_gameweek,
            "bank": _money(transfer_state["bank_tenths"]),
            "squad_value": _money(transfer_state["squad_value_tenths"]),
            "event_transfers": transfer_state["transfers_made"],
            "event_transfer_cost": None,
            "free_transfers": transfer_state["free_transfers"],
            "chips": private_snapshot["chips"],
            "has_current_selling_prices": True,
            "has_current_free_transfer_balance": True,
            "has_current_chip_state": True,
        }
        squad_source = {
            "gameweek": decision_gameweek,
            "type": "private_current_team_snapshot",
            "captured_at": private_snapshot["captured_at"],
            "schema_version": private_snapshot["schema_version"],
            "is_exact_for_source_gameweek": True,
            "is_exact_for_decision_gameweek": True,
            "warning": None,
        }
        limitations = [
            "The private snapshot is read-only and must be refreshed after FPL team changes.",
            "No transfer, captain, chip or lineup action is submitted to FPL.",
            "Start Score and Captain Score are heuristics, not projected FPL points.",
        ]
    else:
        single_transfer_candidates = unavailable_single_transfer_ranking()
        transfer_decision = build_transfer_decision(
            single_transfer_candidates,
            free_transfers=0,
            transfers_made=0,
            max_banked_free_transfers=rules.max_banked_free_transfers,
        )
        financial_snapshot = {
            "gameweek": source_gameweek,
            "bank": _money(event_history.get("bank")),
            "squad_value": _money(event_history.get("value")),
            "event_transfers": event_history.get("event_transfers"),
            "event_transfer_cost": event_history.get("event_transfers_cost"),
            "free_transfers": None,
            "chips": [],
            "has_current_selling_prices": False,
            "has_current_free_transfer_balance": False,
            "has_current_chip_state": False,
        }
        squad_source = {
            "gameweek": source_gameweek,
            "type": "public_locked_picks",
            "is_exact_for_source_gameweek": True,
            "is_exact_for_decision_gameweek": squad_is_current_for_decision,
            "warning": None if squad_is_current_for_decision else (
                "This is the latest publicly confirmed squad. Transfers made after its deadline are hidden, "
                "so it may differ from the squad available for the decision Gameweek."
            ),
        }
        limitations = [
            "The public locked squad can become stale when the manager makes transfers for the next deadline.",
            "The POC does not know current purchase prices, selling prices, banked free transfers or chip availability.",
            "No transfer, captain, chip or lineup action is submitted to FPL.",
            "Start Score and Captain Score are heuristics, not projected FPL points.",
        ]

    generated_at = datetime.now(timezone.utc).isoformat()
    transfer_outcomes = build_transfer_outcomes(
        previous_report,
        transfer_decision,
        players,
        fixtures,
        scoring_gameweek=scoring_gameweek,
        decision_gameweek=decision_gameweek,
        generated_at=generated_at,
    )

    return {
        "mode": "standard_fpl",
        "poc_version": "phase-1-v0.4",
        "generated_at": generated_at,
        "entry_context": {
            "team_name": entry.get("name"),
        },
        "current_gameweek": scoring_gameweek,
        "decision_gameweek": decision_gameweek,
        "planning_gameweeks": planning_gws,
        "rules": rules_summary(rules),
        "squad_legality": squad_legality,
        "squad_source": squad_source,
        "financial_snapshot": financial_snapshot,
        "summary": {
            "squad_count": len(squad),
            "recommended_formation": recommended.get("formation"),
            "captain": (captaincy.get("captain") or {}).get("player"),
            "vice_captain": (captaincy.get("vice_captain") or {}).get("player"),
            "performance_baseline_players": len(baseline_rows),
        },
        "squad": output_squad,
        "confirmed_lineup": official,
        "recommended_lineup": recommended,
        "captaincy": captaincy,
        "single_transfer_candidates": single_transfer_candidates,
        "transfer_decision": transfer_decision,
        "transfer_outcomes": transfer_outcomes,
        "limitations": limitations,
    }
