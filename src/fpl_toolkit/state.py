from __future__ import annotations

from typing import Any

from .normalize import manager_lookup

STATE_FIELDS = ("player_id", "player", "club", "team_id", "position", "status", "owner_raw", "owner_entry_id")


def compact_ownership_state(ownership: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: row.get(key) for key in STATE_FIELDS} for row in ownership]


def decorate_change_manager_names(changes: list[dict[str, Any]], league_details: dict[str, Any]) -> list[dict[str, Any]]:
    managers = manager_lookup(league_details)
    for change in changes:
        if not change.get("from_owner_name") and change.get("from_owner") is not None:
            manager = managers.get(str(change["from_owner"]), {})
            change["from_owner_name"] = manager.get("entry_name") or manager.get("player_name") or manager.get("name")
        if not change.get("to_owner_name") and change.get("to_owner") is not None:
            manager = managers.get(str(change["to_owner"]), {})
            change["to_owner_name"] = manager.get("entry_name") or manager.get("player_name") or manager.get("name")
    return changes
