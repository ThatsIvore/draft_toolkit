from __future__ import annotations

from copy import deepcopy
from typing import Any


MODEL_VERSION = "standard-fpl-transfer-outcomes-v0.1"
HISTORY_LIMIT = 8


def _event_points(player: dict[str, Any]) -> float | None:
    value = player.get("event_points")
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def standard_gameweek_phase(fixtures: list[dict[str, Any]], gameweek: int) -> str:
    matches = [
        row
        for row in fixtures
        if isinstance(row, dict)
        and row.get("event") is not None
        and int(row["event"]) == int(gameweek)
    ]
    if not matches:
        return "UNKNOWN"
    if all(bool(row.get("finished")) for row in matches):
        return "FINAL"
    if any(bool(row.get("started")) for row in matches):
        return "LIVE"
    return "SCHEDULED"


def _capture_forecast(
    decision: dict[str, Any],
    gameweek: int,
    generated_at: str,
    phase: str,
) -> dict[str, Any] | None:
    if not decision.get("is_available"):
        return None
    candidate = decision.get("candidate")
    candidate_snapshot = None
    if isinstance(candidate, dict):
        incoming = candidate.get("incoming") or {}
        outgoing = candidate.get("outgoing") or {}
        allowance = candidate.get("transfer_allowance") or {}
        heuristic = candidate.get("heuristic") or {}
        candidate_snapshot = {
            "incoming": {
                "player_id": incoming.get("player_id"),
                "player": incoming.get("player"),
                "position": incoming.get("position"),
            },
            "outgoing": {
                "player_id": outgoing.get("player_id"),
                "player": outgoing.get("player"),
                "position": outgoing.get("position"),
            },
            "heuristic_score": heuristic.get("score"),
            "confidence": candidate.get("confidence"),
            "incremental_cost_points": int(allowance.get("incremental_cost_points") or 0),
        }
    return {
        "gameweek": int(gameweek),
        "captured_at": generated_at,
        "captured_phase": phase,
        "calibration_eligible": phase == "SCHEDULED",
        "recommendation": decision.get("recommendation"),
        "summary": decision.get("summary"),
        "candidate": candidate_snapshot,
    }


def _evaluate_forecast(
    forecast: dict[str, Any],
    players: list[dict[str, Any]],
    *,
    scoring_gameweek: int,
    phase: str,
) -> dict[str, Any]:
    gameweek = int(forecast.get("gameweek") or 0)
    base = {
        "gameweek": gameweek,
        "phase": phase,
        "forecast": deepcopy(forecast),
    }
    candidate = forecast.get("candidate")
    if not isinstance(candidate, dict):
        return {
            **base,
            "actual": None,
            "evaluation": {
                "complete": False,
                "calibration_eligible": False,
                "reason": "No legal benchmark candidate was available for comparison.",
            },
        }
    if gameweek < int(scoring_gameweek):
        return {
            **base,
            "actual": None,
            "evaluation": {
                "complete": False,
                "calibration_eligible": False,
                "reason": "The Gameweek-specific player snapshot was missed, so later event points were not substituted.",
            },
        }
    if gameweek != int(scoring_gameweek) or phase not in {"LIVE", "FINAL"}:
        return {
            **base,
            "actual": None,
            "evaluation": {
                "complete": False,
                "calibration_eligible": bool(forecast.get("calibration_eligible")),
            },
        }

    by_id = {
        int(row["player_id"]): row
        for row in players
        if isinstance(row, dict) and row.get("player_id") is not None
    }
    incoming = candidate.get("incoming") or {}
    outgoing = candidate.get("outgoing") or {}
    incoming_player = by_id.get(int(incoming.get("player_id") or 0), {})
    outgoing_player = by_id.get(int(outgoing.get("player_id") or 0), {})
    incoming_points = _event_points(incoming_player)
    outgoing_points = _event_points(outgoing_player)
    if incoming_points is None or outgoing_points is None:
        return {
            **base,
            "actual": None,
            "evaluation": {
                "complete": False,
                "calibration_eligible": False,
                "reason": "Matching Gameweek event points were unavailable for one or both players.",
            },
        }
    cost = int(candidate.get("incremental_cost_points") or 0)
    recommendation = str(forecast.get("recommendation") or "HOLD")
    if recommendation == "CONSIDER":
        recommendation_delta = incoming_points - outgoing_points - cost
    else:
        recommendation_delta = outgoing_points - incoming_points + cost
    actual = {
        "incoming_event_points": round(incoming_points, 1),
        "outgoing_event_points": round(outgoing_points, 1),
        "incremental_cost_points": cost,
        "recommendation_delta": round(recommendation_delta, 1),
    }
    evaluation = {
        "complete": phase == "FINAL",
        "calibration_eligible": bool(forecast.get("calibration_eligible")),
        "recommendation_outperformed_benchmark": recommendation_delta > 0 if phase == "FINAL" else None,
        "comparison_result": (
            "BETTER" if recommendation_delta > 0 else "LEVEL" if recommendation_delta == 0 else "WORSE"
        ) if phase == "FINAL" else None,
        "note": (
            "This is a player-points counterfactual including the recorded incremental hit; "
            "it does not prove the manager followed the advice or measure total-team causality."
        ),
    }
    return {**base, "actual": actual, "evaluation": evaluation}


def build_transfer_outcomes(
    previous_report: dict[str, Any] | None,
    decision: dict[str, Any],
    players: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    *,
    scoring_gameweek: int,
    decision_gameweek: int,
    generated_at: str,
) -> dict[str, Any]:
    """Freeze the first decision forecast and evaluate it only with matching GW points."""
    previous = (previous_report or {}).get("transfer_outcomes") or {}
    previous_current = previous.get("current") or {}
    history = [deepcopy(row) for row in previous.get("history") or [] if isinstance(row, dict)]
    current_phase = standard_gameweek_phase(fixtures, decision_gameweek)

    previous_forecast = previous_current.get("forecast")
    previous_gameweek = int((previous_forecast or {}).get("gameweek") or 0)
    if isinstance(previous_forecast, dict) and previous_gameweek != int(decision_gameweek):
        previous_phase = standard_gameweek_phase(fixtures, previous_gameweek)
        evaluated = _evaluate_forecast(
            previous_forecast,
            players,
            scoring_gameweek=scoring_gameweek,
            phase=previous_phase,
        )
        history = [
            row for row in history
            if int(((row.get("forecast") or {}).get("gameweek") or row.get("gameweek") or 0)) != previous_gameweek
        ]
        history.append(evaluated)

    refreshed_history: list[dict[str, Any]] = []
    for row in history:
        forecast = row.get("forecast")
        if not isinstance(forecast, dict) or (row.get("evaluation") or {}).get("complete"):
            refreshed_history.append(row)
            continue
        phase = standard_gameweek_phase(fixtures, int(forecast.get("gameweek") or 0))
        refreshed_history.append(
            _evaluate_forecast(
                forecast,
                players,
                scoring_gameweek=scoring_gameweek,
                phase=phase,
            )
        )
    history = refreshed_history[-HISTORY_LIMIT:]

    if isinstance(previous_forecast, dict) and previous_gameweek == int(decision_gameweek):
        forecast = deepcopy(previous_forecast)
    else:
        forecast = _capture_forecast(decision, decision_gameweek, generated_at, current_phase)
    current = (
        _evaluate_forecast(
            forecast,
            players,
            scoring_gameweek=scoring_gameweek,
            phase=current_phase,
        )
        if isinstance(forecast, dict)
        else None
    )
    return {
        "model": MODEL_VERSION,
        "current": current,
        "history": history,
        "note": (
            "The first recommendation captured before a Gameweek is frozen for evaluation. "
            "Only event points from that same scoring Gameweek are used."
        ),
    }
