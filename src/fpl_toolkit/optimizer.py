from __future__ import annotations

from typing import Any


FORMATION_LIMITS = {
    "DEF": (3, 5),
    "MID": (2, 5),
    "FWD": (1, 3),
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _gameweek_matches(player: dict[str, Any], gameweek: int) -> list[dict[str, Any]]:
    for item in player.get("fixtures") or []:
        if int(item.get("gameweek") or 0) == int(gameweek):
            return [match for match in (item.get("matches") or []) if isinstance(match, dict)]
    return []


def next_fixture_score(player: dict[str, Any], gameweek: int) -> float:
    """Convert official FPL 1-5 fixture difficulty into a 0-100 next-GW score."""
    matches = _gameweek_matches(player, gameweek)
    if not matches:
        return 0.0
    values = []
    for match in matches:
        difficulty = int(_clamp(_number(match.get("difficulty"), 3.0), 1.0, 5.0))
        values.append(float((6 - difficulty) * 20))
    score = sum(values) / len(values)
    if len(values) > 1:
        score = min(100.0, score + 10.0 * (len(values) - 1))
    return _clamp(score)


def player_start_score(player: dict[str, Any], gameweek: int) -> dict[str, float]:
    """Return transparent next-GW selection components and a heuristic Start Score.

    Start Score is not expected FPL points. Availability is intentionally applied
    both as an input and as a final selection-risk factor so ruled-out players do
    not outrank fit alternatives solely on historical quality.
    """
    intel = player.get("intelligence") or {}
    chance = player.get("chance_next_round")
    availability = _number(intel.get("availability_score"), 100.0 if chance is None else _number(chance))
    availability = _clamp(availability)
    expected_minutes = _clamp(_number(intel.get("expected_minutes"), 60.0 if availability > 0 else 0.0), 0.0, 90.0)
    minutes_score = expected_minutes / 90.0 * 100.0
    fixture = next_fixture_score(player, gameweek)
    floor = _clamp(_number(intel.get("floor_score"), intel.get("roster_score", 0.0)))
    upside = _clamp(_number(intel.get("upside_score"), intel.get("roster_score", 0.0)))

    raw = (
        0.30 * availability
        + 0.25 * minutes_score
        + 0.20 * fixture
        + 0.15 * floor
        + 0.10 * upside
    )
    availability_factor = 0.20 + 0.80 * (availability / 100.0)
    blank_factor = 1.0 if _gameweek_matches(player, gameweek) else 0.55
    score = _clamp(raw * availability_factor * blank_factor)
    return {
        "start_score": round(score, 1),
        "availability": round(availability, 1),
        "expected_minutes": round(expected_minutes, 1),
        "next_fixture": round(fixture, 1),
        "floor": round(floor, 1),
        "upside": round(upside, 1),
    }


def _legal_formations(squad: list[dict[str, Any]]) -> list[tuple[int, int, int]]:
    counts = {position: sum(1 for player in squad if player.get("position") == position) for position in ("DEF", "MID", "FWD")}
    formations = []
    for defenders in range(FORMATION_LIMITS["DEF"][0], min(FORMATION_LIMITS["DEF"][1], counts["DEF"]) + 1):
        for midfielders in range(FORMATION_LIMITS["MID"][0], min(FORMATION_LIMITS["MID"][1], counts["MID"]) + 1):
            for forwards in range(FORMATION_LIMITS["FWD"][0], min(FORMATION_LIMITS["FWD"][1], counts["FWD"]) + 1):
                if defenders + midfielders + forwards == 10:
                    formations.append((defenders, midfielders, forwards))
    return formations


def _rank(players: list[dict[str, Any]], scores: dict[int, dict[str, float]]) -> list[dict[str, Any]]:
    return sorted(
        players,
        key=lambda player: (
            scores.get(int(player.get("player_id") or 0), {}).get("start_score", 0.0),
            _number((player.get("intelligence") or {}).get("floor_score")),
            _number((player.get("intelligence") or {}).get("upside_score")),
        ),
        reverse=True,
    )


def _with_selection(player: dict[str, Any], score: dict[str, float], role: str, bench_order: int | None = None) -> dict[str, Any]:
    row = dict(player)
    row["selection"] = {"role": role, **score}
    if bench_order is not None:
        row["selection"]["bench_order"] = bench_order
    return row


def recommend_lineup(squad: list[dict[str, Any]], gameweek: int) -> dict[str, Any]:
    """Choose the highest-scoring legal XI and order the outfield bench.

    Legal FPL formations require exactly one goalkeeper, 3-5 defenders,
    2-5 midfielders and 1-3 forwards. The reserve goalkeeper is separate from
    outfield autosub priority, which is ordered 1-3 by Start Score.
    """
    player_scores = {
        int(player.get("player_id") or 0): player_start_score(player, gameweek)
        for player in squad
        if player.get("player_id") is not None
    }
    goalkeepers = _rank([player for player in squad if player.get("position") == "GKP"], player_scores)
    formations = _legal_formations(squad)
    if not goalkeepers or not formations:
        return {
            "model": "v0.6",
            "gameweek": gameweek,
            "is_recommendation": True,
            "is_valid": False,
            "formation": None,
            "starters": [],
            "bench": [],
            "reserve_goalkeeper": None,
            "player_scores": {str(key): value for key, value in player_scores.items()},
            "note": "A legal XI could not be generated from the current squad shape.",
        }

    ranked = {
        position: _rank([player for player in squad if player.get("position") == position], player_scores)
        for position in ("DEF", "MID", "FWD")
    }
    starting_goalkeeper = goalkeepers[0]
    best: tuple[float, tuple[int, int, int], list[dict[str, Any]]] | None = None
    for defenders, midfielders, forwards in formations:
        starters = (
            [starting_goalkeeper]
            + ranked["DEF"][:defenders]
            + ranked["MID"][:midfielders]
            + ranked["FWD"][:forwards]
        )
        total = sum(player_scores[int(player["player_id"])]["start_score"] for player in starters)
        candidate = (total, (defenders, midfielders, forwards), starters)
        if best is None or candidate[0] > best[0]:
            best = candidate

    assert best is not None
    total_score, formation_counts, selected = best
    selected_ids = {int(player["player_id"]) for player in selected}
    selected_by_position = []
    for position in ("GKP", "DEF", "MID", "FWD"):
        selected_by_position.extend(
            _rank([player for player in selected if player.get("position") == position], player_scores)
        )

    remaining_outfield = _rank(
        [player for player in squad if player.get("position") != "GKP" and int(player.get("player_id") or 0) not in selected_ids],
        player_scores,
    )
    reserve_goalkeeper = goalkeepers[1] if len(goalkeepers) > 1 else None

    starters = [
        _with_selection(player, player_scores[int(player["player_id"])], "START")
        for player in selected_by_position
    ]
    bench = [
        _with_selection(player, player_scores[int(player["player_id"])], "BENCH", index)
        for index, player in enumerate(remaining_outfield, start=1)
    ]
    reserve = (
        _with_selection(reserve_goalkeeper, player_scores[int(reserve_goalkeeper["player_id"])], "RESERVE GKP")
        if reserve_goalkeeper
        else None
    )
    defenders, midfielders, forwards = formation_counts
    return {
        "model": "v0.6",
        "gameweek": gameweek,
        "is_recommendation": True,
        "is_valid": True,
        "formation": f"{defenders}-{midfielders}-{forwards}",
        "starters": starters,
        "bench": bench,
        "reserve_goalkeeper": reserve,
        "player_scores": {str(key): value for key, value in player_scores.items()},
        "total_start_score": round(total_score, 1),
        "average_start_score": round(total_score / 11.0, 1),
        "note": "Toolkit recommendation only; this is not the submitted Draft lineup or projected FPL points.",
    }
