from __future__ import annotations

from copy import deepcopy
from typing import Any

from .h2h import player_projected_points


OUTCOME_MODEL = "v0.2"


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def gameweek_phase(fixtures: list[dict[str, Any]], gameweek: int) -> str:
    matches = [
        fixture
        for fixture in fixtures
        if isinstance(fixture, dict) and fixture.get("event") is not None and int(fixture["event"]) == int(gameweek)
    ]
    if not matches:
        return "UNKNOWN"
    if all(bool(match.get("finished")) for match in matches):
        return "FINAL"
    if any(bool(match.get("started")) for match in matches):
        return "LIVE"
    return "SCHEDULED"


def _capture_forecast(report: dict[str, Any], gameweek: int, phase: str) -> dict[str, Any]:
    recommended = report.get("recommended_lineup") or {}
    h2h = report.get("h2h_matchup") or {}
    matchup = h2h.get("matchup") or {}
    my_projection = (matchup.get("my") or {}).get("projection") or {}
    opponent_projection = (matchup.get("opponent") or {}).get("projection") or {}
    starters = []
    for player in recommended.get("starters") or []:
        if not isinstance(player, dict) or player.get("player_id") is None:
            continue
        projection = player_projected_points(player, gameweek)
        starters.append({
            "player_id": int(player["player_id"]),
            "player": player.get("player"),
            "position": player.get("position"),
            "projected_points": projection.get("projected_points"),
            "range_low": projection.get("range_low"),
            "range_high": projection.get("range_high"),
        })
    has_context = bool(starters) and all(
        any(int(week.get("gameweek") or 0) == gameweek for week in player.get("fixtures") or [])
        for player in recommended.get("starters") or []
    )
    eligible = (
        phase == "SCHEDULED" and report.get("_forecast_before_deadline", True)
        and has_context and recommended.get("is_valid", True)
    )
    return {
        "model": OUTCOME_MODEL,
        "captured_at": report.get("generated_at"),
        "captured_phase": phase,
        "calibration_eligible": bool(eligible),
        "exclusion_reason": None if eligible else "Forecast lacks pre-deadline evidence or a valid lineup with fixture context.",
        "recommended": {
            "formation": recommended.get("formation"),
            "projected_total": round(sum(_number(row.get("projected_points")) for row in starters), 1),
            "range_low": round(sum(_number(row.get("range_low")) for row in starters), 1),
            "range_high": round(sum(_number(row.get("range_high")) for row in starters), 1),
            "starters": starters,
        },
        "h2h": {
            "projected_my_total": my_projection.get("total"),
            "projected_opponent_total": opponent_projection.get("total"),
            "projected_edge": matchup.get("projected_points_edge"),
            "signal": matchup.get("signal"),
        },
    }


def _actuals(report: dict[str, Any], forecast: dict[str, Any], phase: str, scoring_players: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    squad = {
        int(player["player_id"]): player
        for player in (scoring_players if scoring_players is not None else report.get("my_squad") or [])
        if isinstance(player, dict) and player.get("player_id") is not None
    }
    players = []
    for row in (forecast.get("recommended") or {}).get("starters") or []:
        player = squad.get(int(row.get("player_id") or 0), {})
        players.append({
            "player_id": row.get("player_id"),
            "player": row.get("player"),
            "event_points": _number(player["event_points"]) if player.get("event_points") is not None else None,
        })
    actuals_complete = bool(players) and all(player["event_points"] is not None for player in players)
    recommended_points = sum(_number(player.get("event_points")) for player in players)
    lineup = report.get("lineup") or {}
    official_points = lineup.get("event_points_total")
    if official_points is None and lineup.get("is_exact"):
        official_points = sum(_number(player.get("event_points")) for player in lineup.get("starters") or [])
    h2h_result = (report.get("h2h_matchup") or {}).get("result") or {}
    my_points = _number(h2h_result.get("my_points"))
    opponent_points = _number(h2h_result.get("opponent_points"))
    h2h_score_source = h2h_result.get("source") or "league_details"
    if phase in {"LIVE", "FINAL"} and my_points == 0 and opponent_points == 0:
        opponent_lineup = (report.get("h2h_matchup") or {}).get("opponent_lineup") or {}
        estimated_opponent = sum(
            _number(player.get("event_points"))
            for player in opponent_lineup.get("starters") or []
            if isinstance(player, dict)
        )
        estimated_mine = _number(official_points, recommended_points)
        if estimated_mine != 0 or estimated_opponent != 0:
            my_points = estimated_mine
            opponent_points = estimated_opponent
            h2h_score_source = "estimated_lineups"
    result = "DRAW" if my_points == opponent_points else "WIN" if my_points > opponent_points else "LOSS"
    return {
        "recommended_points": round(recommended_points, 1) if actuals_complete else None,
        "recommended_actuals_complete": actuals_complete,
        "recommended_players": players,
        "official_points": round(_number(official_points), 1) if official_points is not None else None,
        "h2h_my_points": round(my_points, 1),
        "h2h_opponent_points": round(opponent_points, 1),
        "h2h_edge": round(my_points - opponent_points, 1),
        "h2h_result": result,
        "h2h_score_source": h2h_score_source,
    }


def _evaluation(forecast: dict[str, Any], actual: dict[str, Any], phase: str) -> dict[str, Any]:
    if phase != "FINAL":
        return {"complete": False, "calibration_eligible": bool(forecast.get("calibration_eligible"))}
    projected_total = _number((forecast.get("recommended") or {}).get("projected_total"))
    projected_edge = _number((forecast.get("h2h") or {}).get("projected_edge"))
    predicted_result = "DRAW" if projected_edge == 0 else "WIN" if projected_edge > 0 else "LOSS"
    return {
        "complete": True,
        "calibration_eligible": bool(forecast.get("calibration_eligible")) and actual.get("recommended_points") is not None,
        "recommended_absolute_error": round(abs(_number(actual.get("recommended_points")) - projected_total), 1) if actual.get("recommended_points") is not None else None,
        "h2h_edge_error": round(abs(_number(actual.get("h2h_edge")) - projected_edge), 1),
        "predicted_h2h_result": predicted_result,
        "h2h_result_correct": predicted_result == actual.get("h2h_result"),
    }


def build_outcome_diagnostics(
    previous_state: dict[str, Any] | None,
    report: dict[str, Any],
    phase: str,
    gameweek: int | None = None,
    scoring_players: list[dict[str, Any]] | None = None,
    decision_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gameweek = int(gameweek if gameweek is not None else report.get("current_gameweek") or 0)
    previous = (previous_state or {}).get("outcome_diagnostics") or {}
    previous_current = previous.get("current") or {}
    if int(previous_current.get("gameweek") or -1) == gameweek and isinstance(previous_current.get("forecast"), dict):
        forecast = deepcopy(previous_current["forecast"])
    elif str(gameweek) in (previous.get("pending_forecasts") or {}):
        forecast = deepcopy(previous["pending_forecasts"][str(gameweek)])
    else:
        forecast = _capture_forecast(report, gameweek, phase)

    _exclude_legacy_zero_forecast(forecast)
    actual = _actuals(report, forecast, phase, scoring_players)
    current = {
        "gameweek": gameweek,
        "phase": phase,
        "forecast": forecast,
        "actual": actual,
        "evaluation": _evaluation(forecast, actual, phase),
    }
    history = deepcopy([row for row in previous.get("history") or [] if isinstance(row, dict)])
    if previous_current and int(previous_current.get("gameweek") or -1) != gameweek and previous_current.get("phase") == "FINAL":
        history = [row for row in history if int(row.get("gameweek") or -1) != int(previous_current.get("gameweek") or -1)]
        history.append(deepcopy(previous_current))
    for row in history:
        if _exclude_legacy_zero_forecast(row.get("forecast") or {}):
            row.setdefault("evaluation", {})["calibration_eligible"] = False
    pending = {}
    if decision_report is not None:
        decision_gw = int(decision_report.get("decision_gameweek") or 0)
        if decision_gw > gameweek:
            key = str(decision_gw)
            if key in (previous.get("pending_forecasts") or {}):
                pending[key] = deepcopy(previous["pending_forecasts"][key])
            elif decision_report.get("decision_gameweek_phase") == "SCHEDULED":
                candidate = _capture_forecast({**decision_report, "_forecast_before_deadline": True}, decision_gw, "SCHEDULED")
                if candidate["calibration_eligible"]:
                    pending[key] = candidate
    return {
        "model": OUTCOME_MODEL,
        "current": current,
        "history": history[-8:],
        "pending_forecasts": pending,
        "note": (
            "This forecast was captured before the Gameweek started and is eligible for calibration."
            if current["evaluation"].get("calibration_eligible")
            else "This sample is excluded from calibration because pre-deadline forecast evidence or complete actuals are unavailable; original forecast values are retained."
        ),
    }


def _exclude_legacy_zero_forecast(forecast: dict[str, Any]) -> bool:
    """Quarantine legacy blank-context forecasts without rewriting predictions."""
    recommended = forecast.get("recommended") or {}
    if forecast.get("model") is None and _number(recommended.get("projected_total")) == 0:
        forecast["calibration_eligible"] = False
        forecast["exclusion_reason"] = "Legacy zero forecast may lack scoring-Gameweek fixture context."
        return True
    return False
