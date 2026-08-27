from __future__ import annotations

from typing import Any

from .intelligence import is_hard_inactive
from .transfer_intel import transfer_action_rank


INJURY_STASH_MODEL = "v1.1"


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_health_concern(player: dict[str, Any]) -> bool:
    chance = player.get("chance_next_round")
    return chance is not None and _number(chance, 100.0) < 100 and not is_hard_inactive(player)


def _fixture_for_gameweek(player: dict[str, Any], gameweek: int | None) -> dict[str, Any] | None:
    if gameweek is None:
        return None
    for item in player.get("fixtures") or []:
        if int(_number(item.get("gameweek"), -1)) == int(gameweek):
            matches = [match for match in (item.get("matches") or []) if isinstance(match, dict)]
            if not matches:
                return {"gameweek": gameweek, "label": "Blank", "difficulty": None}
            labels = [
                f"{match.get('opponent') or '-'} ({match.get('venue') or '-'})"
                for match in matches
            ]
            difficulties = [
                _number(match.get("difficulty"), 3.0)
                for match in matches
            ]
            return {
                "gameweek": gameweek,
                "label": " + ".join(labels),
                "difficulty": round(sum(difficulties) / len(difficulties), 1),
            }
    return None


def _card(player: dict[str, Any], dashboard_action: str) -> dict[str, Any]:
    intel = player.get("intelligence") or {}
    replacement = player.get("replacement") or {}
    return_gameweek = intel.get("expected_return_gameweek")
    return {
        "player_id": player.get("player_id"),
        "player": player.get("player"),
        "club": player.get("club"),
        "team_code": player.get("team_code"),
        "position": player.get("position"),
        "chance_next_round": player.get("chance_next_round"),
        "news": player.get("news"),
        "dashboard_action": dashboard_action,
        "health_signal": intel.get("injury_return_signal"),
        "health_trend": intel.get("health_trend"),
        "expected_return": intel.get("expected_return"),
        "expected_return_gameweek": return_gameweek,
        "return_fixture": _fixture_for_gameweek(player, return_gameweek),
        "post_return_fixture_score": intel.get("post_return_fixture_score"),
        "stash_fixture_score": intel.get("stash_fixture_score"),
        "stash_score": intel.get("stash_score"),
        "recommendation": intel.get("recommendation"),
        "recommendation_reason": intel.get("recommendation_reason"),
        "waiver_action": replacement.get("action"),
        "drop_player": replacement.get("drop_player"),
        "combined_delta": replacement.get("combined_delta"),
        "confidence": replacement.get("confidence"),
        "transfer_intel": player.get("transfer_intel"),
    }


def _transfer_card(player: dict[str, Any], context: str) -> dict[str, Any]:
    intel = player.get("transfer_intel") or {}
    card = _card(player, str(intel.get("action") or "MOVE WATCH"))
    card.update({
        "context": context,
        "transfer_status": intel.get("status"),
        "move_kind": intel.get("move_kind"),
        "source_tier": intel.get("source_tier"),
        "destination": intel.get("destination"),
        "destination_fixture_score": intel.get("destination_fixture_score"),
        "current_fixture_score": intel.get("current_fixture_score"),
        "fixture_delta": intel.get("fixture_delta"),
        "role_outlook": intel.get("role_outlook"),
        "feed_synced": intel.get("feed_synced"),
        "blocks_selection": intel.get("blocks_selection"),
        "blocks_acquisition": intel.get("blocks_acquisition"),
        "transfer_summary": intel.get("summary"),
        "sources": intel.get("sources") or [],
        "expires_at": intel.get("expires_at"),
    })
    return card


def _candidate_action(player: dict[str, Any]) -> str | None:
    intel = player.get("intelligence") or {}
    replacement = player.get("replacement") or {}
    waiver_action = str(replacement.get("action") or "")
    standalone_action = str(intel.get("recommendation") or "")
    true_stash = bool(replacement.get("true_stash_candidate"))
    if true_stash and waiver_action in {"STASH SWAP", "SWAP NOW", "CONSIDER"}:
        return waiver_action
    if standalone_action == "STASH":
        return "STASH"

    fixture_opportunity = intel.get("post_return_fixture_score")
    if fixture_opportunity is None:
        fixture_opportunity = intel.get("future_fixture_score")
    if (
        standalone_action == "WATCH"
        and _number(intel.get("stash_score")) >= 55
        and _number(fixture_opportunity) >= 60
        and _number(replacement.get("combined_delta"), -999.0) >= -15
        and str(replacement.get("confidence") or "LOW") != "LOW"
    ):
        return "MONITOR"
    return None


def build_injury_stash_dashboard(
    my_squad: list[dict[str, Any]],
    available_players: list[dict[str, Any]],
    *,
    tracked_players: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    squad_health = [
        _card(player, str((player.get("intelligence") or {}).get("recommendation") or "HOLD"))
        for player in my_squad
        if _is_health_concern(player)
    ]
    squad_health.sort(key=lambda row: (_number(row.get("chance_next_round"), 100.0), -_number(row.get("stash_score"))))

    candidates = []
    for player in available_players:
        if not _is_health_concern(player):
            continue
        action = _candidate_action(player)
        if action:
            candidates.append(_card(player, action))
    action_rank = {"SWAP NOW": 5, "STASH SWAP": 4, "STASH": 3, "CONSIDER": 2, "MONITOR": 1}
    candidates.sort(key=lambda row: (
        -action_rank.get(str(row.get("dashboard_action")), 0),
        -_number(row.get("combined_delta"), -999.0),
        -_number(row.get("stash_score")),
    ))
    candidates = candidates[:4]

    return_rows = []
    candidate_ids = {row.get("player_id") for row in candidates}
    for player in [*my_squad, *available_players]:
        if not _is_health_concern(player):
            continue
        intel = player.get("intelligence") or {}
        if intel.get("expected_return_gameweek") is None:
            continue
        is_squad_player = any(str(row.get("player_id")) == str(player.get("player_id")) for row in my_squad)
        if not is_squad_player and player.get("player_id") not in candidate_ids and _number(intel.get("stash_score")) < 50:
            continue
        action = (
            str(intel.get("recommendation") or "HOLD")
            if is_squad_player
            else _candidate_action(player) or "NO MOVE"
        )
        return_rows.append(_card(player, action))
    return_rows.sort(key=lambda row: (
        int(_number(row.get("expected_return_gameweek"), 99)),
        -_number(row.get("post_return_fixture_score")),
    ))
    return_rows = return_rows[:6]

    active_watch_count = sum(
        1 for player in [*my_squad, *available_players] if _is_health_concern(player)
    )
    act_now = sum(
        1
        for row in candidates
        if row.get("dashboard_action") in {"SWAP NOW", "STASH SWAP", "STASH"}
    )
    my_ids = {str(player.get("player_id")) for player in my_squad}
    available_ids = {str(player.get("player_id")) for player in available_players}
    tracked = tracked_players if tracked_players is not None else [*my_squad, *available_players]
    transfer_rows = []
    seen_transfer_ids = set()
    for player in tracked:
        player_id = str(player.get("player_id"))
        if not player.get("transfer_intel") or player_id in seen_transfer_ids:
            continue
        seen_transfer_ids.add(player_id)
        if player_id in my_ids:
            context = "YOUR SQUAD"
        elif player_id in available_ids:
            context = "FREE AGENT"
        else:
            context = "OWNED ELSEWHERE"
        transfer_rows.append(_transfer_card(player, context))
    transfer_rows.sort(key=lambda row: (
        -transfer_action_rank({"transfer_intel": row.get("transfer_intel")}),
        -_number(row.get("destination_fixture_score"), -1.0),
        str(row.get("player") or ""),
    ))
    transfer_rows = transfer_rows[:8]
    early_pickups = [
        row for row in transfer_rows
        if row.get("context") == "FREE AGENT" and row.get("dashboard_action") == "EARLY PICKUP"
    ]
    return {
        "model": INJURY_STASH_MODEL,
        "available": True,
        "summary": {
            "squad_concerns": len(squad_health),
            "act_now": act_now,
            "monitor": len(candidates) - act_now,
            "dated_returns": len(return_rows),
            "decision_count": len(squad_health) + len(candidates),
            "active_watch_count": active_watch_count,
            "transfer_alerts": len(transfer_rows),
            "early_pickups": len(early_pickups),
        },
        "squad_health": squad_health,
        "stash_candidates": candidates,
        "return_calendar": return_rows,
        "transfer_watch": transfer_rows,
        "early_pickups": early_pickups,
        "note": "Only decision-relevant health and transfer cases are shown. Transfer reports expire automatically, and talks never change a score without stronger evidence.",
    }
