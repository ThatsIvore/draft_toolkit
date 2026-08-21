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
        start = float(intel.get("start_probability") or 0.0)
        minutes = float(intel.get("expected_minutes") or 0.0)
        fixture = float(intel.get("fixture_score") or 0.0)
        availability = float(intel.get("availability_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    usage = 0.55 * start + 0.45 * (minutes / 90.0 * 100.0)
    return 0.45 * usage + 0.35 * fixture + 0.20 * availability


def attach_replacement_analysis(
    available_players: list[dict[str, Any]],
    my_squad: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compare each free agent to the weakest same-position roster alternative.

    Draft roster construction makes same-position comparison the safest first-pass
    replacement model. Deltas are transparent toolkit scores, not projected FPL points.
    """
    by_position: dict[str, list[dict[str, Any]]] = {}
    for player in my_squad:
        by_position.setdefault(str(player.get("position") or ""), []).append(player)

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
            combined = 0.45 * roster_delta + 0.35 * immediate_delta + 0.20 * future_delta
            comparisons.append((combined, roster_delta, immediate_delta, future_delta, owned))

        combined, roster_delta, immediate_delta, future_delta, owned = max(comparisons, key=lambda item: item[0])
        if combined >= 8 and immediate_delta >= 0:
            action = "SWAP NOW"
        elif combined >= 6 and future_delta > immediate_delta:
            action = "STASH SWAP"
        elif combined >= 3:
            action = "CONSIDER"
        else:
            action = "KEEP ROSTER"

        row["replacement"] = {
            "model": "v0.4",
            "drop_player_id": owned.get("player_id"),
            "drop_player": owned.get("player"),
            "drop_club": owned.get("club"),
            "position": row.get("position"),
            "roster_delta": round(roster_delta, 1),
            "immediate_delta": round(immediate_delta, 1),
            "future_delta": round(future_delta, 1),
            "combined_delta": round(combined, 1),
            "action": action,
        }
        output.append(row)
    return output
