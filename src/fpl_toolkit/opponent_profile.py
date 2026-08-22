from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
import unicodedata
from typing import Any


PROFILE_MODEL = "v0.1"
HISTORY_SCHEMA_VERSION = 1


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _normalise(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9þðæø]+", "", text.casefold())


def _entries(league_details: dict[str, Any]) -> list[dict[str, Any]]:
    rows = league_details.get("league_entries") or league_details.get("entries") or []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _entry_key(entry: dict[str, Any]) -> str | None:
    value = entry.get("entry_id", entry.get("entry"))
    if value is None:
        value = entry.get("id")
    return str(value) if value is not None else None


def _entry_aliases(entry: dict[str, Any]) -> set[str]:
    return {
        str(entry[key])
        for key in ("id", "entry_id", "entry")
        if entry.get(key) is not None
    }


def _manager_initials(entry: dict[str, Any]) -> str:
    first = str(entry.get("player_first_name") or entry.get("first_name") or "").strip()
    last = str(entry.get("player_last_name") or entry.get("last_name") or "").strip()
    return f"{first[:1]}{last[:1]}".upper()


def expand_draft_picks(draft: dict[str, Any]) -> list[dict[str, Any]]:
    teams = [row for row in draft.get("teams") or [] if isinstance(row, dict)]
    rounds = [row for row in draft.get("rounds") or [] if isinstance(row, list)]
    player_ids = draft.get("player_ids") or []
    by_slot = {int(row.get("draft_slot") or 0): row for row in teams}
    team_count = len(teams)
    if not team_count or set(by_slot) != set(range(1, team_count + 1)):
        raise ValueError("Draft teams must have consecutive draft slots starting at 1.")
    picks: list[dict[str, Any]] = []
    for round_number, players in enumerate(rounds, start=1):
        if len(players) != team_count:
            raise ValueError(f"Draft round {round_number} has {len(players)} picks; expected {team_count}.")
        for round_pick, player in enumerate(players, start=1):
            draft_slot = round_pick if round_number % 2 else team_count - round_pick + 1
            team = by_slot[draft_slot]
            picks.append({
                "overall_pick": (round_number - 1) * team_count + round_pick,
                "round": round_number,
                "round_pick": round_pick,
                "draft_slot": draft_slot,
                "draft_code": team.get("draft_code"),
                "team_name": team.get("team_name"),
                "player": str(player),
                "player_id": (
                    player_ids[round_number - 1][round_pick - 1]
                    if round_number - 1 < len(player_ids)
                    and isinstance(player_ids[round_number - 1], list)
                    and round_pick - 1 < len(player_ids[round_number - 1])
                    else None
                ),
            })
    return picks


def _relative_scores(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low, high = min(values.values()), max(values.values())
    if abs(high - low) < 0.001:
        return {key: 50.0 for key in values}
    return {
        key: 35.0 + 30.0 * (value - low) / (high - low)
        for key, value in values.items()
    }


def draft_profiles(draft: dict[str, Any] | None, ownership: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not draft:
        return {}
    picks = expand_draft_picks(draft)
    players_by_name: dict[str, list[dict[str, Any]]] = {}
    players_by_id = {str(player.get("player_id")): player for player in ownership if player.get("player_id") is not None}
    for player in ownership:
        players_by_name.setdefault(_normalise(player.get("player")), []).append(player)

    resolved: list[dict[str, Any]] = []
    for pick in picks:
        matches = players_by_name.get(_normalise(pick.get("player")), [])
        player = players_by_id.get(str(pick.get("player_id"))) if pick.get("player_id") is not None else None
        if player is None and len(matches) == 1:
            player = matches[0]
        intel = (player or {}).get("intelligence") or {}
        resolved.append({
            **pick,
            "resolved": player is not None,
            "player_id": player.get("player_id") if player else pick.get("player_id"),
            "position": player.get("position") if player else None,
            "baseline_score": intel.get("baseline_score") if player else None,
        })

    position_ordinals: dict[str, int] = {}
    for pick in resolved:
        position = str(pick.get("position") or "")
        if not position:
            continue
        position_ordinals[position] = position_ordinals.get(position, 0) + 1
        pick["position_pick"] = position_ordinals[position]
    for position in {str(pick.get("position")) for pick in resolved if pick.get("position")}:
        rows = [pick for pick in resolved if pick.get("position") == position and pick.get("baseline_score") is not None]
        rows.sort(key=lambda row: _number(row.get("baseline_score")), reverse=True)
        for rank, pick in enumerate(rows, start=1):
            pick["baseline_position_rank"] = rank

    codes = [str(row.get("draft_code")) for row in draft.get("teams") or []]
    team_rows = {code: [pick for pick in resolved if str(pick.get("draft_code")) == code] for code in codes}
    roster_raw = {
        code: _mean([_number(pick.get("baseline_score")) for pick in rows if pick.get("baseline_score") is not None])
        for code, rows in team_rows.items()
    }
    value_raw = {
        code: _mean([
            _number(pick.get("position_pick")) - _number(pick.get("baseline_position_rank"))
            for pick in rows
            if pick.get("position_pick") is not None and pick.get("baseline_position_rank") is not None
        ])
        for code, rows in team_rows.items()
    }
    roster_scores = _relative_scores(roster_raw)
    value_scores = _relative_scores(value_raw)

    output: dict[str, dict[str, Any]] = {}
    for team in draft.get("teams") or []:
        code = str(team.get("draft_code"))
        rows = team_rows.get(code, [])
        resolved_count = sum(1 for pick in rows if pick.get("resolved"))
        coverage = resolved_count / len(rows) if rows else 0.0
        raw_score = 0.58 * roster_scores.get(code, 50.0) + 0.42 * value_scores.get(code, 50.0)
        score = 50.0 + (raw_score - 50.0) * coverage
        adjustment = _clamp((score - 50.0) / 15.0 * 0.6, -0.6, 0.6)
        output[code] = {
            "draft_code": code,
            "draft_slot": team.get("draft_slot"),
            "team_name": team.get("team_name"),
            "score": round(score, 1),
            "roster_strength_score": round(roster_scores.get(code, 50.0), 1),
            "pick_value_score": round(value_scores.get(code, 50.0), 1),
            "resolved_picks": resolved_count,
            "total_picks": len(rows),
            "projected_points_adjustment": round(adjustment, 1),
            "evidence": "LOW",
        }
    return output


def empty_manager_history() -> dict[str, Any]:
    return {"schema_version": HISTORY_SCHEMA_VERSION, "updated_at": None, "managers": {}}


def _transaction_player(player_id: Any, players_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    player = players_by_id.get(str(player_id)) or {}
    return {
        "player_id": player_id,
        "player": player.get("player"),
        "position": player.get("position"),
        "roster_score": (player.get("intelligence") or {}).get("roster_score"),
    }


def update_manager_history(
    history: dict[str, Any] | None,
    league_details: dict[str, Any],
    ownership: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    *,
    captured_at: str | None,
    gameweek: int | None,
    lineup_decisions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state = deepcopy(history) if isinstance(history, dict) else empty_manager_history()
    if state.get("schema_version") != HISTORY_SCHEMA_VERSION:
        state = empty_manager_history()
    managers = state.setdefault("managers", {})
    alias_to_key: dict[str, str] = {}
    for entry in _entries(league_details):
        key = _entry_key(entry)
        if not key:
            continue
        alias_to_key.update({alias: key for alias in _entry_aliases(entry)})
        manager = managers.setdefault(key, {"transactions": [], "lineups": {}})
        manager["team_name"] = entry.get("entry_name") or entry.get("short_name") or "League opponent"
        manager.setdefault("transactions", [])
        manager.setdefault("lineups", {})

    players_by_id = {str(row.get("player_id")): row for row in ownership if row.get("player_id") is not None}
    grouped: dict[str, dict[str, list[Any]]] = {}

    def add_event(owner: Any, direction: str, player_id: Any) -> None:
        key = alias_to_key.get(str(owner)) if owner is not None else None
        if key:
            grouped.setdefault(key, {"adds": [], "drops": []})[direction].append(player_id)

    for change in changes:
        if not isinstance(change, dict):
            continue
        kind = change.get("type")
        if kind in {"add", "ownership_change"}:
            add_event(change.get("to_owner"), "adds", change.get("player_id"))
        if kind in {"drop", "ownership_change"}:
            add_event(change.get("from_owner"), "drops", change.get("player_id"))

    for key, activity in grouped.items():
        adds = [_transaction_player(player_id, players_by_id) for player_id in activity["adds"]]
        drops = [_transaction_player(player_id, players_by_id) for player_id in activity["drops"]]
        fingerprint = f"{gameweek}:{','.join(sorted(str(row['player_id']) for row in adds))}:{','.join(sorted(str(row['player_id']) for row in drops))}"
        transactions = managers[key].setdefault("transactions", [])
        if any(row.get("fingerprint") == fingerprint for row in transactions):
            continue
        transactions.append({
            "fingerprint": fingerprint,
            "captured_at": captured_at,
            "gameweek": gameweek,
            "adds": adds,
            "drops": drops,
            "value_delta": round(
                sum(_number(row.get("roster_score")) for row in adds)
                - sum(_number(row.get("roster_score")) for row in drops),
                1,
            ),
        })

    for alias, decision in (lineup_decisions or {}).items():
        key = alias_to_key.get(str(alias), str(alias) if str(alias) in managers else None)
        if key and decision.get("gameweek") is not None:
            managers[key].setdefault("lineups", {})[str(decision["gameweek"])] = decision

    state["updated_at"] = captured_at or datetime.now(timezone.utc).isoformat()
    return state


def lineup_decision(lineup: dict[str, Any] | None) -> dict[str, Any] | None:
    if not lineup or not lineup.get("is_exact"):
        return None
    starters = [row for row in lineup.get("starters") or [] if isinstance(row, dict)]
    bench = [row for row in lineup.get("bench") or [] if isinstance(row, dict)]
    squad = starters + bench
    if len(starters) != 11 or len(squad) < 15:
        return None
    by_position = {
        position: sorted(
            [row for row in squad if row.get("position") == position],
            key=lambda row: _number(row.get("event_points")),
            reverse=True,
        )
        for position in ("GKP", "DEF", "MID", "FWD")
    }
    possible = []
    for defenders in range(3, 6):
        for midfielders in range(2, 6):
            forwards = 10 - defenders - midfielders
            if forwards < 1 or forwards > 3:
                continue
            counts = {"GKP": 1, "DEF": defenders, "MID": midfielders, "FWD": forwards}
            if any(len(by_position[position]) < count for position, count in counts.items()):
                continue
            possible.append(sum(
                sum(_number(row.get("event_points")) for row in by_position[position][:count])
                for position, count in counts.items()
            ))
    if not possible:
        return None
    submitted = sum(_number(row.get("event_points")) for row in starters)
    best = max(possible)
    efficiency = 100.0 if best <= 0 else _clamp(submitted / best * 100.0, 0.0, 100.0)
    return {
        "gameweek": lineup.get("gameweek"),
        "submitted_points": round(submitted, 1),
        "best_possible_points": round(best, 1),
        "points_left_on_bench": round(max(0.0, best - submitted), 1),
        "efficiency": round(efficiency, 1),
        "starter_ids": [row.get("player_id") for row in starters],
    }


def _management_profile(manager: dict[str, Any]) -> dict[str, Any]:
    transactions = [row for row in manager.get("transactions") or [] if isinstance(row, dict)]
    lineups = [row for row in (manager.get("lineups") or {}).values() if isinstance(row, dict)]
    deltas = [_number(row.get("value_delta")) for row in transactions]
    efficiencies = [_number(row.get("efficiency")) for row in lineups if row.get("efficiency") is not None]
    transfer_score = _clamp(50.0 + _mean(deltas) * 2.0, 25.0, 75.0) if deltas else 50.0
    lineup_score = _clamp(50.0 + (_mean(efficiencies) - 85.0) * 1.5, 25.0, 75.0) if efficiencies else 50.0
    transfer_weight = min(1.0, len(transactions) / 5.0)
    lineup_weight = min(1.0, len(efficiencies) / 4.0)
    adjustment = (
        (transfer_score - 50.0) / 25.0 * 0.8 * transfer_weight
        + (lineup_score - 50.0) / 25.0 * 0.8 * lineup_weight
    )
    samples = len(transactions) + len(efficiencies)
    evidence = "HIGH" if len(transactions) >= 5 and len(efficiencies) >= 3 else "MEDIUM" if samples >= 3 else "LOW"
    return {
        "transaction_windows": len(transactions),
        "adds": sum(len(row.get("adds") or []) for row in transactions),
        "drops": sum(len(row.get("drops") or []) for row in transactions),
        "average_transfer_value": round(_mean(deltas), 1) if deltas else None,
        "lineup_gameweeks": len(efficiencies),
        "average_lineup_efficiency": round(_mean(efficiencies), 1) if efficiencies else None,
        "transfer_score": round(transfer_score, 1),
        "lineup_score": round(lineup_score, 1),
        "projected_points_adjustment": round(adjustment, 1),
        "evidence": evidence,
    }


def build_manager_profiles(
    league_details: dict[str, Any],
    ownership: list[dict[str, Any]],
    draft: dict[str, Any] | None,
    history: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    draft_by_code = draft_profiles(draft, ownership)
    draft_teams = [row for row in (draft or {}).get("teams") or [] if isinstance(row, dict)]
    draft_by_name = {_normalise(row.get("team_name")): row for row in draft_teams}
    draft_codes = {str(row.get("draft_code")): row for row in draft_teams}
    history_managers = (history or {}).get("managers") or {}
    profiles: dict[str, dict[str, Any]] = {}
    for entry in _entries(league_details):
        key = _entry_key(entry)
        if not key:
            continue
        team_name = entry.get("entry_name") or entry.get("short_name") or "League opponent"
        draft_team = draft_by_name.get(_normalise(team_name)) or draft_codes.get(_manager_initials(entry))
        draft_profile = draft_by_code.get(str((draft_team or {}).get("draft_code")))
        management = _management_profile(history_managers.get(key) or {})
        draft_adjustment = _number((draft_profile or {}).get("projected_points_adjustment"))
        adjustment = _clamp(draft_adjustment + _number(management.get("projected_points_adjustment")), -2.0, 2.0)
        score = _clamp(50.0 + adjustment * 12.5, 25.0, 75.0)
        level = "HIGH" if score >= 57.0 else "LOW" if score <= 43.0 else "MEDIUM"
        profile = {
            "model": PROFILE_MODEL,
            "team_name": team_name,
            "draft": draft_profile,
            "management": management,
            "decision_threat": {
                "level": level,
                "score": round(score, 1),
                "projected_points_adjustment": round(adjustment, 1),
                "evidence": management.get("evidence") or "LOW",
                "basis": "Draft quality is a small early-season prior; observed transfer and lineup decisions gradually replace it.",
            },
        }
        for alias in _entry_aliases(entry):
            profiles[alias] = profile
    return profiles
