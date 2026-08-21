from __future__ import annotations

from typing import Any


BASELINE_FIELDS = (
    "player_id",
    "player",
    "club",
    "position",
    "total_points",
    "minutes",
    "starts",
    "goals_scored",
    "assists",
    "expected_goal_involvements",
    "points_per_game",
)


def capture_performance_baseline(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Persist the preseason/previous-season evidence before live-season fields reset."""
    return [{key: player.get(key) for key in BASELINE_FIELDS} for player in players]


def baseline_lookup(rows: list[dict[str, Any]] | None) -> dict[int, dict[str, Any]]:
    lookup: dict[int, dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict) or row.get("player_id") is None:
            continue
        try:
            lookup[int(row["player_id"])] = row
        except (TypeError, ValueError):
            continue
    return lookup
