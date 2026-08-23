from __future__ import annotations

from collections import Counter
from typing import Any

from .optimizer import recommend_lineup


OUTLOOK_MODEL = "standard-fpl-squad-outlook-v0.1"
RISK_AVAILABILITY_THRESHOLD = 75.0
RISK_MINUTES_THRESHOLD = 60.0


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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


def _compact_player(player: dict[str, Any]) -> dict[str, Any]:
    selection = player.get("selection") or {}
    row = {
        "player_id": player.get("player_id"),
        "player": player.get("player"),
        "club": player.get("club"),
        "position": player.get("position"),
        "start_score": selection.get("start_score"),
        "availability": selection.get("availability"),
        "expected_minutes": selection.get("expected_minutes"),
        "fixture_score": selection.get("next_fixture"),
    }
    if selection.get("bench_order") is not None:
        row["bench_order"] = selection.get("bench_order")
    return row


def _risk(player: dict[str, Any]) -> dict[str, Any] | None:
    selection = player.get("selection") or {}
    availability = _number(selection.get("availability"), 100.0)
    expected_minutes = _number(selection.get("expected_minutes"), 90.0)
    reasons = []
    if availability < RISK_AVAILABILITY_THRESHOLD:
        reasons.append("availability")
    if expected_minutes < RISK_MINUTES_THRESHOLD:
        reasons.append("minutes")
    if not reasons:
        return None
    return {
        **_compact_player(player),
        "risk_reasons": reasons,
    }


def build_squad_outlook(
    squad: list[dict[str, Any]],
    planning_gameweeks: list[int],
) -> dict[str, Any]:
    """Summarize legal lineups, captaincy and squad pressure across the horizon."""
    rounds: list[dict[str, Any]] = []
    starter_counts: Counter[int] = Counter()
    player_names: dict[int, str | None] = {}
    position_by_id: dict[int, str | None] = {}

    for gameweek in planning_gameweeks:
        lineup = recommend_lineup(squad, int(gameweek))
        captaincy = recommend_captaincy(lineup)
        starters = [row for row in lineup.get("starters") or [] if isinstance(row, dict)]
        bench = [row for row in lineup.get("bench") or [] if isinstance(row, dict)]
        reserve = lineup.get("reserve_goalkeeper")
        risks = [risk for player in starters if (risk := _risk(player)) is not None]
        playable_bench = [
            player
            for player in bench
            if _number((player.get("selection") or {}).get("availability"), 100.0)
            >= RISK_AVAILABILITY_THRESHOLD
            and _number((player.get("selection") or {}).get("expected_minutes"), 90.0)
            >= RISK_MINUTES_THRESHOLD
        ]
        if not lineup.get("is_valid"):
            pressure = "HIGH"
        elif len(risks) >= 2 and not playable_bench:
            pressure = "HIGH"
        elif risks:
            pressure = "MEDIUM"
        else:
            pressure = "LOW"

        for player in starters:
            player_id = int(player.get("player_id") or 0)
            if player_id <= 0:
                continue
            starter_counts[player_id] += 1
            player_names[player_id] = player.get("player")
            position_by_id[player_id] = player.get("position")
        for player in bench + ([reserve] if isinstance(reserve, dict) else []):
            player_id = int(player.get("player_id") or 0)
            if player_id <= 0:
                continue
            player_names[player_id] = player.get("player")
            position_by_id[player_id] = player.get("position")

        rounds.append({
            "gameweek": int(gameweek),
            "is_valid": bool(lineup.get("is_valid")),
            "formation": lineup.get("formation"),
            "total_start_score": lineup.get("total_start_score"),
            "average_start_score": lineup.get("average_start_score"),
            "captain": captaincy.get("captain"),
            "vice_captain": captaincy.get("vice_captain"),
            "captaincy_shortlist": captaincy.get("shortlist") or [],
            "starters": [_compact_player(player) for player in starters],
            "bench": [_compact_player(player) for player in bench],
            "reserve_goalkeeper": _compact_player(reserve) if isinstance(reserve, dict) else None,
            "availability_risks": risks,
            "playable_outfield_bench_count": len(playable_bench),
            "selection_pressure": pressure,
            "close_calls": lineup.get("close_calls") or [],
        })

    horizon_count = len(rounds)
    player_rows = [
        {
            "player_id": player_id,
            "player": player_names.get(player_id),
            "position": position_by_id.get(player_id),
            "starts": starter_counts.get(player_id, 0),
            "rounds": horizon_count,
        }
        for player_id in sorted(player_names)
    ]
    core = [row for row in player_rows if horizon_count > 0 and row["starts"] == horizon_count]
    rotation = [row for row in player_rows if 0 < row["starts"] < horizon_count]
    always_benched = [row for row in player_rows if row["starts"] == 0]
    return {
        "model": OUTLOOK_MODEL,
        "is_valid": bool(rounds) and all(row["is_valid"] for row in rounds),
        "gameweeks": [int(gameweek) for gameweek in planning_gameweeks],
        "rounds": rounds,
        "core_starters": core,
        "rotation_players": rotation,
        "always_benched": always_benched,
        "note": (
            "Start Score and Captain Score are transparent selection heuristics, not projected FPL points. "
            "This outlook submits no lineup or captaincy action."
        ),
    }
