"""Bounded observed activity and prospective, four-Gameweek transfer evaluation."""
from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Any

from .h2h import player_projected_points


PUBLIC_ACTIVITY_FIELDS = {
    "type", "player_id", "player", "club", "from_team", "to_team",
    "captured_at", "gameweek", "source",
}


def retain_activity(
    state: dict[str, Any], changes: list[dict[str, Any]], league: dict[str, Any],
    captured_at: str | None, gameweek: int | None,
) -> None:
    teams = {}
    for entry in league.get("league_entries") or league.get("entries") or []:
        for field in ("id", "entry_id", "entry"):
            if entry.get(field) is not None:
                teams[str(entry[field])] = entry.get("entry_name") or entry.get("short_name") or "League opponent"
    if "activity" not in state:
        # Only recover recorded adds/drops, never invent their counterparty or exact time.
        state["activity"] = []
        for manager in state.get("managers", {}).values():
            for transaction in manager.get("transactions", []):
                for direction in ("adds", "drops"):
                    for player in transaction.get(direction, []):
                        state["activity"].append({
                            "type": direction[:-1], "player_id": player.get("player_id"),
                            "player": player.get("player"),
                            "from_team": manager.get("team_name", "League opponent") if direction == "drops" else "Unknown previous owner",
                            "to_team": manager.get("team_name", "League opponent") if direction == "adds" else "Unknown next owner",
                            "captured_at": transaction.get("captured_at"),
                            "gameweek": transaction.get("gameweek"), "source": "retained manager record",
                        })
    def label(owner):
        return "Free pool" if owner is None else teams.get(str(owner), "League opponent")
    for change in changes:
        item = {key: change[key] for key in ("type", "player_id", "player", "club") if key in change}
        item.update(from_team=label(change.get("from_owner")), to_team=label(change.get("to_owner")),
                    captured_at=captured_at, gameweek=gameweek, source="ownership snapshot")
        if item not in state["activity"]:
            state["activity"].append(item)
    state["activity"] = sorted(state["activity"], key=lambda row: row.get("captured_at") or "")[-500:]


def freeze_transfer(
    adds: list[dict[str, Any]], drops: list[dict[str, Any]],
    players: dict[str, dict[str, Any]], gameweek: int | None,
) -> dict[str, Any]:
    """Freeze a same-position batch, without guessing individual transfer pairings."""
    eligible = bool(adds and drops and gameweek and len(adds) == len(drops)
                    and all(row.get("position") for row in adds + drops)
                    and Counter(row["position"] for row in adds) == Counter(row["position"] for row in drops))
    forecasts = {}
    if eligible:
        for gw in range(gameweek, min(gameweek + 4, 39)):
            rows = [players[str(row["player_id"])] for row in adds + drops]
            # Missing schedule coverage is not a blank Gameweek.
            if not all(any(f.get("gameweek") == gw for f in player.get("fixtures", [])) for player in rows):
                continue
            forecasts[str(gw)] = round(
                sum(player_projected_points(players[str(row["player_id"])], gw)["projected_points"] for row in adds)
                - sum(player_projected_points(players[str(row["player_id"])], gw)["projected_points"] for row in drops), 2)
    return {"evaluation_version": 1, "eligible": eligible, "expected_gains": forecasts, "observations": {}}


def completed_player_points(
    payloads: list[tuple[int, dict[str, Any]]], player_id_map: dict[int, int],
) -> dict[int, dict[str, float]]:
    """Accept only explicit final points, joining Standard to Draft by stable code."""
    output = {}
    for gameweek, payload in payloads:
        points = {}
        for element in payload.get("elements") or []:
            mapped = player_id_map.get(element.get("id"))
            value = (element.get("stats") or {}).get("total_points")
            if mapped is not None and isinstance(value, (int, float)) and isfinite(value):
                points[str(mapped)] = float(value)
        output[gameweek] = points
    return output


def evaluate_transfers(manager: dict[str, Any], completed_points: dict[int, dict[str, float]]) -> None:
    for transaction in manager.get("transactions", []):
        if transaction.get("evaluation_version") != 1 or not transaction.get("eligible"):
            continue
        if len(transaction.get("expected_gains", {})) < 4:
            transaction["outcome"] = {"status": "unrated", "reason": "Four original forecasts unavailable"}
            continue
        start = transaction["gameweek"]
        weeks = list(range(start, min(start + 4, 39)))
        adds = {str(row["player_id"]) for row in transaction["adds"]}
        drops = {str(row["player_id"]) for row in transaction["drops"]}
        observations = transaction.setdefault("observations", {})
        stopped = False
        for gw in weeks:
            ended = transaction.get("ended_gameweek")
            if ended is not None and gw >= ended:
                stopped = True
                break
            lineup = manager.get("lineups", {}).get(str(gw), {})
            squad = {str(pid) for pid in lineup.get("squad_ids", [])}
            if squad and (not adds <= squad or drops & squad):
                stopped = True
                break
            points = completed_points.get(gw, {})
            expected = transaction.get("expected_gains", {}).get(str(gw))
            if not squad or expected is None or not (adds | drops) <= points.keys():
                continue
            starters = {str(pid) for pid in lineup.get("starter_ids", [])}
            gain = sum(points[pid] for pid in adds) - sum(points[pid] for pid in drops)
            observations[str(gw)] = {
                "points_gain": gain, "expected_gain": expected,
                "excess_points": (gain - expected) * len(adds & starters) / len(adds),
                "incoming_started_points": sum(points[pid] for pid in adds & starters),
                "incoming_starts": len(adds & starters),
            }
        rows = [observations[str(week)] for week in weeks if str(week) in observations and (not stopped or week < gw)]
        complete = len(rows) == len(weeks) and len(weeks) == 4 and not stopped
        transaction["outcome"] = {
            "status": "complete" if complete else "stopped" if stopped else "pending",
            "observed_gameweeks": len(rows), "target_gameweeks": 4,
            "points_gain": round(sum(row["points_gain"] for row in rows), 1) if rows else None,
            "incoming_started_points": round(sum(row["incoming_started_points"] for row in rows), 1) if rows else None,
            "incoming_starts": sum(row["incoming_starts"] for row in rows),
            "excess_points_per_player_week": round(sum(row["excess_points"] for row in rows) / (len(rows) * len(adds)), 2) if rows else None,
        }


def public_transfer_reviews(history: dict[str, Any]) -> list[dict[str, Any]]:
    reviews = []
    for manager in history.get("managers", {}).values():
        for transaction in manager.get("transactions", []):
            reviews.append({
                "team_name": manager.get("team_name") or "League opponent",
                "captured_at": transaction.get("captured_at"), "gameweek": transaction.get("gameweek"),
                "adds": [row.get("player") or "Unknown player" for row in transaction.get("adds", [])],
                "drops": [row.get("player") or "Unknown player" for row in transaction.get("drops", [])],
                "decision_value": transaction.get("value_delta"),
                "outcome": transaction.get("outcome") or {"status": "unrated"},
            })
    return sorted(reviews, key=lambda row: row.get("captured_at") or "", reverse=True)[:100]
