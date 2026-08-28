from __future__ import annotations

from collections import defaultdict
from typing import Any

from .api import FPLApiError, FantasyApiClient


RECENCY_WEIGHTS = (1.0, 0.75, 0.55, 0.4)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def completed_gameweeks(bootstrap: dict[str, Any], limit: int = 4) -> list[int]:
    """Return only Gameweeks whose official scoring has been checked and finalised."""
    gameweeks = []
    for event in bootstrap.get("events") or []:
        if not isinstance(event, dict):
            continue
        if event.get("finished") is not True or event.get("data_checked") is not True:
            continue
        try:
            gameweeks.append(int(event["id"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(gameweeks)[-max(0, int(limit)):]


def player_id_map_by_code(
    source_bootstrap: dict[str, Any],
    target_bootstrap: dict[str, Any],
) -> dict[int, int]:
    """Map source element IDs to target IDs through the shared stable player code.

    Standard FPL and FPL Draft assign different element IDs to some players, while
    the underlying ``code`` remains consistent across both public bootstrap feeds.
    """
    target_by_code = {
        int(element["code"]): int(element["id"])
        for element in target_bootstrap.get("elements") or []
        if isinstance(element, dict)
        and element.get("id") is not None
        and element.get("code") is not None
    }
    return {
        int(element["id"]): target_by_code[int(element["code"])]
        for element in source_bootstrap.get("elements") or []
        if isinstance(element, dict)
        and element.get("id") is not None
        and element.get("code") is not None
        and int(element["code"]) in target_by_code
    }


def fetch_completed_event_live(
    client: FantasyApiClient,
    bootstrap: dict[str, Any],
    limit: int = 4,
) -> tuple[list[tuple[int, dict[str, Any]]], str]:
    """Fetch compact official event-live data, failing closed without blocking collection."""
    gameweeks = completed_gameweeks(bootstrap, limit=limit)
    if not gameweeks:
        return [], "no_completed_gameweeks"
    event_live = getattr(client, "event_live", None)
    if not callable(event_live):
        return [], "client_unavailable"
    payloads: list[tuple[int, dict[str, Any]]] = []
    try:
        for gameweek in gameweeks:
            payload = event_live(gameweek)
            if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
                return [], "invalid_payload"
            payloads.append((gameweek, payload))
    except FPLApiError:
        return [], "feed_unavailable"
    return payloads, "available"


def _percentiles(values: dict[int, float]) -> dict[int, float]:
    """Tie-aware percentile ranks with a neutral score for a one-player group."""
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    if not ordered:
        return {}
    if len(ordered) == 1:
        return {ordered[0][0]: 50.0}
    result: dict[int, float] = {}
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[index][1]:
            end += 1
        average_rank = (index + end) / 2.0
        score = 100.0 * average_rank / (len(ordered) - 1)
        for position in range(index, end + 1):
            result[ordered[position][0]] = score
        index = end + 1
    return result


def _grade(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "E"


def build_recent_match_evidence(
    players: list[dict[str, Any]],
    event_payloads: list[tuple[int, dict[str, Any]]],
    event_player_id_map: dict[int, int] | None = None,
) -> dict[int, dict[str, Any]]:
    """Create capped, position-relative grades from final official Gameweek statistics."""
    position_by_id = {
        int(player["player_id"]): str(player.get("position") or "UNK")
        for player in players
        if isinstance(player, dict) and player.get("player_id") is not None
    }
    rows_by_gameweek: dict[int, dict[int, dict[str, Any]]] = {}
    scores_by_gameweek: dict[int, dict[int, float]] = {}

    for gameweek, payload in event_payloads:
        rows: dict[int, dict[str, Any]] = {}
        groups: dict[str, list[int]] = defaultdict(list)
        for element in payload.get("elements") or []:
            if not isinstance(element, dict) or element.get("id") is None:
                continue
            event_player_id = int(element["id"])
            if event_player_id_map is not None:
                mapped_player_id = event_player_id_map.get(event_player_id)
                if mapped_player_id is None:
                    continue
                player_id = int(mapped_player_id)
            else:
                player_id = event_player_id
            if player_id not in position_by_id:
                continue
            stats = element.get("stats") if isinstance(element.get("stats"), dict) else {}
            row = {
                "gameweek": int(gameweek),
                "minutes": int(_number(stats.get("minutes"))),
                "starts": int(_number(stats.get("starts"))),
                "points": int(_number(stats.get("total_points"))),
                "bonus": int(_number(stats.get("bonus"))),
                "bps": int(_number(stats.get("bps"))),
                "xgi": round(_number(stats.get("expected_goal_involvements")), 2),
                "played": stats.get("played") is True or _number(stats.get("minutes")) > 0,
            }
            rows[player_id] = row
            groups[position_by_id[player_id]].append(player_id)

        gameweek_scores: dict[int, float] = {}
        for player_ids in groups.values():
            played_ids = [player_id for player_id in player_ids if rows[player_id]["played"]]
            points = _percentiles({player_id: rows[player_id]["points"] for player_id in played_ids})
            bps = _percentiles({player_id: rows[player_id]["bps"] for player_id in played_ids})
            xgi = _percentiles({player_id: rows[player_id]["xgi"] for player_id in played_ids})
            minutes = _percentiles({player_id: rows[player_id]["minutes"] for player_id in played_ids})
            for player_id in played_ids:
                gameweek_scores[player_id] = (
                    0.55 * points[player_id]
                    + 0.25 * bps[player_id]
                    + 0.15 * xgi[player_id]
                    + 0.05 * minutes[player_id]
                )
        rows_by_gameweek[int(gameweek)] = rows
        scores_by_gameweek[int(gameweek)] = gameweek_scores

    ordered_gameweeks = sorted(rows_by_gameweek, reverse=True)[:len(RECENCY_WEIGHTS)]
    result: dict[int, dict[str, Any]] = {}
    for player_id in position_by_id:
        appearances: list[tuple[float, float]] = []
        gameweek_rows: list[dict[str, Any]] = []
        total_minutes = 0
        starts = 0
        eligible_gameweeks = 0
        for weight, gameweek in zip(RECENCY_WEIGHTS, ordered_gameweeks):
            row = rows_by_gameweek[gameweek].get(player_id)
            if row is None:
                continue
            eligible_gameweeks += 1
            total_minutes += row["minutes"]
            starts += row["starts"]
            grade_score = scores_by_gameweek[gameweek].get(player_id)
            output = dict(row)
            output["grade_score"] = None if grade_score is None else round(grade_score, 1)
            output["grade"] = None if grade_score is None else _grade(grade_score)
            gameweek_rows.append(output)
            if grade_score is not None:
                appearances.append((weight, grade_score))

        if appearances:
            weighted_grade = sum(weight * score for weight, score in appearances) / sum(weight for weight, _ in appearances)
            role_score = 100.0 * min(1.0, total_minutes / max(90.0, eligible_gameweeks * 90.0))
            recent_score = 0.85 * weighted_grade + 0.15 * role_score
            appearance_confidence = min(1.0, len(appearances) / 3.0)
            minutes_confidence = min(1.0, total_minutes / 270.0)
            confidence = 100.0 * appearance_confidence * minutes_confidence
            adjustment = max(-5.0, min(5.0, (recent_score - 50.0) * 0.10 * confidence / 100.0))
        else:
            recent_score = 50.0
            confidence = 0.0
            adjustment = 0.0

        result[player_id] = {
            "version": "v1",
            "status": "available" if eligible_gameweeks else "unavailable",
            "score": round(recent_score, 1),
            "grade": _grade(recent_score) if appearances else None,
            "adjustment": round(adjustment, 2),
            "confidence": round(confidence, 1),
            "completed_gameweeks": eligible_gameweeks,
            "appearances": len(appearances),
            "minutes": total_minutes,
            "starts": starts,
            "gameweeks": gameweek_rows,
        }
    return result
