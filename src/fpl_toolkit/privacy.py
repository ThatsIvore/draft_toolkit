from __future__ import annotations

from copy import deepcopy
from typing import Any

OWNER_FIELDS = {"owner_raw", "owner_entry_id", "owner_name"}


def _strip_owner_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in OWNER_FIELDS}


def sanitize_public_report(report: dict[str, Any]) -> dict[str, Any]:
    public = deepcopy(report)
    public.pop("manager", None)
    public.pop("entry_id", None)
    public.pop("snapshot", None)
    for key in ("my_squad", "available_players", "injury_watch"):
        rows = public.get(key, [])
        if isinstance(rows, list):
            public[key] = [_strip_owner_fields(row) for row in rows if isinstance(row, dict)]
    lineup = public.get("lineup")
    if isinstance(lineup, dict):
        for key in ("starters", "bench", "squad"):
            rows = lineup.get(key, [])
            if isinstance(rows, list):
                lineup[key] = [_strip_owner_fields(row) for row in rows if isinstance(row, dict)]
    activity = []
    for change in public.get("league_activity", []) or []:
        if not isinstance(change, dict):
            continue
        item = dict(change)
        for key in ("from_owner", "to_owner", "from_owner_name", "to_owner_name"):
            item.pop(key, None)
        activity.append(item)
    public["league_activity"] = activity
    return public
