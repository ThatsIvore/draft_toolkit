from __future__ import annotations

from copy import deepcopy
from typing import Any

OWNER_FIELDS = {"owner_raw", "owner_entry_id", "owner_name"}
H2H_IDENTITY_FIELDS = {
    "entry_id",
    "league_entry_id",
    "entry_name",
    "short_name",
    "player_first_name",
    "player_last_name",
    "first_name",
    "last_name",
}


def _strip_owner_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in OWNER_FIELDS}


def _sanitize_lineup(lineup: Any) -> None:
    if not isinstance(lineup, dict):
        return
    for key in ("starters", "bench", "squad"):
        rows = lineup.get(key, [])
        if isinstance(rows, list):
            lineup[key] = [_strip_owner_fields(row) for row in rows if isinstance(row, dict)]
    reserve = lineup.get("reserve_goalkeeper")
    if isinstance(reserve, dict):
        lineup["reserve_goalkeeper"] = _strip_owner_fields(reserve)


def sanitize_public_report(report: dict[str, Any]) -> dict[str, Any]:
    public = deepcopy(report)
    public.pop("manager", None)
    public.pop("entry_id", None)
    public.pop("snapshot", None)
    for key in ("my_squad", "available_players", "injury_watch"):
        rows = public.get(key, [])
        if isinstance(rows, list):
            public[key] = [_strip_owner_fields(row) for row in rows if isinstance(row, dict)]
    for lineup_key in ("lineup", "recommended_lineup"):
        _sanitize_lineup(public.get(lineup_key))
    availability = public.get("injury_stash")
    if isinstance(availability, dict):
        for key in (
            "squad_health",
            "stash_candidates",
            "return_calendar",
            "transfer_watch",
            "early_pickups",
        ):
            rows = availability.get(key, [])
            if isinstance(rows, list):
                availability[key] = [
                    _strip_owner_fields(row)
                    for row in rows
                    if isinstance(row, dict)
                ]
    activity = []
    for change in public.get("league_activity", []) or []:
        if not isinstance(change, dict):
            continue
        item = dict(change)
        for key in ("from_owner", "to_owner", "from_owner_name", "to_owner_name"):
            item.pop(key, None)
        activity.append(item)
    public["league_activity"] = activity

    h2h = public.get("h2h_matchup")
    if isinstance(h2h, dict):
        opponent = h2h.get("opponent")
        if isinstance(opponent, dict):
            for key in H2H_IDENTITY_FIELDS:
                opponent.pop(key, None)
            opponent["display_name"] = str(opponent.get("display_name") or "League opponent")
        opponent_squad = h2h.get("opponent_squad", [])
        if isinstance(opponent_squad, list):
            h2h["opponent_squad"] = [
                _strip_owner_fields(row) for row in opponent_squad if isinstance(row, dict)
            ]
        _sanitize_lineup(h2h.get("my_lineup"))
        _sanitize_lineup(h2h.get("opponent_lineup"))
    outlook = public.get("h2h_outlook")
    if isinstance(outlook, dict):
        for card in outlook.get("gameweeks") or []:
            if not isinstance(card, dict):
                continue
            opponent = card.get("opponent")
            if not isinstance(opponent, dict):
                continue
            for key in H2H_IDENTITY_FIELDS:
                opponent.pop(key, None)
            opponent["display_name"] = str(opponent.get("display_name") or "League opponent")
    return public
