from __future__ import annotations

from typing import Any

from .optimizer import player_start_score, recommend_lineup


POSITION_ORDER = {"GKP": 0, "DEF": 1, "MID": 2, "FWD": 3}
EDGE_THRESHOLD = 3.0
TACTICAL_WATCH_THRESHOLD = 3.0


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key) or []
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _entry_id(entry: dict[str, Any]) -> str | None:
    for key in ("entry_id", "entry"):
        if entry.get(key) is not None:
            return str(entry[key])
    return None


def _league_entry_id(entry: dict[str, Any]) -> str | None:
    return str(entry["id"]) if entry.get("id") is not None else None


def _find_entry(league_details: dict[str, Any], entry_id: str) -> dict[str, Any] | None:
    entries = _rows(league_details, "league_entries") or _rows(league_details, "entries")
    for entry in entries:
        if _entry_id(entry) == str(entry_id):
            return entry
    for entry in entries:
        if _league_entry_id(entry) == str(entry_id):
            return entry
    return None


def _entry_by_league_id(league_details: dict[str, Any], league_entry_id: str) -> dict[str, Any] | None:
    entries = _rows(league_details, "league_entries") or _rows(league_details, "entries")
    return next((entry for entry in entries if _league_entry_id(entry) == str(league_entry_id)), None)


def _match_side_ids(match: dict[str, Any]) -> tuple[str | None, str | None]:
    first = match.get("league_entry_1", match.get("entry_1"))
    second = match.get("league_entry_2", match.get("entry_2"))
    return (
        str(first) if first is not None else None,
        str(second) if second is not None else None,
    )


def _match_event(match: dict[str, Any]) -> int | None:
    value = match.get("event", match.get("gameweek"))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _find_match(league_details: dict[str, Any], own_league_entry_id: str, gameweek: int) -> dict[str, Any] | None:
    matches = _rows(league_details, "matches")
    involving = []
    for match in matches:
        first, second = _match_side_ids(match)
        if str(own_league_entry_id) not in {first, second}:
            continue
        event = _match_event(match)
        if event is None:
            continue
        involving.append((event, match))
    exact = [match for event, match in involving if event == int(gameweek)]
    if exact:
        return exact[0]
    future = [(event, match) for event, match in involving if event >= int(gameweek)]
    return min(future, key=lambda item: item[0])[1] if future else None


def _standing(league_details: dict[str, Any], league_entry_id: str) -> dict[str, Any]:
    for row in _rows(league_details, "standings"):
        candidate = row.get("league_entry", row.get("entry"))
        if candidate is not None and str(candidate) == str(league_entry_id):
            return {
                "rank": row.get("rank"),
                "h2h_points": row.get("total"),
                "points_for": row.get("points_for", row.get("event_total")),
            }
    return {"rank": None, "h2h_points": None, "points_for": None}


def _squad_for_entry(
    ownership: list[dict[str, Any]],
    league_entry_id: str | None,
    entry_id: str | None,
) -> list[dict[str, Any]]:
    result = []
    for row in ownership:
        raw_owner = row.get("owner_raw")
        public_owner = row.get("owner_entry_id")
        raw_match = league_entry_id is not None and raw_owner is not None and str(raw_owner) == str(league_entry_id)
        entry_match = entry_id is not None and public_owner is not None and str(public_owner) == str(entry_id)
        if raw_match or entry_match:
            result.append(row)
    return result


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _intel(player: dict[str, Any], key: str, default: float = 0.0) -> float:
    return _number((player.get("intelligence") or {}).get(key), default)


def _selection(player: dict[str, Any], key: str, default: float = 0.0) -> float:
    return _number((player.get("selection") or {}).get(key), default)


def _fixture_label(player: dict[str, Any], gameweek: int) -> str:
    for week in player.get("fixtures") or []:
        if int(week.get("gameweek") or 0) != int(gameweek):
            continue
        labels = [
            f"{match.get('opponent') or '-'} ({match.get('venue') or '-'})"
            for match in (week.get("matches") or [])
            if isinstance(match, dict)
        ]
        return " + ".join(labels) or "Blank"
    return "Blank"


def _signal(edge: float) -> str:
    if edge >= EDGE_THRESHOLD:
        return "EDGE"
    if edge <= -EDGE_THRESHOLD:
        return "TRAIL"
    return "EVEN"


def _lineup_summary(lineup: dict[str, Any]) -> dict[str, Any]:
    if not lineup.get("is_valid"):
        return {
            "formation": None,
            "average_start_score": 0.0,
            "average_roster_value": 0.0,
            "average_fixture_score": 0.0,
            "bench_start_score": 0.0,
            "evidence": "LOW",
        }
    starters = [row for row in lineup.get("starters") or [] if isinstance(row, dict)]
    bench = [row for row in lineup.get("bench") or [] if isinstance(row, dict)]
    reserve = lineup.get("reserve_goalkeeper")
    if isinstance(reserve, dict):
        bench.append(reserve)
    confidence = _mean([_selection(player, "sample_confidence", 0.0) for player in starters])
    evidence = "HIGH" if confidence >= 70 else "MEDIUM" if confidence >= 40 else "LOW"
    return {
        "formation": lineup.get("formation"),
        "average_start_score": round(_mean([_selection(player, "start_score") for player in starters]), 1),
        "average_roster_value": round(_mean([_intel(player, "roster_score") for player in starters]), 1),
        "average_fixture_score": round(_mean([_selection(player, "next_fixture") for player in starters]), 1),
        "bench_start_score": round(_mean([_selection(player, "start_score") for player in bench]), 1),
        "average_sample_confidence": round(confidence, 1),
        "evidence": evidence,
    }


def _position_edges(my_lineup: dict[str, Any], opponent_lineup: dict[str, Any]) -> list[dict[str, Any]]:
    my_starters = [row for row in my_lineup.get("starters") or [] if isinstance(row, dict)]
    opp_starters = [row for row in opponent_lineup.get("starters") or [] if isinstance(row, dict)]
    output = []
    for position in ("GKP", "DEF", "MID", "FWD"):
        mine = [row for row in my_starters if row.get("position") == position]
        theirs = [row for row in opp_starters if row.get("position") == position]
        if not mine and not theirs:
            continue
        my_start = _mean([_selection(player, "start_score") for player in mine])
        opp_start = _mean([_selection(player, "start_score") for player in theirs])
        my_fixture = _mean([_selection(player, "next_fixture") for player in mine])
        opp_fixture = _mean([_selection(player, "next_fixture") for player in theirs])
        edge = my_start - opp_start
        output.append({
            "position": position,
            "my_count": len(mine),
            "opponent_count": len(theirs),
            "my_start_score": round(my_start, 1),
            "opponent_start_score": round(opp_start, 1),
            "start_score_edge": round(edge, 1),
            "fixture_edge": round(my_fixture - opp_fixture, 1),
            "signal": _signal(edge),
        })
    output.sort(key=lambda row: POSITION_ORDER.get(str(row.get("position")), 99))
    return output


def _player_strength(player: dict[str, Any]) -> float:
    return 0.65 * _selection(player, "start_score") + 0.35 * _intel(player, "roster_score")


def _threat_rows(lineup: dict[str, Any], gameweek: int, limit: int = 3) -> list[dict[str, Any]]:
    starters = [row for row in lineup.get("starters") or [] if isinstance(row, dict)]
    ranked = sorted(starters, key=_player_strength, reverse=True)[:limit]
    return [
        {
            "player_id": player.get("player_id"),
            "player": player.get("player"),
            "position": player.get("position"),
            "club": player.get("club"),
            "team_code": player.get("team_code"),
            "start_score": round(_selection(player, "start_score"), 1),
            "roster_value": round(_intel(player, "roster_score"), 1),
            "fixture": _fixture_label(player, gameweek),
            "role_evidence": (player.get("selection") or {}).get("role_evidence"),
        }
        for player in ranked
    ]


def _best_available_counter(
    available_players: list[dict[str, Any]],
    my_squad: list[dict[str, Any]],
    position: str,
    gameweek: int,
) -> dict[str, Any] | None:
    owned = [player for player in my_squad if player.get("position") == position]
    available = [player for player in available_players if player.get("position") == position]
    if not owned or not available:
        return None
    ranked = []
    owned_by_id = {str(player.get("player_id")): player for player in owned}
    for player in available:
        score = player_start_score(player, gameweek)
        evidence = str(score.get("role_evidence") or "LOW").upper()
        replacement = player.get("replacement") or {}
        if evidence == "LOW" or _number(score.get("availability")) < 75 or replacement.get("action") == "KEEP ROSTER":
            continue
        drop = owned_by_id.get(str(replacement.get("drop_player_id")))
        if drop is None:
            drop = min(owned, key=lambda item: _number(player_start_score(item, gameweek).get("start_score")))
        drop_score = _number(player_start_score(drop, gameweek).get("start_score"))
        delta = _number(score.get("start_score")) - drop_score
        ranked.append((delta, _number(score.get("start_score")), player, score, drop, replacement))
    if not ranked:
        return None
    delta, candidate_score, candidate, score, drop, replacement = max(ranked, key=lambda item: (item[0], item[1]))
    if delta < TACTICAL_WATCH_THRESHOLD:
        return None
    return {
        "add_player_id": candidate.get("player_id"),
        "add_player": candidate.get("player"),
        "add_club": candidate.get("club"),
        "team_code": candidate.get("team_code"),
        "drop_player_id": drop.get("player_id"),
        "drop_player": drop.get("player"),
        "position": position,
        "start_score_delta": round(delta, 1),
        "candidate_start_score": round(candidate_score, 1),
        "role_evidence": score.get("role_evidence"),
        "replacement_action": replacement.get("action"),
    }


def _tactical_priorities(
    position_edges: list[dict[str, Any]],
    available_players: list[dict[str, Any]],
    my_squad: list[dict[str, Any]],
    gameweek: int,
) -> list[dict[str, Any]]:
    trailing = sorted(
        [row for row in position_edges if _number(row.get("start_score_edge")) <= -EDGE_THRESHOLD],
        key=lambda row: _number(row.get("start_score_edge")),
    )
    priorities = []
    for edge in trailing:
        position = str(edge.get("position") or "")
        counter = _best_available_counter(available_players, my_squad, position, gameweek)
        if counter:
            priorities.append({
                "action": "H2H WAIVER WATCH",
                "position": position,
                "reason": f"Opponent leads {position} by {abs(_number(edge.get('start_score_edge'))):.1f} Start Score; a fit, established free agent can improve your weakest {position} slot for this Gameweek.",
                "counter": counter,
            })
        else:
            priorities.append({
                "action": "LINEUP FOCUS",
                "position": position,
                "reason": f"Opponent leads {position} by {abs(_number(edge.get('start_score_edge'))):.1f} Start Score, but no evidence-backed free agent clears the tactical watch threshold.",
                "counter": None,
            })
    if not priorities:
        priorities.append({
            "action": "HOLD SHAPE",
            "position": None,
            "reason": "No position group trails the opponent by 3.0 Start Score or more. Avoid forcing a matchup-specific move without a clear roster upgrade.",
            "counter": None,
        })
    return priorities[:3]


def build_h2h_matchup(
    league_details: dict[str, Any],
    my_entry_id: str,
    my_squad: list[dict[str, Any]],
    ownership: list[dict[str, Any]],
    available_players: list[dict[str, Any]],
    gameweek: int,
    my_lineup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build opponent-aware next-Gameweek intelligence for an H2H Draft league.

    The comparison uses the same legal-XI Start Score heuristic for both teams.
    It deliberately does not output a win probability because Start Score is a
    normalized decision signal rather than a calibrated expected-points model.
    """
    my_entry = _find_entry(league_details, str(my_entry_id))
    if not my_entry:
        return {
            "model": "v0.8",
            "available": False,
            "gameweek": int(gameweek),
            "reason": "Could not map the configured Draft entry to a league entry.",
        }
    my_league_id = _league_entry_id(my_entry)
    if my_league_id is None:
        return {
            "model": "v0.8",
            "available": False,
            "gameweek": int(gameweek),
            "reason": "The league entry does not expose an internal H2H identifier.",
        }
    match = _find_match(league_details, my_league_id, int(gameweek))
    if not match:
        return {
            "model": "v0.8",
            "available": False,
            "gameweek": int(gameweek),
            "reason": "No upcoming H2H match was exposed by the league details payload.",
        }
    match_gameweek = _match_event(match) or int(gameweek)
    first, second = _match_side_ids(match)
    opponent_league_id = second if first == my_league_id else first
    if opponent_league_id is None:
        return {
            "model": "v0.8",
            "available": False,
            "gameweek": match_gameweek,
            "reason": "The upcoming H2H match did not expose an opponent league entry.",
        }
    opponent_entry = _entry_by_league_id(league_details, opponent_league_id) or {}
    opponent_entry_id = _entry_id(opponent_entry)
    opponent_squad = _squad_for_entry(ownership, opponent_league_id, opponent_entry_id)
    if len(opponent_squad) < 11:
        return {
            "model": "v0.8",
            "available": False,
            "gameweek": match_gameweek,
            "opponent": {
                "display_name": opponent_entry.get("entry_name") or opponent_entry.get("short_name") or "League opponent",
                "league_entry_id": opponent_league_id,
                "entry_id": opponent_entry_id,
                **_standing(league_details, opponent_league_id),
            },
            "reason": f"Opponent ownership resolved to only {len(opponent_squad)} players; a legal comparison would be unreliable.",
        }

    mine = my_lineup or recommend_lineup(my_squad, match_gameweek)
    theirs = recommend_lineup(opponent_squad, match_gameweek)
    if not mine.get("is_valid") or not theirs.get("is_valid"):
        return {
            "model": "v0.8",
            "available": False,
            "gameweek": match_gameweek,
            "reason": "A legal toolkit XI could not be generated for both sides.",
        }

    my_summary = _lineup_summary(mine)
    opponent_summary = _lineup_summary(theirs)
    start_edge = _number(my_summary.get("average_start_score")) - _number(opponent_summary.get("average_start_score"))
    roster_edge = _number(my_summary.get("average_roster_value")) - _number(opponent_summary.get("average_roster_value"))
    fixture_edge = _number(my_summary.get("average_fixture_score")) - _number(opponent_summary.get("average_fixture_score"))
    position_edges = _position_edges(mine, theirs)
    evidence_values = [my_summary.get("average_sample_confidence"), opponent_summary.get("average_sample_confidence")]
    evidence_floor = min(_number(value) for value in evidence_values)
    matchup_evidence = "HIGH" if evidence_floor >= 70 else "MEDIUM" if evidence_floor >= 40 else "LOW"

    return {
        "model": "v0.8",
        "available": True,
        "gameweek": match_gameweek,
        "opponent": {
            "display_name": opponent_entry.get("entry_name") or opponent_entry.get("short_name") or "League opponent",
            "league_entry_id": opponent_league_id,
            "entry_id": opponent_entry_id,
            **_standing(league_details, opponent_league_id),
        },
        "my_standing": _standing(league_details, my_league_id),
        "matchup": {
            "signal": _signal(start_edge),
            "start_score_edge": round(start_edge, 1),
            "roster_value_edge": round(roster_edge, 1),
            "fixture_edge": round(fixture_edge, 1),
            "evidence": matchup_evidence,
            "my": my_summary,
            "opponent": opponent_summary,
            "position_edges": position_edges,
        },
        "my_lineup": mine,
        "opponent_lineup": theirs,
        "opponent_squad": opponent_squad,
        "opponent_threats": _threat_rows(theirs, match_gameweek),
        "my_counterweights": _threat_rows(mine, match_gameweek),
        "tactical_priorities": _tactical_priorities(position_edges, available_players, my_squad, match_gameweek),
        "note": "Opponent XI is a toolkit estimate built with the same legal-lineup Start Score model as your Recommended XI. EDGE / EVEN / TRAIL is a relative heuristic, not a win probability or projected FPL score.",
    }
