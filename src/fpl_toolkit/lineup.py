from __future__ import annotations

from typing import Any


def _pick_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("picks", "squad", "elements", "entry_picks"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _event_points_total(payload: Any) -> float | None:
    if not isinstance(payload, dict):
        return None
    history = payload.get("entry_history")
    candidates = [history.get("points")] if isinstance(history, dict) else []
    candidates.extend([payload.get("event_points"), payload.get("points")])
    for value in candidates:
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def normalize_lineup(payload: Any, squad: list[dict[str, Any]], gameweek: int) -> dict[str, Any] | None:
    rows = _pick_rows(payload)
    if not rows:
        return None
    by_id = {int(row["player_id"]): row for row in squad if row.get("player_id") is not None}
    picks: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        raw_element = row.get("element", row.get("element_id", row.get("player_id", row.get("id"))))
        try:
            player_id = int(raw_element)
        except (TypeError, ValueError):
            continue
        raw_position = row.get("position", row.get("pick_position", row.get("order", index)))
        try:
            position = int(raw_position)
        except (TypeError, ValueError):
            position = index
        player = by_id.get(player_id)
        if not player:
            continue
        enriched = dict(player)
        enriched["pick_position"] = position
        enriched["is_starter"] = position <= 11
        picks.append(enriched)
    if len(picks) < 11:
        return None
    picks.sort(key=lambda row: int(row.get("pick_position", 99)))
    return {
        "gameweek": int(gameweek),
        "source": "draft_entry_event",
        "is_exact": True,
        "event_points_total": _event_points_total(payload),
        "starters": [row for row in picks if row.get("is_starter")],
        "bench": [row for row in picks if not row.get("is_starter")],
    }


def fallback_lineup(squad: list[dict[str, Any]], gameweek: int) -> dict[str, Any]:
    return {
        "gameweek": int(gameweek),
        "source": "ownership_fallback",
        "is_exact": False,
        "starters": [],
        "bench": [],
        "squad": list(squad),
    }
