from __future__ import annotations

from typing import Any

from .normalize import team_lookup


def planning_gameweeks(bootstrap: dict[str, Any], horizon: int) -> list[int]:
    events = [e for e in bootstrap.get("events", []) if isinstance(e, dict) and e.get("id") is not None]
    events.sort(key=lambda e: int(e["id"]))
    if not events:
        return []
    start_index = None
    for i, event in enumerate(events):
        if event.get("is_current"):
            start_index = i
            break
    if start_index is None:
        for i, event in enumerate(events):
            if event.get("is_next"):
                start_index = i
                break
    if start_index is None:
        for i, event in enumerate(events):
            if event.get("finished") is not True:
                start_index = i
                break
    if start_index is None:
        return []
    return [int(e["id"]) for e in events[start_index:start_index + horizon]]


def build_team_fixture_matrix(fixtures: list[dict[str, Any]], bootstrap: dict[str, Any], horizon: int) -> dict[str, list[dict[str, Any]]]:
    gws = planning_gameweeks(bootstrap, horizon)
    gw_set = set(gws)
    teams = team_lookup(bootstrap)
    matrix: dict[str, list[dict[str, Any]]] = {str(team_id): [] for team_id in teams}
    by_team_gw: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for fixture in fixtures:
        gw, home, away = fixture.get("event"), fixture.get("team_h"), fixture.get("team_a")
        if gw not in gw_set or home is None or away is None:
            continue
        home_id, away_id, gw_id = int(home), int(away), int(gw)
        common = {"kickoff_time": fixture.get("kickoff_time"), "started": fixture.get("started"), "finished": fixture.get("finished")}
        home_opp, away_opp = teams.get(away_id, {}), teams.get(home_id, {})
        by_team_gw.setdefault((home_id, gw_id), []).append({"opponent_id": away_id, "opponent": home_opp.get("short_name") or home_opp.get("name") or str(away_id), "venue": "H", **common})
        by_team_gw.setdefault((away_id, gw_id), []).append({"opponent_id": home_id, "opponent": away_opp.get("short_name") or away_opp.get("name") or str(home_id), "venue": "A", **common})
    for team_id in teams:
        matrix[str(team_id)] = [{"gameweek": gw, "matches": by_team_gw.get((team_id, gw), [])} for gw in gws]
    return matrix


def attach_fixture_matrix(ownership: list[dict[str, Any]], matrix: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    output = []
    for row in ownership:
        enriched = dict(row)
        enriched["fixtures"] = matrix.get(str(row.get("team_id")), [])
        output.append(enriched)
    return output
