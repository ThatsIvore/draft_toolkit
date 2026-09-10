from __future__ import annotations

from typing import Any
from .transfer_intel import transfer_blocks_acquisition


def _score(player: dict[str, Any], key: str) -> float:
    try:
        return float((player.get("intelligence") or {}).get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _immediate_value(player: dict[str, Any]) -> float:
    intel = player.get("intelligence") or {}
    try:
        usage = float(intel.get("usage_score") or 0.0)
        fixture = float(intel.get("fixture_score") or 0.0)
        availability = float(intel.get("availability_score") or 0.0)
        floor = float(intel.get("floor_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return 0.35 * usage + 0.25 * fixture + 0.15 * availability + 0.25 * floor


def _confidence_label(available: dict[str, Any], owned: dict[str, Any], combined: float) -> str:
    sample = min(_score(available, "sample_confidence"), _score(owned, "sample_confidence"))
    if sample >= 70 and abs(combined) >= 10:
        return "HIGH"
    if sample >= 40 and abs(combined) >= 5:
        return "MEDIUM"
    return "LOW"


def _is_true_stash_candidate(player: dict[str, Any]) -> bool:
    intel = player.get("intelligence") or {}
    availability = _score(player, "availability_score")
    return_signal = str(intel.get("injury_return_signal") or "fit")
    return availability < 100 or return_signal in {"out", "return-watch", "near-return"}


def attach_replacement_analysis(
    available_players: list[dict[str, Any]],
    my_squad: list[dict[str, Any]],
    current_gameweek: int | None = None,
) -> list[dict[str, Any]]:
    """Compare each free agent with the best same-position roster replacement.

    Pairwise comparisons remain diagnostic. v0.6.0 then applies evidence,
    timing and value guards and chooses one lead per outgoing player.
    """
    by_position: dict[str, list[dict[str, Any]]] = {}
    for player in my_squad:
        by_position.setdefault(str(player.get("position") or ""), []).append(player)

    preseason = current_gameweek in (None, 0)
    output: list[dict[str, Any]] = []
    for available in available_players:
        row = dict(available)
        candidates = by_position.get(str(row.get("position") or ""), [])
        if not candidates:
            row["replacement"] = None
            output.append(row)
            continue

        comparisons = []
        for owned in candidates:
            roster_delta = _score(row, "roster_score") - _score(owned, "roster_score")
            future_delta = _score(row, "stash_score") - _score(owned, "stash_score")
            immediate_delta = _immediate_value(row) - _immediate_value(owned)
            floor_delta = _score(row, "floor_score") - _score(owned, "floor_score")
            upside_delta = _score(row, "upside_score") - _score(owned, "upside_score")
            combined = 0.32 * roster_delta + 0.25 * immediate_delta + 0.18 * future_delta + 0.15 * floor_delta + 0.10 * upside_delta
            comparisons.append((combined, roster_delta, immediate_delta, future_delta, floor_delta, upside_delta, owned))

        combined, roster_delta, immediate_delta, future_delta, floor_delta, upside_delta, owned = max(comparisons, key=lambda item: item[0])
        confidence = _confidence_label(row, owned, combined)
        true_stash = _is_true_stash_candidate(row)

        swap_threshold = 16.0 if preseason else 10.0
        consider_threshold = 5.0 if preseason else 3.0
        if combined >= swap_threshold and immediate_delta >= 2 and floor_delta >= 0 and confidence != "LOW":
            action = "SWAP NOW"
        elif true_stash and combined >= (10.0 if preseason else 7.0) and future_delta > immediate_delta and upside_delta > 0 and confidence != "LOW":
            action = "STASH SWAP"
        elif combined >= consider_threshold:
            action = "CONSIDER"
        else:
            action = "KEEP ROSTER"

        row["replacement"] = {
            "model": "v0.5.1",
            "drop_player_id": owned.get("player_id"),
            "drop_player": owned.get("player"),
            "drop_club": owned.get("club"),
            "position": row.get("position"),
            "roster_delta": round(roster_delta, 1),
            "immediate_delta": round(immediate_delta, 1),
            "future_delta": round(future_delta, 1),
            "floor_delta": round(floor_delta, 1),
            "upside_delta": round(upside_delta, 1),
            "combined_delta": round(combined, 1),
            "confidence": confidence,
            "preseason_guardrail": preseason,
            "true_stash_candidate": true_stash,
            "action": action,
        }
        output.append(row)
    return _prioritize_moves(output, my_squad, current_gameweek)


def _prioritize_moves(players, squad, gameweek):
    """One urgent lead per outgoing player; scores alone do not imply urgency."""
    owned = {p.get("player_id"): p for p in squad}
    groups = {}
    improving_alternatives = {}
    for player in players:
        r = player.get("replacement")
        if not r:
            continue
        r["comparison_action"] = r["action"]
        r["model"] = "v0.6.0"
        r["policy_revision"] = "20260910.2"
        r["action"] = "CONSIDER" if r["combined_delta"] >= (5 if gameweek in (None, 0) else 3) else "HOLD / WATCH"
        r["reason"] = "Potential improvement, but no sufficiently strong, timely transfer clears the priority checks." if r["action"] == "CONSIDER" else "No compelling improvement over the current roster."
        drop = owned[r["drop_player_id"]]
        fixtures = [m for week in player.get("fixtures") or [] if week.get("gameweek") == gameweek for m in week.get("matches") or []]
        # Preserve production value: an injury penalty alone must not justify
        # sacrificing a substantially stronger long-term player.
        production_ok = _score(player, "baseline_score") >= _score(drop, "baseline_score") - 5
        usable = (_score(player, "availability_score") == 100 and _score(player, "expected_minutes") >= 65
                  and bool(fixtures) and not transfer_blocks_acquisition(player))
        timely = (_score(drop, "availability_score") <= 50 or
                  (_score(player, "expected_minutes") - _score(drop, "expected_minutes") >= 15
                   and r["immediate_delta"] >= 15))
        recent = (player.get("intelligence") or {}).get("recent_match_evidence") or {}
        improving = (not production_ok and _score(player, "baseline_score") >= _score(drop, "baseline_score") - 10
                     and recent.get("status") == "available" and float(recent.get("confidence") or 0) >= 70
                     and int(recent.get("completed_gameweeks") or 0) >= 3
                     and float(recent.get("minutes") or 0) >= 240 and float(recent.get("score") or 0) >= 70)
        checks = [
            (gameweek not in (None, 0), "Priority moves are not issued before the season."),
            (r["combined_delta"] >= 20, "Overall improvement is below the priority threshold of 20 heuristic points."),
            (r["confidence"] == "HIGH", "Comparison evidence is not HIGH."),
            (r["floor_delta"] >= 0, "The move reduces the projected floor."),
            (r["future_delta"] >= 0, "The move reduces four-Gameweek roster value."),
            (production_ok, f"Production baseline {_score(player, 'baseline_score'):.1f} versus {_score(drop, 'baseline_score'):.1f}: more than 5 points lower."),
            (_score(player, "availability_score") == 100, "Incoming player is not fully available."),
            (_score(player, "expected_minutes") >= 65, "Expected minutes are below 65."),
            (bool(fixtures), "No fixture in the decision Gameweek."),
            (timely, "No urgent availability or playing-time weakness to address."),
        ]
        failures = [reason for passed, reason in checks if not passed]
        r["priority_checks_failed"] = failures
        if failures:
            r["reason"] = " ".join(failures)
        qualifies = (gameweek not in (None, 0) and r["combined_delta"] >= 20 and r["confidence"] == "HIGH"
                     and r["floor_delta"] >= 0 and r["future_delta"] >= 0 and production_ok and usable and timely)
        otherwise_qualified = all(passed for i, (passed, _) in enumerate(checks) if i != 5) and usable
        if improving and otherwise_qualified:
            improving_alternatives.setdefault(r["drop_player_id"], []).append(player)
            r["reason"] += " Strong recent evidence supports a fallback only when a fully qualified priority exists."
        if qualifies:
            groups.setdefault(r["drop_player_id"], []).append(player)
        if transfer_blocks_acquisition(player):
            r["action"] = "HOLD / WATCH"
            r["reason"] = "Player is blocked from acquisition."
    for drop_id, candidates in groups.items():
        candidates.sort(key=lambda p: (-p["replacement"]["combined_delta"], str(p.get("player")), p["player_id"]))
        lead = candidates[0]
        candidates += improving_alternatives.get(drop_id, [])
        candidates = [lead] + sorted(candidates[1:], key=lambda p: (-p["replacement"]["combined_delta"], str(p.get("player")), p["player_id"]))
        for rank, player in enumerate(candidates, 1):
            r = player["replacement"]
            r.update(group_rank=rank, lead_player_id=lead["player_id"], lead_player=lead["player"],
                     action="PRIORITY MOVE" if rank == 1 else "ALTERNATIVE")
            r["reason"] = ("Strong improvement with high evidence and usable minutes this week; addresses an availability or playing-time weakness."
                           if rank == 1 else f"Fallback to {lead['player']} for the same outgoing player; choose one of these moves.")
            if r["priority_checks_failed"]:
                r["reason"] += " " + " ".join(r["priority_checks_failed"]) + " Strong recent evidence supports this alternative, but does not clear the priority safeguard."
    return players
