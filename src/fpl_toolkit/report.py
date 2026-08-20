from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def find_user_manager(league_details: dict[str, Any], entry_id: str) -> dict[str, Any] | None:
    entries = league_details.get("league_entries") or league_details.get("entries") or []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        candidates = {str(entry.get(k)) for k in ("entry_id", "entry") if entry.get(k) is not None}
        if entry_id in candidates:
            return entry
    return None


def current_gameweek(bootstrap: dict[str, Any], planning_gameweeks: list[int] | None = None) -> int | None:
    events = bootstrap.get("events", [])
    for event in events:
        if isinstance(event, dict) and event.get("is_current"):
            return int(event["id"])
    for event in events:
        if isinstance(event, dict) and event.get("is_next"):
            next_id = int(event["id"])
            return 0 if next_id == 1 else next_id - 1
    if planning_gameweeks and planning_gameweeks[0] == 1:
        return 0
    return None


def build_report(entry_id: str, league_id: str, league_details: dict[str, Any], bootstrap: dict[str, Any], ownership: list[dict[str, Any]], changes: list[dict[str, Any]], horizon: int, planning_gameweeks: list[int] | None = None) -> dict[str, Any]:
    manager = find_user_manager(league_details, entry_id)
    own_ids = {entry_id}
    if manager:
        for key in ("id", "entry_id", "entry"):
            if manager.get(key) is not None:
                own_ids.add(str(manager[key]))
    my_squad = [row for row in ownership if (row.get("owner_entry_id") is not None and str(row.get("owner_entry_id")) in own_ids) or (row.get("owner_raw") is not None and str(row.get("owner_raw")) in own_ids)]
    available = [row for row in ownership if str(row.get("status", "")).lower() == "a"]
    injured_or_doubtful = [row for row in ownership if row.get("chance_next_round") is not None and int(row.get("chance_next_round") or 0) < 100]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entry_id": entry_id,
        "league_id": league_id,
        "league_name": (league_details.get("league") or {}).get("name") if isinstance(league_details.get("league"), dict) else league_details.get("name"),
        "manager": manager,
        "current_gameweek": current_gameweek(bootstrap, planning_gameweeks),
        "planning_horizon": horizon,
        "summary": {
            "my_squad_count": len(my_squad),
            "available_count": len(available),
            "tracked_players": len(ownership),
            "ownership_changes": len(changes),
            "injured_or_doubtful_count": len(injured_or_doubtful),
        },
        "my_squad": my_squad,
        "available_players": available,
        "league_activity": changes,
        "injury_watch": injured_or_doubtful,
        "notes": ["This POC proves roster/availability collection and state diffing.", "Projection and stash scoring are deferred until the live payload is validated."],
    }
