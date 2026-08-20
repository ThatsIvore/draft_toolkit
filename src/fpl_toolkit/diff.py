from __future__ import annotations

from typing import Any


def _owner(row: dict[str, Any]) -> str | None:
    owner = row.get("owner_entry_id")
    if owner is None:
        owner = row.get("owner_raw")
    return str(owner) if owner is not None else None


def diff_ownership(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prev = {int(row["player_id"]): row for row in previous}
    curr = {int(row["player_id"]): row for row in current}
    events: list[dict[str, Any]] = []
    for player_id in sorted(set(prev) | set(curr)):
        before, after = prev.get(player_id), curr.get(player_id)
        if not before or not after:
            continue
        old_owner, new_owner = _owner(before), _owner(after)
        old_status, new_status = before.get("status"), after.get("status")
        if old_owner == new_owner and old_status == new_status:
            continue
        if old_owner and not new_owner:
            kind = "drop"
        elif not old_owner and new_owner:
            kind = "add"
        elif old_owner and new_owner and old_owner != new_owner:
            kind = "ownership_change"
        else:
            kind = "status_change"
        events.append({
            "type": kind,
            "player_id": player_id,
            "player": after.get("player") or before.get("player"),
            "club": after.get("club") or before.get("club"),
            "from_owner": old_owner,
            "from_owner_name": before.get("owner_name"),
            "to_owner": new_owner,
            "to_owner_name": after.get("owner_name"),
            "from_status": old_status,
            "to_status": new_status,
        })
    return events
