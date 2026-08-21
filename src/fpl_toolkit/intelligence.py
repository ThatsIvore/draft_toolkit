from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import re
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
    """Return transparent start-probability and expected-minutes proxies."""
    availability = availability_score(player) / 100.0
    starts = _number(player.get("starts"))
    minutes = _number(player.get("minutes"))

    if starts <= 0 or minutes <= 0:
        base_start = 0.70 if availability > 0 else 0.0
        base_minutes = 60.0 if availability > 0 else 0.0
    else:
        avg_minutes_per_start = _clamp(minutes / starts, 0.0, 90.0)
        base_start = _clamp((avg_minutes_per_start - 25.0) / 65.0, 0.05, 1.0)
        base_minutes = avg_minutes_per_start

    start_probability = _clamp(base_start * availability * 100.0)
    expected_minutes = _clamp(base_minutes * availability, 0.0, 90.0)
    return start_probability, expected_minutes


def injury_return_signal(player: dict[str, Any]) -> str:
    chance = player.get("chance_next_round")
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


_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def parse_expected_return(news: str, now: datetime | None = None) -> str | None:
    """Parse a conservative expected-return date from official FPL news text.

    Only explicit phrases such as 'expected back 30 Aug' or 'return 30 August'
    are accepted. The function deliberately does not infer a date from vague injury text.
    """
    text = str(news or "")
    if not text:
        return None
    match = re.search(
        r"(?:expected\s+(?:back|return)|return(?:ing)?(?:\s+date)?|back)\s+(?:on\s+|by\s+)?(\d{1,2})\s+([A-Za-z]{3,9})(?:\s+(\d{4}))?",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    day = int(match.group(1))
    month = _MONTHS.get(match.group(2).lower())
    if not month:
        return None
    now = now or datetime.now(timezone.utc)
    year = int(match.group(3)) if match.group(3) else now.year
    try:
        candidate = datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None
    if not match.group(3) and candidate < now.replace(hour=0, minute=0, second=0, microsecond=0):
        candidate = candidate.replace(year=year + 1)
    return candidate.date().isoformat()


def return_gameweek(player: dict[str, Any], expected_return: str | None) -> int | None:
    if not expected_return:
        return None
    try:
        return_date = datetime.fromisoformat(expected_return).date()
    except ValueError:
        return None
    for gw in player.get("fixtures") or []:
        kickoff_dates = []
        for match in gw.get("matches") or []:
            raw = match.get("kickoff_time")
            if not raw:
                continue
            try:
                kickoff_dates.append(datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date())
            except ValueError:
                continue
        if kickoff_dates and return_date <= max(kickoff_dates):
            return int(gw.get("gameweek"))
    return None


def health_trend(player: dict[str, Any], previous: dict[str, Any] | None) -> str:
    if not previous:
        return "new-baseline"
    current_chance = player.get("chance_next_round")
    previous_chance = previous.get("chance_next_round")
    if current_chance is not None and previous_chance is not None:
        delta = _number(current_chance) - _number(previous_chance)
        if delta >= 25:
            return "improving"
        if delta <= -25:
            return "worsening"
    current_news = str(player.get("news") or "").strip()
    previous_news = str(previous.get("news") or "").strip()
    if current_news != previous_news:
        return "news-changed"
    return "stable"


def _recommendation(
    player: dict[str, Any],
    roster: float,
    stash: float,
    availability: float,
    return_signal: str,
    trend: str,
    my_entry_id: str | None,
) -> tuple[str, str]:
    owner = player.get("owner_entry_id")
    is_mine = my_entry_id is not None and str(owner) == str(my_entry_id)
    is_free = owner is None

    if is_mine:
        if roster < 35 and availability <= 25:
            return "REVIEW DROP", "Low near-term roster value while unavailable."
        if stash >= 70 or roster >= 68:
            return "HOLD", "Strong medium-term value relative to the current pool."
        if return_signal in {"out", "return-watch"} and stash >= 55:
            return "HOLD", "Injury cost is offset by future value and fixture outlook."
        return "HOLD", "No strong drop signal from the current model."

    if is_free:
        if availability >= 75 and roster >= 78:
            return "CLAIM", "High immediate roster value and usable availability."
        if stash >= 75 and return_signal in {"out", "return-watch", "near-return"}:
            return "STASH", "High future value despite current availability risk."
        if trend == "improving" and stash >= 65:
            return "STASH", "Health outlook improved while future value remains strong."
        if stash >= 62 or roster >= 65:
            return "WATCH", "Interesting value, but not yet a clear claim signal."
        return "PASS", "Current value does not justify using a roster spot."

    if trend == "improving" and stash >= 70:
        return "WATCH", "Owned elsewhere, but improving health makes this a drop-watch target."
    return "WATCH", "Owned by another manager; monitor for a future drop or status change."


def attach_intelligence(
    players: list[dict[str, Any]],
    previous: list[dict[str, Any]] | None = None,
    my_entry_id: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    baseline_by_id = _position_percentiles(players)
    previous_by_id = {
        int(row["player_id"]): row
        for row in (previous or [])
        if isinstance(row, dict) and row.get("player_id") is not None
    }
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
        return_signal = injury_return_signal(row)
        expected_return = parse_expected_return(str(row.get("news") or ""), now)
        expected_return_gw = return_gameweek(row, expected_return)
        trend = health_trend(row, previous_by_id.get(player_id))

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
        action, reason = _recommendation(
            row, roster, stash, availability, return_signal, trend, my_entry_id
        )

        row["intelligence"] = {
            "model": "v0.3",
            "baseline_score": round(_clamp(baseline), 1),
            "fixture_score": round(_clamp(fixtures), 1),
            "future_fixture_score": round(_clamp(future_fixtures), 1),
            "availability_score": round(_clamp(availability), 1),
            "start_probability": round(_clamp(start_probability), 1),
            "expected_minutes": round(_clamp(expected_minutes, 0.0, 90.0), 1),
            "usage_score": round(_clamp(usage), 1),
            "injury_return_signal": return_signal,
            "expected_return": expected_return,
            "expected_return_gameweek": expected_return_gw,
            "health_trend": trend,
            "roster_score": round(_clamp(roster), 1),
            "stash_score": round(_clamp(stash), 1),
            "recommendation": action,
            "recommendation_reason": reason,
        }
        enriched.append(row)
    return enriched
