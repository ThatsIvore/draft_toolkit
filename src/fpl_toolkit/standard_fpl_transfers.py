from __future__ import annotations

from collections import Counter
from typing import Any

from .optimizer import player_start_score
from .standard_fpl_rules import (
    RULES_2026_27,
    StandardFplRules,
    evaluate_single_transfer,
)


MODEL_VERSION = "standard-fpl-single-transfer-ranking-v0.1"
WEIGHTS = {
    "roster": 0.30,
    "start": 0.25,
    "future_fixture": 0.20,
    "floor": 0.15,
    "upside": 0.10,
}
UNAVAILABLE_REASON = (
    "Exact current selling prices, bank, free-transfer balance and chip state are required."
)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _confidence_label(value: float) -> str:
    if value >= 70.0:
        return "HIGH"
    if value >= 40.0:
        return "MEDIUM"
    return "LOW"


def _player_summary(player: dict[str, Any], *, outgoing: bool) -> dict[str, Any]:
    price_field = "selling_price" if outgoing else "now_cost"
    return {
        "player_id": player.get("player_id"),
        "player": player.get("player"),
        "club": player.get("club"),
        "team_id": player.get("team_id"),
        "position": player.get("position"),
        price_field: player.get(price_field),
    }


def unavailable_single_transfer_ranking(reason: str = UNAVAILABLE_REASON) -> dict[str, Any]:
    return {
        "model": MODEL_VERSION,
        "is_available": False,
        "advisory_only": True,
        "reason": reason,
        "weights": dict(WEIGHTS),
        "candidates": [],
        "evaluated_pairs": 0,
        "rejected_counts": {},
        "note": (
            "Transfer ranking is unavailable without exact private team state. "
            "Heuristic deltas are not projected FPL points."
        ),
    }


def _ranking_components(
    incoming: dict[str, Any],
    outgoing: dict[str, Any],
    decision_gameweek: int,
) -> tuple[dict[str, float], float, str]:
    incoming_intel = incoming.get("intelligence") or {}
    outgoing_intel = outgoing.get("intelligence") or {}
    incoming_start = player_start_score(incoming, decision_gameweek)
    outgoing_start = player_start_score(outgoing, decision_gameweek)

    deltas = {
        "roster": _number(incoming_intel.get("roster_score"))
        - _number(outgoing_intel.get("roster_score")),
        "start": _number(incoming_start.get("start_score"))
        - _number(outgoing_start.get("start_score")),
        "future_fixture": _number(incoming_intel.get("future_fixture_score"))
        - _number(outgoing_intel.get("future_fixture_score")),
        "floor": _number(incoming_intel.get("floor_score"))
        - _number(outgoing_intel.get("floor_score")),
        "upside": _number(incoming_intel.get("upside_score"))
        - _number(outgoing_intel.get("upside_score")),
    }
    score = sum(WEIGHTS[key] * value for key, value in deltas.items())
    confidence_value = min(
        _number(incoming_intel.get("sample_confidence"), 0.0),
        _number(outgoing_intel.get("sample_confidence"), 0.0),
    )
    return (
        {key: round(value, 1) for key, value in deltas.items()},
        round(score, 1),
        _confidence_label(confidence_value),
    )


def rank_single_transfers(
    players: list[dict[str, Any]],
    squad: list[dict[str, Any]],
    decision_gameweek: int,
    *,
    bank_tenths: int,
    free_transfers: int,
    transfers_made: int,
    active_chip: str | None = None,
    limit: int = 10,
    rules: StandardFplRules = RULES_2026_27,
) -> dict[str, Any]:
    """Rank legal one-for-one Standard FPL moves using advisory heuristic deltas.

    A point deduction remains a separate decision cost. It is deliberately not
    subtracted from the ranking score because that score is not projected FPL points.
    """
    owned_ids = {row.get("player_id") for row in squad}
    incoming_pool = [
        row
        for row in players
        if row.get("player_id") not in owned_ids and not row.get("is_owned")
    ]
    rejected: Counter[str] = Counter()
    evaluated_pairs = 0
    candidates: list[dict[str, Any]] = []

    for outgoing in squad:
        for incoming in incoming_pool:
            if incoming.get("position") != outgoing.get("position"):
                continue
            evaluated_pairs += 1
            legality = evaluate_single_transfer(
                squad,
                incoming,
                int(outgoing.get("player_id") or 0),
                bank_tenths=bank_tenths,
                free_transfers=free_transfers,
                transfers_made=transfers_made,
                active_chip=active_chip,
                rules=rules,
            )
            if not legality["is_legal"]:
                rejected.update(issue["code"] for issue in legality["issues"])
                continue

            deltas, ranking_score, confidence = _ranking_components(
                incoming,
                outgoing,
                decision_gameweek,
            )
            allowance = legality["transfer_allowance"]
            incremental_cost = int(allowance["incremental_cost_points"] or 0)
            if incremental_cost > 0:
                action = "HIT REVIEW"
            elif ranking_score >= 5.0 and confidence != "LOW":
                action = "CONSIDER"
            else:
                action = "LOW PRIORITY"

            candidates.append({
                "rank": None,
                "action": action,
                "confidence": confidence,
                "outgoing": _player_summary(outgoing, outgoing=True),
                "incoming": _player_summary(incoming, outgoing=False),
                "heuristic": {
                    "score": ranking_score,
                    "deltas": deltas,
                },
                "transfer_allowance": {
                    "uses_free_transfer": allowance["uses_free_transfer"],
                    "free_transfers_remaining_after": allowance[
                        "free_transfers_remaining_after"
                    ],
                    "incremental_cost_points": incremental_cost,
                    "active_chip": allowance["active_chip"],
                    "chip_makes_transfers_free": allowance["chip_makes_transfers_free"],
                },
                "money": legality["money"],
            })

    candidates.sort(
        key=lambda row: (
            _number((row.get("heuristic") or {}).get("score")),
            1 if row.get("confidence") == "HIGH" else 0,
        ),
        reverse=True,
    )
    bounded_limit = max(0, int(limit))
    candidates = candidates[:bounded_limit]
    for index, candidate in enumerate(candidates, start=1):
        candidate["rank"] = index

    return {
        "model": MODEL_VERSION,
        "season": rules.season,
        "is_available": True,
        "advisory_only": True,
        "reason": None,
        "weights": dict(WEIGHTS),
        "candidates": candidates,
        "evaluated_pairs": evaluated_pairs,
        "rejected_counts": dict(sorted(rejected.items())),
        "note": (
            "Ranking scores compare transparent football heuristics and are not projected FPL "
            "points. Any point-hit cost is reported separately and requires manager review."
        ),
    }
