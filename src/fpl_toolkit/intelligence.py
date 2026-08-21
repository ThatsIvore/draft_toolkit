from __future__ import annotations

from collections import defaultdict
from typing import Any


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _position_percentiles(players: list[dict[str, Any]]) -> dict[int, float]:
    groups: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for player in players:
        player_id = player.get("player_id")
        if player_id is None:
            continue
        groups[str(player.get("position") or "UNK")].append(
            (int(player_id), _number(player.get("total_points")))
        )

    scores: dict[int, float] = {}
    for rows in groups.values():
        ordered = sorted(rows, key=lambda item: (item[1], item[0]))
        count = len(ordered)
        if count == 1:
            scores[ordered[0][0]] = 100.0
            continue
        for rank, (player_id, _) in enumerate(ordered):
            scores[player_id] = 100.0 * rank / (count - 1)
    return scores


def availability_score(player: dict[str, Any]) -> float:
    chance = player.get("chance_next_round")
    if chance is None:
        return 100.0
    return _clamp(_number(chance))


def _inactive_factor(player: dict[str, Any]) -> float:
    news = str(player.get("news") or "").lower()
    hard_inactive_phrases = (
        "joined ",
        "permanently",
        "on loan for the rest of the season",
        "out for the season",
        "season-ending",
    )
    if any(phrase in news for phrase in hard_inactive_phrases):
        return 0.05
    return 1.0


def _match_desirability(match: dict[str, Any]) -> float:
    difficulty = int(_clamp(_number(match.get("difficulty"), 3.0), 1.0, 5.0))
    return float((6 - difficulty) * 20)


def fixture_score(player: dict[str, Any], skip_first: bool = False) -> float:
    gameweeks = list(player.get("fixtures") or [])
    if skip_first and gameweeks:
        gameweeks = gameweeks[1:]
    if not gameweeks:
        return 0.0

    weights = [1.0, 0.82, 0.67, 0.55]
    total = 0.0
    weight_total = 0.0
    for index, gw in enumerate(gameweeks[:4]):
        weight = weights[min(index, len(weights) - 1)]
        matches = [m for m in (gw.get("matches") or []) if isinstance(m, dict)]
        if not matches:
            gw_score = 0.0
        else:
            values = [_match_desirability(match) for match in matches]
            gw_score = sum(values) / len(values)
            if len(values) > 1:
                gw_score = min(100.0, gw_score + 12.0 * (len(values) - 1))
        total += gw_score * weight
        weight_total += weight
    return _clamp(total / weight_total if weight_total else 0.0)


def usage_scores(player: dict[str, Any]) -> tuple[float, float]:
    """Return (start_probability, expected_minutes) as transparent proxies.

    Public FPL data exposes season starts and minutes, but not an official next-match
    start probability. We convert historical average minutes per start into a role
    signal, then scale it by current chance-of-playing. Before meaningful season data
    exists, the model falls back to availability rather than inventing a role history.
    """
    availability = availability_score(player) / 100.0
    starts = _number(player.get("starts"))
    minutes = _number(player.get("minutes"))

    if starts <= 0 or minutes <= 0:
        base_start = 0.70 if availability > 0 else 0.0
        base_minutes = 60.0 if availability > 0 else 0.0
    else:
        avg_minutes_per_start = _clamp(minutes / starts, 0.0, 90.0)
        # 90 mins/start maps near certainty, while ~45 mins/start is treated as
        # rotation territory. This is a proxy, not an official probability.
        base_start = _clamp((avg_minutes_per_start - 25.0) / 65.0, 0.05, 1.0)
        base_minutes = avg_minutes_per_start

    start_probability = _clamp(base_start * availability * 100.0)
    expected_minutes = _clamp(base_minutes * availability, 0.0, 90.0)
    return start_probability, expected_minutes


def injury_return_signal(player: dict[str, Any]) -> str:
    chance = player.get("chance_next_round")
    news = str(player.get("news") or "").strip()
    if chance is None:
        return "fit"
    value = _number(chance)
    if value <= 0:
        return "out"
    if value < 75:
        return "return-watch"
    if value < 100:
        return "near-return"
    return "fit"


def attach_intelligence(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline_by_id = _position_percentiles(players)
    enriched: list[dict[str, Any]] = []
    for player in players:
        row = dict(player)
        player_id = int(row.get("player_id") or 0)
        baseline = baseline_by_id.get(player_id, 0.0)
        fixtures = fixture_score(row)
        future_fixtures = fixture_score(row, skip_first=True)
        availability = availability_score(row)
        start_probability, expected_minutes = usage_scores(row)
        active_factor = _inactive_factor(row)

        usage = 0.55 * start_probability + 0.45 * (expected_minutes / 90.0 * 100.0)
        roster = (
            0.35 * baseline
            + 0.28 * fixtures
            + 0.17 * availability
            + 0.20 * usage
        ) * active_factor
        stash = (
            0.45 * baseline
            + 0.34 * future_fixtures
            + 0.06 * availability
            + 0.15 * usage
        ) * active_factor

        row["intelligence"] = {
            "model": "v0.2",
            "baseline_score": round(_clamp(baseline), 1),
            "fixture_score": round(_clamp(fixtures), 1),
            "future_fixture_score": round(_clamp(future_fixtures), 1),
            "availability_score": round(_clamp(availability), 1),
            "start_probability": round(_clamp(start_probability), 1),
            "expected_minutes": round(_clamp(expected_minutes, 0.0, 90.0), 1),
            "usage_score": round(_clamp(usage), 1),
            "injury_return_signal": injury_return_signal(row),
            "roster_score": round(_clamp(roster), 1),
            "stash_score": round(_clamp(stash), 1),
        }
        enriched.append(row)
    return enriched
