from __future__ import annotations

from collections import Counter
from typing import Any

from .intelligence import is_hard_inactive
from .optimizer import player_start_score
from .standard_fpl_rules import (
    RULES_2026_27,
    StandardFplRules,
    evaluate_single_transfer,
)


MODEL_VERSION = "standard-fpl-single-transfer-ranking-v0.1"
DECISION_MODEL_VERSION = "standard-fpl-hold-transfer-decision-v0.1"
CONSIDER_THRESHOLD = 5.0
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
    summary = {
        "player_id": player.get("player_id"),
        "player": player.get("player"),
        "club": player.get("club"),
        "team_id": player.get("team_id"),
        "position": player.get("position"),
        price_field: player.get(price_field),
    }
    if outgoing:
        summary["now_cost"] = player.get("now_cost")
    return summary


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
        and not is_hard_inactive(row)
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
            elif ranking_score >= CONSIDER_THRESHOLD and confidence != "LOW":
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


def _reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def build_transfer_decision(
    ranking: dict[str, Any],
    *,
    free_transfers: int,
    transfers_made: int,
    max_banked_free_transfers: int = RULES_2026_27.max_banked_free_transfers,
) -> dict[str, Any]:
    """Turn legal candidate rankings into one conservative, explained decision.

    The decision does not convert heuristic scores into points. A candidate must
    already be labelled CONSIDER by the ranker to displace HOLD.
    """
    if not ranking.get("is_available"):
        return {
            "model": DECISION_MODEL_VERSION,
            "is_available": False,
            "advisory_only": True,
            "recommendation": "UNAVAILABLE",
            "summary": "Hold-versus-transfer advice requires an exact private team snapshot.",
            "reasons": [_reason("private_state_required", str(ranking.get("reason") or UNAVAILABLE_REASON))],
            "candidate": None,
            "banking": None,
            "note": "No transfer, lineup or chip action is submitted to FPL.",
        }

    candidates = [row for row in ranking.get("candidates") or [] if isinstance(row, dict)]
    consider = next((row for row in candidates if row.get("action") == "CONSIDER"), None)
    candidate = consider or (candidates[0] if candidates else None)
    recommendation = "CONSIDER" if consider is not None else "HOLD"
    reasons: list[dict[str, str]] = []

    remaining_before = max(0, int(free_transfers) - int(transfers_made))
    can_bank = remaining_before < int(max_banked_free_transfers)
    banking = {
        "free_transfers_remaining_before": remaining_before,
        "maximum_banked_free_transfers": int(max_banked_free_transfers),
        "can_bank_if_unused": can_bank,
    }

    if candidate is None:
        reasons.append(_reason("no_legal_candidate", "No legal single-transfer candidate was found."))
    else:
        heuristic = candidate.get("heuristic") or {}
        deltas = heuristic.get("deltas") or {}
        score = _number(heuristic.get("score"))
        confidence = str(candidate.get("confidence") or "LOW")
        allowance = candidate.get("transfer_allowance") or {}
        cost = int(allowance.get("incremental_cost_points") or 0)
        incoming_name = str((candidate.get("incoming") or {}).get("player") or "the incoming player")
        outgoing_name = str((candidate.get("outgoing") or {}).get("player") or "the outgoing player")

        if recommendation == "CONSIDER":
            reasons.extend([
                _reason(
                    "clear_heuristic_upgrade",
                    f"{incoming_name} over {outgoing_name} improves the combined heuristic by {score:.1f}, "
                    f"above the {CONSIDER_THRESHOLD:.1f} review threshold.",
                ),
                _reason("sufficient_evidence", f"The comparison has {confidence.lower()} evidence confidence."),
                _reason("no_incremental_hit", "The move uses no additional point deduction."),
            ])
        else:
            if cost > 0:
                reasons.append(
                    _reason(
                        "point_hit_review",
                        f"The best shortlisted move costs {cost} points, while its heuristic score is not a points forecast.",
                    )
                )
            if score < CONSIDER_THRESHOLD:
                reasons.append(
                    _reason(
                        "below_upgrade_threshold",
                        f"The best legal move improves the combined heuristic by only {score:.1f}; "
                        f"the review threshold is {CONSIDER_THRESHOLD:.1f}.",
                    )
                )
            if confidence == "LOW":
                reasons.append(_reason("low_evidence", "The best comparison has low evidence confidence."))
            if _number(deltas.get("future_fixture")) <= 0:
                reasons.append(_reason("no_fixture_gain", "The alternative does not improve the future-fixture signal."))
            if _number(deltas.get("start")) <= 0:
                reasons.append(_reason("no_start_gain", "The alternative does not improve the next-Gameweek Start Score."))

        outgoing = candidate.get("outgoing") or {}
        selling_price = _number(outgoing.get("selling_price"), -1.0)
        current_price = _number(outgoing.get("now_cost"), -1.0)
        if selling_price >= 0 and current_price > selling_price:
            reasons.append(
                _reason(
                    "selling_value_at_risk",
                    f"Selling {outgoing_name} returns £{selling_price:.1f}m while the current market price is "
                    f"£{current_price:.1f}m, so buying the player back may cost more.",
                )
            )

    if recommendation == "HOLD" and can_bank:
        reasons.append(_reason("bank_transfer", "Leaving the transfer unused can add it to the next Gameweek allowance."))

    if recommendation == "CONSIDER" and candidate is not None:
        incoming = (candidate.get("incoming") or {}).get("player") or "incoming player"
        outgoing = (candidate.get("outgoing") or {}).get("player") or "outgoing player"
        summary = f"Consider {outgoing} to {incoming}; it is the strongest legal no-hit single transfer."
    elif candidate is not None:
        summary = "Hold: no legal, adequately evidenced, no-hit move clears the upgrade threshold."
    else:
        summary = "Hold: no legal single-transfer alternative was found."

    return {
        "model": DECISION_MODEL_VERSION,
        "is_available": True,
        "advisory_only": True,
        "recommendation": recommendation,
        "summary": summary,
        "reasons": reasons,
        "candidate": candidate,
        "banking": banking,
        "note": (
            "Heuristic improvements are not projected FPL points. The manager must review news, "
            "captaincy and wider plans before acting; no action is submitted."
        ),
    }
