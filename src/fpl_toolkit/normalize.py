from __future__ import annotations

from typing import Any, Iterable


class LeagueDiscoveryError(RuntimeError):
    pass


def _numeric(value: Any) -> str | None:
    if isinstance(value, int) and value > 0:
        return str(value)
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return value
    return None


def discover_league_ids(entry_payload: Any) -> list[str]:
    found: list[str] = []

    def add(value: Any) -> None:
        numeric = _numeric(value)
        if numeric and numeric not in found:
            found.append(numeric)

    def walk(node: Any, parent_key: str | None = None) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = key.lower()
                if lowered in {"league_id", "leagueid"}:
                    add(value)
                elif lowered == "league" and not isinstance(value, (dict, list)):
                    add(value)
                elif parent_key in {"league", "leagues"} and lowered == "id":
                    add(value)
                walk(value, lowered)
        elif isinstance(node, list):
            for item in node:
                walk(item, parent_key)

    walk(entry_payload)
    return found


def choose_league_id(entry_payload: Any, explicit_league_id: str | None) -> str:
    if explicit_league_id:
        return explicit_league_id
    ids = discover_league_ids(entry_payload)
    if len(ids) == 1:
        return ids[0]
    if not ids:
        raise LeagueDiscoveryError(
            "The public Draft entry payload did not expose a league ID. Set "
            "FPL_DRAFT_LEAGUE_ID once from /api/league/<ID>/details in the "
            "Draft site's browser Network tab. No login credentials need to be stored."
        )
    raise LeagueDiscoveryError(
        "Multiple Draft leagues were found in the entry payload. Set "
        f"FPL_DRAFT_LEAGUE_ID explicitly. Candidates: {', '.join(ids)}"
    )


def list_payload(payload: Any, preferred_keys: Iterable[str]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in preferred_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def manager_lookup(league_details: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = list_payload(league_details, ("league_entries", "entries"))
    lookup: dict[str, dict[str, Any]] = {}
    for entry in entries:
        for key in ("id", "entry_id", "entry"):
            value = entry.get(key)
            if value is not None:
                lookup[str(value)] = entry
    return lookup


def player_lookup(bootstrap: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(p["id"]): p for p in bootstrap.get("elements", []) if isinstance(p, dict) and p.get("id") is not None}


def team_lookup(bootstrap: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(t["id"]): t for t in bootstrap.get("teams", []) if isinstance(t, dict) and t.get("id") is not None}


def position_lookup(bootstrap: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(p["id"]): p for p in bootstrap.get("element_types", []) if isinstance(p, dict) and p.get("id") is not None}


def normalize_ownership(element_status_payload: Any, league_details: dict[str, Any], bootstrap: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list_payload(element_status_payload, ("element_status", "elements", "results"))
    managers = manager_lookup(league_details)
    players = player_lookup(bootstrap)
    teams = team_lookup(bootstrap)
    positions = position_lookup(bootstrap)
    normalized: list[dict[str, Any]] = []
    for row in rows:
        raw_player_id = row.get("element", row.get("element_id", row.get("id")))
        try:
            player_id = int(raw_player_id)
        except (TypeError, ValueError):
            continue
        player = players.get(player_id, {})
        owner_raw = row.get("owner")
        manager = managers.get(str(owner_raw), {}) if owner_raw is not None else {}
        team = teams.get(int(player.get("team", 0) or 0), {})
        position = positions.get(int(player.get("element_type", 0) or 0), {})
        normalized.append({
            "player_id": player_id,
            "player": player.get("web_name") or player.get("second_name") or f"Player {player_id}",
            "club": team.get("short_name") or team.get("name"),
            "team_id": player.get("team"),
            "team_code": team.get("code"),
            "position": position.get("singular_name_short") or position.get("singular_name"),
            "status": row.get("status"),
            "owner_raw": owner_raw,
            "owner_entry_id": manager.get("entry_id") or manager.get("entry"),
            "owner_name": manager.get("entry_name") or manager.get("player_name") or manager.get("name"),
            "chance_next_round": player.get("chance_of_playing_next_round"),
            "news": player.get("news") or "",
            "news_added": player.get("news_added"),
            "total_points": player.get("total_points"),
            "minutes": player.get("minutes"),
            "starts": player.get("starts"),
            "goals_scored": player.get("goals_scored"),
            "assists": player.get("assists"),
            "clean_sheets": player.get("clean_sheets"),
            "bonus": player.get("bonus"),
            "expected_goal_involvements": player.get("expected_goal_involvements"),
            "form": player.get("form"),
            "points_per_game": player.get("points_per_game"),
            "expected_points_next": player.get("ep_next"),
        })
    return normalized
