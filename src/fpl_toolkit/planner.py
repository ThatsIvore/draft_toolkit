from __future__ import annotations

from typing import Any

from .optimizer import player_start_score


FORMATION_LIMITS = {
    "DEF": (3, 5),
    "MID": (2, 5),
    "FWD": (1, 3),
}
POSITION_ORDER = {"GKP": 0, "DEF": 1, "MID": 2, "FWD": 3}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _fixture_matches(player: dict[str, Any], gameweek: int) -> list[dict[str, Any]]:
    for item in player.get("fixtures") or []:
        if int(item.get("gameweek") or 0) == int(gameweek):
            return [match for match in (item.get("matches") or []) if isinstance(match, dict)]
    return []


def _fixture_summary(player: dict[str, Any], gameweek: int) -> dict[str, Any]:
    matches = _fixture_matches(player, gameweek)
    difficulties = [
        _clamp(_number(match.get("difficulty"), 3.0), 1.0, 5.0)
        for match in matches
    ]
    label = " + ".join(
        f"{match.get('opponent') or '-'} ({match.get('venue') or '-'})"
        for match in matches
    ) or "Blank"
    return {
        "label": label,
        "difficulty": round(sum(difficulties) / len(difficulties), 1) if difficulties else None,
        "fixture_count": len(matches),
    }


def player_schedule_score(player: dict[str, Any], gameweek: int) -> dict[str, Any]:
    """Return future-window utility without pretending to project FPL points.

    Schedule Score deliberately separates fixture-window usefulness from the
    next-GW Start Score. It rewards the immediate fixture in that Gameweek and
    blends in Floor, Upside, Roster Value and the amount of role evidence.
    Current availability is exposed separately rather than being projected
    several weeks into the future without evidence.
    """
    intel = player.get("intelligence") or {}
    fixture = _fixture_summary(player, gameweek)
    difficulty = fixture["difficulty"]
    if difficulty is None:
        fixture_score = 0.0
    else:
        fixture_score = _clamp((6.0 - difficulty) * 20.0)
        if fixture["fixture_count"] > 1:
            fixture_score = min(100.0, fixture_score + 10.0 * (fixture["fixture_count"] - 1))

    floor = _clamp(_number(intel.get("floor_score"), intel.get("roster_score", 0.0)))
    upside = _clamp(_number(intel.get("upside_score"), intel.get("roster_score", 0.0)))
    roster = _clamp(_number(intel.get("roster_score")))
    confidence = _clamp(_number(intel.get("sample_confidence"), 100.0))
    raw = 0.50 * fixture_score + 0.20 * floor + 0.15 * upside + 0.10 * roster + 0.05 * confidence
    score = raw if fixture["fixture_count"] else raw * 0.45
    return {
        "schedule_score": round(_clamp(score), 1),
        "fixture": fixture["label"],
        "difficulty": difficulty,
        "fixture_count": fixture["fixture_count"],
    }


def _legal_formations(squad: list[dict[str, Any]]) -> list[tuple[int, int, int]]:
    counts = {
        position: sum(1 for player in squad if player.get("position") == position)
        for position in ("DEF", "MID", "FWD")
    }
    formations: list[tuple[int, int, int]] = []
    for defenders in range(FORMATION_LIMITS["DEF"][0], min(FORMATION_LIMITS["DEF"][1], counts["DEF"]) + 1):
        for midfielders in range(FORMATION_LIMITS["MID"][0], min(FORMATION_LIMITS["MID"][1], counts["MID"]) + 1):
            for forwards in range(FORMATION_LIMITS["FWD"][0], min(FORMATION_LIMITS["FWD"][1], counts["FWD"]) + 1):
                if defenders + midfielders + forwards == 10:
                    formations.append((defenders, midfielders, forwards))
    return formations


def _schedule_lineup(squad: list[dict[str, Any]], gameweek: int) -> dict[str, Any]:
    scores = {
        int(player["player_id"]): player_schedule_score(player, gameweek)
        for player in squad
        if player.get("player_id") is not None
    }
    goalkeepers = sorted(
        [player for player in squad if player.get("position") == "GKP"],
        key=lambda player: scores[int(player["player_id"])]["schedule_score"],
        reverse=True,
    )
    formations = _legal_formations(squad)
    if not goalkeepers or not formations:
        return {
            "gameweek": gameweek,
            "formation": None,
            "average_schedule_score": 0.0,
            "low_schedule_starters": 0,
            "starter_ids": [],
        }

    ranked = {
        position: sorted(
            [player for player in squad if player.get("position") == position],
            key=lambda player: scores[int(player["player_id"])]["schedule_score"],
            reverse=True,
        )
        for position in ("DEF", "MID", "FWD")
    }
    best: tuple[float, tuple[int, int, int], list[dict[str, Any]]] | None = None
    for defenders, midfielders, forwards in formations:
        starters = (
            [goalkeepers[0]]
            + ranked["DEF"][:defenders]
            + ranked["MID"][:midfielders]
            + ranked["FWD"][:forwards]
        )
        total = sum(scores[int(player["player_id"])]["schedule_score"] for player in starters)
        if best is None or total > best[0]:
            best = (total, (defenders, midfielders, forwards), starters)

    assert best is not None
    total, formation, starters = best
    starter_scores = [scores[int(player["player_id"])]["schedule_score"] for player in starters]
    defenders, midfielders, forwards = formation
    return {
        "gameweek": gameweek,
        "formation": f"{defenders}-{midfielders}-{forwards}",
        "average_schedule_score": round(total / 11.0, 1),
        "low_schedule_starters": sum(1 for score in starter_scores if score < 60.0),
        "starter_ids": [int(player["player_id"]) for player in starters],
    }


def _schedule_signal(weeks: list[dict[str, Any]]) -> str:
    strong = sum(1 for week in weeks if week.get("difficulty") is not None and _number(week["difficulty"]) <= 2.0)
    weak = sum(1 for week in weeks if week.get("difficulty") is None or _number(week["difficulty"]) >= 4.0)
    if weak >= 2:
        return "WEAK WINDOW"
    if strong >= 2 and weak <= 1:
        return "STRONG RUN"
    return "MIXED"


def _player_planner_row(player: dict[str, Any], gameweeks: list[int]) -> dict[str, Any]:
    weeks = [
        {"gameweek": gameweek, **player_schedule_score(player, gameweek)}
        for gameweek in gameweeks
    ]
    scores = [_number(week["schedule_score"]) for week in weeks]
    intel = player.get("intelligence") or {}
    next_start = player_start_score(player, gameweeks[0])["start_score"] if gameweeks else None
    return {
        "player_id": int(player.get("player_id") or 0),
        "player": player.get("player"),
        "club": player.get("club"),
        "team_code": player.get("team_code"),
        "position": player.get("position"),
        "roster_value": round(_number(intel.get("roster_score")), 1),
        "next_start_score": next_start,
        "average_schedule_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "role_evidence": intel.get("role_evidence"),
        "availability_now": round(_number(intel.get("availability_score"), 100.0), 1),
        "signal": _schedule_signal(weeks),
        "weeks": weeks,
    }


def _streamer_targets(
    squad_rows: list[dict[str, Any]],
    available: list[dict[str, Any]],
    gameweeks: list[int],
    limit: int = 8,
) -> list[dict[str, Any]]:
    owned_by_position: dict[str, list[dict[str, Any]]] = {}
    for row in squad_rows:
        owned_by_position.setdefault(str(row.get("position") or ""), []).append(row)

    targets: list[dict[str, Any]] = []
    for player in available:
        position = str(player.get("position") or "")
        owned = owned_by_position.get(position) or []
        if not owned:
            continue
        candidate = _player_planner_row(player, gameweeks)
        drop = min(owned, key=lambda row: _number(row.get("average_schedule_score")))
        schedule_delta = candidate["average_schedule_score"] - _number(drop.get("average_schedule_score"))
        if schedule_delta < 3.0:
            continue
        roster_delta = candidate["roster_value"] - _number(drop.get("roster_value"))
        next_start_delta = _number(candidate.get("next_start_score")) - _number(drop.get("next_start_score"))
        evidence = str(candidate.get("role_evidence") or "LOW").upper()
        label = "SCHEDULE UPGRADE" if schedule_delta >= 6.0 and roster_delta >= -5.0 and evidence != "LOW" else "WATCH"
        targets.append({
            "label": label,
            "add_player_id": candidate["player_id"],
            "add_player": candidate["player"],
            "add_club": candidate["club"],
            "team_code": candidate["team_code"],
            "position": position,
            "drop_player_id": drop["player_id"],
            "drop_player": drop["player"],
            "schedule_delta": round(schedule_delta, 1),
            "roster_delta": round(roster_delta, 1),
            "next_start_delta": round(next_start_delta, 1),
            "candidate_schedule_score": candidate["average_schedule_score"],
            "drop_schedule_score": drop["average_schedule_score"],
            "role_evidence": candidate.get("role_evidence"),
            "availability_now": candidate.get("availability_now"),
            "weeks": candidate["weeks"],
        })

    targets.sort(
        key=lambda target: (
            target["label"] == "SCHEDULE UPGRADE",
            _number(target["schedule_delta"]),
            _number(target["roster_delta"]),
        ),
        reverse=True,
    )
    return targets[:limit]


def build_schedule_planner(
    squad: list[dict[str, Any]],
    available: list[dict[str, Any]],
    gameweeks: list[int],
) -> dict[str, Any]:
    """Build the four-Gameweek schedule and streamer decision layer."""
    gws = [int(gameweek) for gameweek in gameweeks]
    squad_rows = [_player_planner_row(player, gws) for player in squad]
    squad_rows.sort(key=lambda row: (POSITION_ORDER.get(str(row.get("position")), 99), -_number(row.get("average_schedule_score"))))
    weeks = [_schedule_lineup(squad, gameweek) for gameweek in gws]
    weakest = min(weeks, key=lambda week: _number(week.get("average_schedule_score"))) if weeks else None
    return {
        "model": "v0.7",
        "gameweeks": gws,
        "weeks": weeks,
        "weakest_gameweek": weakest.get("gameweek") if weakest else None,
        "roster_rows": squad_rows,
        "streamer_targets": _streamer_targets(squad_rows, available, gws),
        "note": "Schedule Score measures fixture-window utility, not projected FPL points. Start Score remains a next-Gameweek selection signal; Roster Value remains the longer-term player signal.",
    }
