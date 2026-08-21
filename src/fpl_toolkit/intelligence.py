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


def _percentile_scores(players: list[dict[str, Any]], value_fn) -> dict[int, float]:
    groups: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for player in players:
        player_id = player.get("player_id")
        if player_id is None:
            continue
        groups[str(player.get("position") or "UNK")].append((int(player_id), float(value_fn(player))))
    scores: dict[int, float] = {}
    for rows in groups.values():
        ordered = sorted(rows, key=lambda item: (item[1], item[0]))
        if len(ordered) == 1:
            scores[ordered[0][0]] = 100.0
            continue
        for rank, (player_id, _) in enumerate(ordered):
            scores[player_id] = 100.0 * rank / (len(ordered) - 1)
    return scores


def _raw_points_rate(player: dict[str, Any]) -> float:
    minutes = _number(player.get("minutes"))
    points = _number(player.get("total_points"))
    ppg = _number(player.get("points_per_game"))
    if minutes >= 90:
        return points * 90.0 / minutes
    if ppg > 0:
        return ppg
    return 0.0


def _raw_attacking_rate(player: dict[str, Any]) -> float:
    minutes = _number(player.get("minutes"))
    if minutes <= 0:
        return 0.0
    goals = _number(player.get("goals_scored"))
    assists = _number(player.get("assists"))
    xgi = _number(player.get("expected_goal_involvements"))
    observed = (goals + assists) * 90.0 / minutes
    expected = xgi * 90.0 / minutes if xgi > 0 else observed
    return 0.65 * observed + 0.35 * expected


def _live_evidence_weight(player: dict[str, Any], current_gameweek: int | None) -> float:
    if current_gameweek in (None, 0):
        return 1.0
    minutes = _number(player.get("minutes"))
    return min(0.85, minutes / 1350.0)


def _blend_rate(current: float, previous: float, weight: float, has_previous: bool) -> float:
    if not has_previous:
        return current
    return previous * (1.0 - weight) + current * weight


def _points_rate(player: dict[str, Any], prior: dict[str, Any] | None = None, current_gameweek: int | None = None) -> float:
    current = _raw_points_rate(player)
    if not prior or current_gameweek in (None, 0):
        return current
    previous = _raw_points_rate(prior)
    return _blend_rate(current, previous, _live_evidence_weight(player, current_gameweek), previous > 0)


def _attacking_rate(player: dict[str, Any], prior: dict[str, Any] | None = None, current_gameweek: int | None = None) -> float:
    current = _raw_attacking_rate(player)
    if not prior or current_gameweek in (None, 0):
        return current
    previous = _raw_attacking_rate(prior)
    return _blend_rate(current, previous, _live_evidence_weight(player, current_gameweek), previous > 0)


def _sample_confidence(player: dict[str, Any], prior: dict[str, Any] | None = None, current_gameweek: int | None = None) -> float:
    minutes = _number(player.get("minutes"))
    starts = _number(player.get("starts"))
    current = _clamp(max(minutes / 1800.0, starts / 20.0) * 100.0)
    if not prior or current_gameweek in (None, 0):
        return current
    prior_minutes = _number(prior.get("minutes"))
    prior_starts = _number(prior.get("starts"))
    previous = _clamp(max(prior_minutes / 1800.0, prior_starts / 20.0) * 100.0)
    weight = _live_evidence_weight(player, current_gameweek)
    return _clamp(previous * (1.0 - weight) + current * weight)


def _normalized_baselines(
    players: list[dict[str, Any]],
    performance_baseline: dict[int, dict[str, Any]] | None = None,
    current_gameweek: int | None = None,
) -> tuple[dict[int, float], dict[int, float], dict[int, float]]:
    performance_baseline = performance_baseline or {}
    points_pct = _percentile_scores(
        players, lambda p: _points_rate(p, performance_baseline.get(int(p.get("player_id") or 0)), current_gameweek)
    )
    attack_pct = _percentile_scores(
        players, lambda p: _attacking_rate(p, performance_baseline.get(int(p.get("player_id") or 0)), current_gameweek)
    )
    raw_points_pct = _percentile_scores(
        players,
        lambda p: _number((performance_baseline.get(int(p.get("player_id") or 0)) or p).get("total_points")),
    )
    baseline: dict[int, float] = {}
    floor: dict[int, float] = {}
    upside: dict[int, float] = {}
    for player in players:
        player_id = int(player.get("player_id") or 0)
        prior = performance_baseline.get(player_id)
        confidence = _sample_confidence(player, prior, current_gameweek) / 100.0
        rate = points_pct.get(player_id, 0.0)
        raw = raw_points_pct.get(player_id, 0.0)
        attack = attack_pct.get(player_id, 0.0)
        baseline[player_id] = (0.70 * rate + 0.30 * raw) * (0.65 + 0.35 * confidence)
        floor[player_id] = 0.55 * rate + 0.25 * raw + 0.20 * confidence * 100.0
        upside[player_id] = 0.52 * rate + 0.38 * attack + 0.10 * confidence * 100.0
    return baseline, floor, upside


def availability_score(player: dict[str, Any]) -> float:
    chance = player.get("chance_next_round")
    if chance is None:
        return 100.0
    return _clamp(_number(chance))


def _inactive_factor(player: dict[str, Any]) -> float:
    news = str(player.get("news") or "").lower()
    hard_inactive_phrases = ("joined ", "permanently", "on loan for the rest of the season", "out for the season", "season-ending")
    return 0.05 if any(phrase in news for phrase in hard_inactive_phrases) else 1.0


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
    total = weight_total = 0.0
    for index, gw in enumerate(gameweeks[:4]):
        weight = weights[min(index, len(weights) - 1)]
        matches = [m for m in (gw.get("matches") or []) if isinstance(m, dict)]
        values = [_match_desirability(m) for m in matches]
        gw_score = 0.0 if not values else sum(values) / len(values)
        if len(values) > 1:
            gw_score = min(100.0, gw_score + 12.0 * (len(values) - 1))
        total += gw_score * weight
        weight_total += weight
    return _clamp(total / weight_total if weight_total else 0.0)


def _raw_usage_scores(player: dict[str, Any], shrink_small_sample: bool = False) -> tuple[float, float]:
    starts = _number(player.get("starts"))
    minutes = _number(player.get("minutes"))
    if starts <= 0 or minutes <= 0:
        return 70.0, 60.0

    expected_minutes = _clamp(minutes / starts, 0.0, 90.0)
    start_probability = _clamp((expected_minutes - 25.0) / 65.0, 0.05, 1.0) * 100.0
    if shrink_small_sample:
        reliability = _clamp(starts / 10.0, 0.0, 1.0)
        start_probability = _blend_rate(start_probability, 70.0, reliability, True)
        expected_minutes = _blend_rate(expected_minutes, 60.0, reliability, True)
    return _clamp(start_probability), _clamp(expected_minutes, 0.0, 90.0)


def _fixture_is_active(player: dict[str, Any], current_gameweek: int | None) -> bool:
    if current_gameweek in (None, 0):
        return False
    for fixture in player.get("fixtures") or []:
        if int(_number(fixture.get("gameweek"), -1)) != int(current_gameweek):
            continue
        return any(
            bool(match.get("started")) and not bool(match.get("finished"))
            for match in (fixture.get("matches") or [])
            if isinstance(match, dict)
        )
    return False


def usage_scores(
    player: dict[str, Any],
    prior: dict[str, Any] | None = None,
    current_gameweek: int | None = None,
) -> tuple[float, float]:
    availability = availability_score(player) / 100.0
    current_start, current_minutes = _raw_usage_scores(player)
    prior_has_usage = bool(prior and _number(prior.get("starts")) > 0 and _number(prior.get("minutes")) > 0)

    if prior_has_usage and current_gameweek not in (None, 0):
        prior_start, prior_minutes = _raw_usage_scores(prior, shrink_small_sample=True)
        live_weight = 0.0 if _fixture_is_active(player, current_gameweek) else _live_evidence_weight(player, current_gameweek)
        base_start = _blend_rate(current_start, prior_start, live_weight, True)
        base_minutes = _blend_rate(current_minutes, prior_minutes, live_weight, True)
    elif _fixture_is_active(player, current_gameweek):
        base_start, base_minutes = 70.0, 60.0
    else:
        base_start, base_minutes = current_start, current_minutes

    return _clamp(base_start * availability), _clamp(base_minutes * availability, 0.0, 90.0)


def role_evidence(sample_confidence: float) -> str:
    if sample_confidence >= 70:
        return "HIGH"
    if sample_confidence >= 40:
        return "MEDIUM"
    return "LOW"


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


_MONTHS = {"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12}


def parse_expected_return(news: str, now: datetime | None = None) -> str | None:
    text = str(news or "")
    if not text:
        return None
    match = re.search(r"(?:expected\s+(?:back|return)|return(?:ing)?(?:\s+date)?|back)\s+(?:on\s+|by\s+)?(\d{1,2})\s+([A-Za-z]{3,9})(?:\s+(\d{4}))?", text, flags=re.IGNORECASE)
    if not match:
        return None
    day = int(match.group(1)); month = _MONTHS.get(match.group(2).lower())
    if not month:
        return None
    now = now or datetime.now(timezone.utc); year = int(match.group(3)) if match.group(3) else now.year
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
            if raw:
                try:
                    kickoff_dates.append(datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date())
                except ValueError:
                    pass
        if kickoff_dates and return_date <= max(kickoff_dates):
            return int(gw.get("gameweek"))
    return None


def health_trend(player: dict[str, Any], previous: dict[str, Any] | None) -> str:
    if not previous:
        return "new-baseline"
    current_chance = player.get("chance_next_round"); previous_chance = previous.get("chance_next_round")
    if current_chance is not None and previous_chance is not None:
        delta = _number(current_chance) - _number(previous_chance)
        if delta >= 25: return "improving"
        if delta <= -25: return "worsening"
    if str(player.get("news") or "").strip() != str(previous.get("news") or "").strip():
        return "news-changed"
    return "stable"


def _recommendation(player: dict[str, Any], roster: float, stash: float, availability: float, return_signal: str, trend: str, my_entry_id: str | None) -> tuple[str, str]:
    owner = player.get("owner_entry_id")
    is_mine = my_entry_id is not None and str(owner) == str(my_entry_id)
    is_free = owner is None
    if is_mine:
        if roster < 35 and availability <= 25: return "REVIEW DROP", "Low near-term roster value while unavailable."
        if stash >= 70 or roster >= 68: return "HOLD", "Strong medium-term value relative to the current pool."
        if return_signal in {"out", "return-watch"} and stash >= 55: return "HOLD", "Injury cost is offset by future value and fixture outlook."
        return "HOLD", "No strong drop signal from the current model."
    if is_free:
        if availability >= 75 and roster >= 78: return "CLAIM", "High immediate roster value and usable availability."
        if stash >= 75 and return_signal in {"out", "return-watch", "near-return"}: return "STASH", "High future value despite current availability risk."
        if trend == "improving" and stash >= 65: return "STASH", "Health outlook improved while future value remains strong."
        if stash >= 62 or roster >= 65: return "WATCH", "Interesting value, but not yet a clear claim signal."
        return "PASS", "Current value does not justify using a roster spot."
    if trend == "improving" and stash >= 70: return "WATCH", "Owned elsewhere, but improving health makes this a drop-watch target."
    return "WATCH", "Owned by another manager; monitor for a future drop or status change."


def attach_intelligence(
    players: list[dict[str, Any]],
    previous: list[dict[str, Any]] | None = None,
    my_entry_id: str | None = None,
    now: datetime | None = None,
    performance_baseline: dict[int, dict[str, Any]] | None = None,
    current_gameweek: int | None = None,
) -> list[dict[str, Any]]:
    performance_baseline = performance_baseline or {}
    baseline_by_id, floor_by_id, upside_by_id = _normalized_baselines(players, performance_baseline, current_gameweek)
    previous_by_id = {int(row["player_id"]): row for row in (previous or []) if isinstance(row, dict) and row.get("player_id") is not None}
    enriched = []
    for player in players:
        row = dict(player); player_id = int(row.get("player_id") or 0)
        prior = performance_baseline.get(player_id)
        baseline = baseline_by_id.get(player_id, 0.0); floor = floor_by_id.get(player_id, 0.0); upside = upside_by_id.get(player_id, 0.0)
        fixtures = fixture_score(row); future_fixtures = fixture_score(row, skip_first=True); availability = availability_score(row)
        start_probability, expected_minutes = usage_scores(row, prior, current_gameweek); active_factor = _inactive_factor(row)
        return_signal = injury_return_signal(row); expected_return = parse_expected_return(str(row.get("news") or ""), now)
        expected_return_gw = return_gameweek(row, expected_return); trend = health_trend(row, previous_by_id.get(player_id))
        usage = 0.55 * start_probability + 0.45 * (expected_minutes / 90.0 * 100.0)
        sample_confidence = _sample_confidence(row, prior, current_gameweek)
        floor = (0.55 * floor + 0.25 * usage + 0.20 * availability) * active_factor
        upside = (0.55 * upside + 0.30 * future_fixtures + 0.15 * availability) * active_factor
        roster = (0.28 * baseline + 0.24 * fixtures + 0.16 * availability + 0.16 * usage + 0.16 * floor) * active_factor
        stash = (0.30 * baseline + 0.30 * future_fixtures + 0.08 * availability + 0.12 * usage + 0.20 * upside) * active_factor
        action, reason = _recommendation(row, roster, stash, availability, return_signal, trend, my_entry_id)
        row["intelligence"] = {
            "model": "v0.5.3", "baseline_score": round(_clamp(baseline), 1), "fixture_score": round(_clamp(fixtures), 1),
            "future_fixture_score": round(_clamp(future_fixtures), 1), "availability_score": round(_clamp(availability), 1),
            "start_probability": round(_clamp(start_probability), 1), "expected_minutes": round(_clamp(expected_minutes, 0.0, 90.0), 1),
            "usage_score": round(_clamp(usage), 1), "sample_confidence": round(sample_confidence, 1), "role_evidence": role_evidence(sample_confidence),
            "floor_score": round(_clamp(floor), 1), "upside_score": round(_clamp(upside), 1),
            "points_per_90": round(_points_rate(row, prior, current_gameweek), 2), "attack_returns_per_90": round(_attacking_rate(row, prior, current_gameweek), 2),
            "historical_prior_active": bool(prior and current_gameweek not in (None, 0)),
            "injury_return_signal": return_signal, "expected_return": expected_return, "expected_return_gameweek": expected_return_gw,
            "health_trend": trend, "roster_score": round(_clamp(roster), 1), "stash_score": round(_clamp(stash), 1),
            "recommendation": action, "recommendation_reason": reason,
        }
        enriched.append(row)
    return enriched
