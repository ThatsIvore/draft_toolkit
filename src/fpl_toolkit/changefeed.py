from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


ROLE_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
WAIVER_RANK = {"KEEP ROSTER": 1, "CONSIDER": 2, "STASH SWAP": 3, "SWAP NOW": 4}
PRIORITY_RANK = {"critical": 4, "important": 3, "watch": 2, "info": 1}
DECISION_STATE_VERSION = 3
CHANGE_FEED_MODEL = "v0.9.3"


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _players(report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = [*(report.get("my_squad") or []), *(report.get("available_players") or [])]
    return {
        int(row["player_id"]): row
        for row in rows
        if isinstance(row, dict) and row.get("player_id") is not None
    }


def _lineup_roles(report: dict[str, Any]) -> dict[int, str]:
    lineup = report.get("recommended_lineup") or {}
    roles: dict[int, str] = {}
    for row in lineup.get("starters") or []:
        if isinstance(row, dict) and row.get("player_id") is not None:
            roles[int(row["player_id"])] = "START"
    for row in lineup.get("bench") or []:
        if isinstance(row, dict) and row.get("player_id") is not None:
            roles[int(row["player_id"])] = "BENCH"
    reserve = lineup.get("reserve_goalkeeper")
    if isinstance(reserve, dict) and reserve.get("player_id") is not None:
        roles[int(reserve["player_id"])] = "BENCH"
    return roles


def _fixture_phase(player: dict[str, Any], gameweek: int | None) -> str:
    if gameweek in (None, 0):
        return "PRESEASON"
    matches: list[dict[str, Any]] = []
    for item in player.get("fixtures") or []:
        if not isinstance(item, dict) or int(item.get("gameweek") or 0) != int(gameweek):
            continue
        matches.extend(match for match in (item.get("matches") or []) if isinstance(match, dict))
    if not matches:
        return "BLANK"
    if any(bool(match.get("started")) for match in matches) and not all(bool(match.get("finished")) for match in matches):
        return "ACTIVE"
    if all(bool(match.get("finished")) for match in matches):
        return "FINISHED"
    return "SCHEDULED"


def _player_state(
    player: dict[str, Any],
    lineup_role: str | None = None,
    gameweek: int | None = None,
) -> dict[str, Any]:
    intel = player.get("intelligence") or {}
    replacement = player.get("replacement") or {}
    return {
        "player_id": int(player.get("player_id") or 0),
        "player": player.get("player"),
        "club": player.get("club"),
        "team_code": player.get("team_code"),
        "position": player.get("position"),
        "status": player.get("status"),
        "chance_next_round": player.get("chance_next_round"),
        "news": player.get("news"),
        "availability_score": intel.get("availability_score"),
        "expected_minutes": intel.get("expected_minutes"),
        "role_evidence": intel.get("role_evidence"),
        "health_trend": intel.get("health_trend"),
        "recommendation": intel.get("recommendation"),
        "roster_score": intel.get("roster_score"),
        "stash_score": intel.get("stash_score"),
        "waiver_action": replacement.get("action"),
        "waiver_drop_player": replacement.get("drop_player"),
        "waiver_delta": replacement.get("combined_delta"),
        "lineup_role": lineup_role,
        "fixture_phase": _fixture_phase(player, gameweek),
    }


def capture_decision_state(report: dict[str, Any]) -> dict[str, Any]:
    roles = _lineup_roles(report)
    players = _players(report)
    h2h = report.get("h2h_matchup") or {}
    planner = report.get("schedule_planner") or {}
    gameweek = report.get("current_gameweek")
    return {
        "schema_version": DECISION_STATE_VERSION,
        "captured_at": report.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "gameweek": gameweek,
        "players": {
            str(player_id): _player_state(player, roles.get(player_id), gameweek)
            for player_id, player in players.items()
        },
        "recommended_formation": (report.get("recommended_lineup") or {}).get("formation"),
        "toughest_gameweek": planner.get("weakest_gameweek"),
        "h2h_signal": ((h2h.get("matchup") or {}).get("signal") if h2h.get("available") else None),
        "h2h_start_edge": ((h2h.get("matchup") or {}).get("start_score_edge") if h2h.get("available") else None),
        "outcome_diagnostics": report.get("outcome_diagnostics"),
    }


def _item(
    kind: str,
    priority: str,
    title: str,
    detail: str,
    *,
    player: dict[str, Any] | None = None,
    badge: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "priority": priority,
        "title": title,
        "detail": detail,
        "badge": badge or kind.replace("_", " ").upper(),
        "player_id": player.get("player_id") if player else None,
        "player": player.get("player") if player else None,
        "club": player.get("club") if player else None,
        "team_code": player.get("team_code") if player else None,
        "position": player.get("position") if player else None,
    }


def _player_changes(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    suppress_model_changes: bool = False,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    name = str(current.get("player") or previous.get("player") or "Player")
    transient_match_data = suppress_model_changes or "ACTIVE" in {
        str(previous.get("fixture_phase") or ""),
        str(current.get("fixture_phase") or ""),
    }

    old_role = previous.get("lineup_role")
    new_role = current.get("lineup_role")
    if not transient_match_data and old_role and new_role and old_role != new_role:
        direction = "BENCH → START" if new_role == "START" else "START → BENCH"
        priority = "important" if new_role == "START" else "watch"
        events.append(_item(
            "lineup_change", priority, f"{name}: {direction}",
            "Recommended XI changed since the previous collection.", player=current,
            badge="NEW START" if new_role == "START" else "BENCHED",
        ))

    old_avail = _number(previous.get("availability_score"), 100.0)
    new_avail = _number(current.get("availability_score"), 100.0)
    avail_delta = new_avail - old_avail
    if abs(avail_delta) >= 20:
        improving = avail_delta > 0
        events.append(_item(
            "availability", "important" if not improving else "watch",
            f"{name}: availability {'improved' if improving else 'fell'}",
            f"Availability Score {old_avail:.0f} → {new_avail:.0f} ({avail_delta:+.0f}).",
            player=current, badge="↑ FIT" if improving else "↓ FIT",
        ))
    elif str(previous.get("news") or "").strip() != str(current.get("news") or "").strip() and current.get("news"):
        events.append(_item(
            "player_news", "watch", f"{name}: player news changed",
            str(current.get("news") or "New official player update."), player=current, badge="NEWS",
        ))

    old_evidence = str(previous.get("role_evidence") or "LOW").upper()
    new_evidence = str(current.get("role_evidence") or "LOW").upper()
    old_minutes = _number(previous.get("expected_minutes"))
    new_minutes = _number(current.get("expected_minutes"))
    if not transient_match_data and old_evidence != new_evidence:
        improved = ROLE_RANK.get(new_evidence, 0) > ROLE_RANK.get(old_evidence, 0)
        events.append(_item(
            "role_change", "important" if improved else "watch",
            f"{name}: role evidence {old_evidence} → {new_evidence}",
            f"Expected-minutes heuristic is now {new_minutes:.0f} minutes.",
            player=current, badge="↑ ROLE" if improved else "↓ ROLE",
        ))
    elif not transient_match_data and abs(new_minutes - old_minutes) >= 10:
        improving = new_minutes > old_minutes
        events.append(_item(
            "minutes_change", "watch", f"{name}: expected minutes {'rose' if improving else 'fell'}",
            f"Expected-minutes heuristic {old_minutes:.0f} → {new_minutes:.0f}.",
            player=current, badge="↑ MIN" if improving else "↓ MIN",
        ))

    old_action = previous.get("waiver_action")
    new_action = current.get("waiver_action")
    if not transient_match_data and old_action and new_action and old_action != new_action:
        stronger = WAIVER_RANK.get(str(new_action), 0) > WAIVER_RANK.get(str(old_action), 0)
        priority = "critical" if new_action == "SWAP NOW" else "important" if stronger else "watch"
        drop = current.get("waiver_drop_player")
        delta = current.get("waiver_delta")
        extra = f" Best comparison: drop {drop}." if drop else ""
        if delta is not None:
            extra += f" Combined delta {_number(delta):+.1f}."
        events.append(_item(
            "waiver_change", priority, f"{name}: {old_action} → {new_action}",
            f"Waiver recommendation changed since the previous collection.{extra}",
            player=current, badge="WAIVER ↑" if stronger else "WAIVER ↓",
        ))

    old_rec = previous.get("recommendation")
    new_rec = current.get("recommendation")
    if not transient_match_data and old_rec and new_rec and old_rec != new_rec and not new_action:
        events.append(_item(
            "recommendation_change", "watch", f"{name}: {old_rec} → {new_rec}",
            "Standalone player recommendation changed.", player=current, badge="DECISION",
        ))
    return events


def build_change_feed(
    previous_state: dict[str, Any] | None,
    report: dict[str, Any],
    league_activity: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current_state = capture_decision_state(report)
    if not previous_state or not isinstance(previous_state.get("players"), dict):
        return {
            "model": CHANGE_FEED_MODEL,
            "baseline": True,
            "since": None,
            "items": [],
            "changed_player_ids": [],
            "summary": {"critical": 0, "important": 0, "watch": 0, "info": 0},
            "note": "Decision-change baseline captured. Future collections will compare against this snapshot.",
        }
    events: list[dict[str, Any]] = []
    baseline_refresh = previous_state.get("schema_version") != DECISION_STATE_VERSION
    old_gameweek = previous_state.get("gameweek")
    new_gameweek = current_state.get("gameweek")
    gameweek_changed = (
        not baseline_refresh
        and
        old_gameweek is not None
        and new_gameweek is not None
        and int(old_gameweek) != int(new_gameweek)
    )
    previous_players = previous_state.get("players") or {}
    current_players = current_state.get("players") or {}
    live_model_data = any(
        str(player.get("fixture_phase") or "") == "ACTIVE"
        for player in [*previous_players.values(), *current_players.values()]
        if isinstance(player, dict)
    )
    if baseline_refresh:
        pass
    elif gameweek_changed:
        events.append(_item(
            "gameweek_rollover", "info", f"Gameweek {new_gameweek} decision baseline started",
            f"GW{old_gameweek} model movements were closed without carrying transition noise into the new planning window.",
            badge="NEW GAMEWEEK",
        ))
    else:
        for player_id, current in current_players.items():
            previous = previous_players.get(str(player_id))
            if isinstance(previous, dict):
                events.extend(_player_changes(
                    previous,
                    current,
                    suppress_model_changes=live_model_data,
                ))

    previous_outcome = (previous_state.get("outcome_diagnostics") or {}).get("current") or {}
    current_outcome = (report.get("outcome_diagnostics") or {}).get("current") or {}
    if (
        current_outcome.get("phase") == "FINAL"
        and previous_outcome.get("phase") != "FINAL"
        and current_outcome.get("gameweek") is not None
    ):
        actual = current_outcome.get("actual") or {}
        forecast = current_outcome.get("forecast") or {}
        recommended = forecast.get("recommended") or {}
        official_points = actual.get("official_points")
        detail = (
            f"Official XI: {_number(official_points):.0f} points. " if official_points is not None else ""
        )
        detail += (
            f"Toolkit XI: {_number(actual.get('recommended_points')):.0f} actual versus "
            f"{_number(recommended.get('projected_total')):.1f} projected. "
            f"H2H: {_number(actual.get('h2h_my_points')):.0f}–{_number(actual.get('h2h_opponent_points')):.0f}."
        )
        events.append(_item(
            "gameweek_result", "info", f"GW{current_outcome['gameweek']} result captured",
            detail, badge="GW FINAL",
        ))

    for activity in league_activity or []:
        if not isinstance(activity, dict) or activity.get("type") != "drop":
            continue
        player_id = activity.get("player_id")
        current = current_players.get(str(player_id)) or {
            "player_id": player_id,
            "player": activity.get("player"),
            "club": activity.get("club"),
        }
        action = current.get("waiver_action")
        decision = f" Current waiver action: {action}." if action else ""
        events.append(_item(
            "opponent_drop", "important" if action in {"SWAP NOW", "STASH SWAP", "CONSIDER"} else "watch",
            f"{current.get('player') or 'Player'} entered the free pool",
            f"A league roster released this player.{decision}", player=current, badge="NEW FREE AGENT",
        ))

    old_toughest = previous_state.get("toughest_gameweek")
    new_toughest = current_state.get("toughest_gameweek")
    if not baseline_refresh and not gameweek_changed and not live_model_data and old_toughest is not None and new_toughest is not None and int(old_toughest) != int(new_toughest):
        events.append(_item(
            "planning_change", "watch", f"Toughest upcoming GW moved to GW{new_toughest}",
            f"The four-Gameweek planner previously identified GW{old_toughest}.", badge="PLANNER",
        ))

    old_h2h = previous_state.get("h2h_signal")
    new_h2h = current_state.get("h2h_signal")
    if not baseline_refresh and not gameweek_changed and not live_model_data and old_h2h and new_h2h and old_h2h != new_h2h:
        edge = _number(current_state.get("h2h_start_edge"))
        events.append(_item(
            "h2h_change", "important" if new_h2h == "TRAIL" else "watch",
            f"H2H signal changed {old_h2h} → {new_h2h}",
            f"Current relative Start Score edge is {edge:+.1f}.", badge="H2H",
        ))

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for event in events:
        key = (event.get("kind"), event.get("player_id"), event.get("title"))
        if key not in seen:
            seen.add(key)
            deduped.append(event)
    deduped.sort(
        key=lambda event: (PRIORITY_RANK.get(str(event.get("priority")), 0), event.get("player_id") is not None),
        reverse=True,
    )
    summary = {key: 0 for key in ("critical", "important", "watch", "info")}
    for event in deduped:
        priority = str(event.get("priority") or "info")
        summary[priority] = summary.get(priority, 0) + 1
    return {
        "model": CHANGE_FEED_MODEL,
        "baseline": baseline_refresh,
        "since": previous_state.get("captured_at"),
        "items": deduped[:40],
        "changed_player_ids": sorted({int(event["player_id"]) for event in deduped if event.get("player_id") is not None}),
        "summary": summary,
        "note": (
            "Decision baseline refreshed to suppress transient live-match changes."
            if baseline_refresh
            else "Only material decision changes are surfaced; small score noise is intentionally suppressed."
        ),
    }
