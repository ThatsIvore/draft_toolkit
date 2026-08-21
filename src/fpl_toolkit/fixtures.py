from __future__ import annotations

from typing import Any

from .normalize import team_lookup


def bootstrap_events(bootstrap: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize the event shapes exposed by the FPL and FPL Draft APIs."""
    raw_events = bootstrap.get("events", [])
    if isinstance(raw_events, list):
        return [dict(event) for event in raw_events if isinstance(event, dict)]
    if not isinstance(raw_events, dict):
        return []

    rows = raw_events.get("data") or raw_events.get("events") or []
    if not isinstance(rows, list):
        return []
    current_id = raw_events.get("current")
    next_id = raw_events.get("next")
    events = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        event = dict(row)
        if current_id is not None:
            event["is_current"] = str(event.get("id")) == str(current_id)
        if next_id is not None:
            event["is_next"] = str(event.get("id")) == str(next_id)
        events.append(event)
    return events


def planning_gameweeks(bootstrap: dict[str, Any], horizon: int, fixtures: list[dict[str, Any]] | None = None) -> list[int]:
    events = [e for e in bootstrap_events(bootstrap) if e.get("id") is not None]
    events.sort(key=lambda e: int(e["id"]))
    if events:
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
        if start_index is not None:
            return [int(e["id"]) for e in events[start_index:start_index + horizon]]

    fixture_gws = sorted({
        int(fixture["event"])
        for fixture in (fixtures or [])
        if isinstance(fixture, dict)
        and fixture.get("event") is not None
        and fixture.get("finished") is not True
    })
    return fixture_gws[:horizon]


def build_team_fixture_matrix(fixtures: list[dict[str, Any]], bootstrap: dict[str, Any], horizon: int) -> dict[str, list[dict[str, Any]]]:
    gws = planning_gameweeks(bootstrap, horizon, fixtures)
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
        by_team_gw.setdefault((home_id, gw_id), []).append({
            "opponent_id": away_id,
            "opponent": home_opp.get("short_name") or home_opp.get("name") or str(away_id),
            "venue": "H",
            "difficulty": fixture.get("team_h_difficulty"),
            **common,
        })
        by_team_gw.setdefault((away_id, gw_id), []).append({
            "opponent_id": home_id,
            "opponent": away_opp.get("short_name") or away_opp.get("name") or str(home_id),
            "venue": "A",
            "difficulty": fixture.get("team_a_difficulty"),
            **common,
        })
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
