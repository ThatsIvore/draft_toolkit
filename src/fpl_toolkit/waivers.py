from __future__ import annotations

from typing import Any


def _score(player: dict[str, Any], key: str) -> float:
    try:
        return float((player.get("intelligence") or {}).get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _immediate_value(player: dict[str, Any]) -> float:
    intel = player.get("intelligence") or {}
    try:
        usage = float(intel.get("usage_score") or 0.0)
        fixture = float(intel.get("fixture_score") or 0.0)
        availability = float(intel.get("availability_score") or 0.0)
        floor = float(intel.get("floor_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return 0.35 * usage + 0.25 * fixture + 0.15 * availability + 0.25 * floor


def _confidence_label(available: dict[str, Any], owned: dict[str, Any], combined: float) -> str:
    sample = min(_score(available, "sample_confidence"), _score(owned, "sample_confidence"))
    if sample >= 70 and abs(combined) >= 10:
        return "HIGH"
    if sample >= 40 and abs(combined) >= 5:
        return "MEDIUM"
    return "LOW"


def _is_true_stash_candidate(player: dict[str, Any]) -> bool:
    intel = player.get("intelligence") or {}
    availability = _score(player, "availability_score")
    return_signal = str(intel.get("injury_return_signal") or "fit")
    return availability < 100 or return_signal in {"out", "return-watch", "near-return"}


def attach_replacement_analysis(
    available_players: list[dict[str, Any]],
    my_squad: list[dict[str, Any]],
    current_gameweek: int | None = None,
) -> list[dict[str, Any]]:
    """Compare each free agent with the best same-position roster replacement.

    v0.5.1 reserves STASH SWAP for players with a real short-term availability
    cost. Fit players with future-led value remain CONSIDER candidates instead.
    """
    by_position: dict[str, list[dict[str, Any]]] = {}
    for player in my_squad:
        by_position.setdefault(str(player.get("position") or ""), []).append(player)

    preseason = current_gameweek in (None, 0)
    output: list[dict[str, Any]] = []
    for available in available_players:
        row = dict(available)
        candidates = by_position.get(str(row.get("position") or ""), [])
        if not candidates:
            row["replacement"] = None
            output.append(row)
            continue

        comparisons = []
        for owned in candidates:
            roster_delta = _score(row, "roster_score") - _score(owned, "roster_score")
            future_delta = _score(row, "stash_score") - _score(owned, "stash_score")
            immediate_delta = _immediate_value(row) - _immediate_value(owned)
            floor_delta = _score(row, "floor_score") - _score(owned, "floor_score")
            upside_delta = _score(row, "upside_score") - _score(owned, "upside_score")
            combined = 0.32 * roster_delta + 0.25 * immediate_delta + 0.18 * future_delta + 0.15 * floor_delta + 0.10 * upside_delta
            comparisons.append((combined, roster_delta, immediate_delta, future_delta, floor_delta, upside_delta, owned))

        combined, roster_delta, immediate_delta, future_delta, floor_delta, upside_delta, owned = max(comparisons, key=lambda item: item[0])
        confidence = _confidence_label(row, owned, combined)
        true_stash = _is_true_stash_candidate(row)

        swap_threshold = 16.0 if preseason else 10.0
        consider_threshold = 5.0 if preseason else 3.0
        if combined >= swap_threshold and immediate_delta >= 2 and floor_delta >= 0 and confidence != "LOW":
            action = "SWAP NOW"
        elif true_stash and combined >= (10.0 if preseason else 7.0) and future_delta > immediate_delta and upside_delta > 0 and confidence != "LOW":
            action = "STASH SWAP"
        elif combined >= consider_threshold:
            action = "CONSIDER"
        else:
            action = "KEEP ROSTER"

        row["replacement"] = {
            "model": "v0.5.1",
            "drop_player_id": owned.get("player_id"),
            "drop_player": owned.get("player"),
            "drop_club": owned.get("club"),
            "position": row.get("position"),
            "roster_delta": round(roster_delta, 1),
            "immediate_delta": round(immediate_delta, 1),
            "future_delta": round(future_delta, 1),
            "floor_delta": round(floor_delta, 1),
            "upside_delta": round(upside_delta, 1),
            "combined_delta": round(combined, 1),
            "confidence": confidence,
            "preseason_guardrail": preseason,
            "true_stash_candidate": true_stash,
            "action": action,
        }
        output.append(row)
    return output
