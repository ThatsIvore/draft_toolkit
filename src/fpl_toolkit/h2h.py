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


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


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


def _match_result(match: dict[str, Any], my_league_id: str, phase: str) -> dict[str, Any]:
    first, _ = _match_side_ids(match)
    mine_key = "league_entry_1_points" if first == str(my_league_id) else "league_entry_2_points"
    opponent_key = "league_entry_2_points" if first == str(my_league_id) else "league_entry_1_points"
    return {
        "status": phase,
        "source": "league_details",
        "my_points": _number(match.get(mine_key)),
        "opponent_points": _number(match.get(opponent_key)),
        "finished": bool(match.get("finished")) or phase == "FINAL",
    }


def _find_match(league_details: dict[str, Any], own_league_entry_id: str, gameweek: int) -> dict[str, Any] | None:
    involving = []
    for match in _rows(league_details, "matches"):
        first, second = _match_side_ids(match)
        if str(own_league_entry_id) not in {first, second}:
            continue
        event = _match_event(match)
        if event is not None:
            involving.append((event, match))
    exact = [match for event, match in involving if event == int(gameweek)]
    if exact:
        return exact[0]
    future = [(event, match) for event, match in involving if event >= int(gameweek)]
    return min(future, key=lambda item: item[0])[1] if future else None


def _find_exact_match(league_details: dict[str, Any], own_league_entry_id: str, gameweek: int) -> dict[str, Any] | None:
    for match in _rows(league_details, "matches"):
        first, second = _match_side_ids(match)
        if str(own_league_entry_id) in {first, second} and _match_event(match) == int(gameweek):
            return match
    return None


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


def _manager_profile(
    profiles: dict[str, dict[str, Any]] | None,
    league_entry_id: str | None,
    entry_id: str | None,
) -> dict[str, Any] | None:
    if not profiles:
        return None
    for candidate in (entry_id, league_entry_id):
        if candidate is not None and isinstance(profiles.get(str(candidate)), dict):
            return profiles[str(candidate)]
    return None


def _apply_decision_adjustment(projection: dict[str, Any], profile: dict[str, Any] | None) -> float:
    threat = (profile or {}).get("decision_threat") or {}
    adjustment = _clamp(_number(threat.get("projected_points_adjustment")), -2.0, 2.0)
    if not adjustment:
        return 0.0
    projection["roster_total"] = projection.get("total")
    projection["decision_adjustment"] = round(adjustment, 1)
    projection["total"] = round(_number(projection.get("total")) + adjustment, 1)
    if projection.get("range_low") is not None:
        projection["range_low"] = round(max(0.0, _number(projection.get("range_low")) + adjustment), 1)
    if projection.get("range_high") is not None:
        projection["range_high"] = round(max(0.0, _number(projection.get("range_high")) + adjustment), 1)
    return round(adjustment, 1)


def player_projected_points(player: dict[str, Any], gameweek: int) -> dict[str, Any]:
    """Estimate next-GW FPL points from the toolkit's existing evidence.

    This is intentionally a conservative first-generation projection, not a
    calibrated probability model. It converts blended historical/live points
    per 90 into expected playing-time points, then applies a bounded fixture
    modifier and current availability. The displayed range widens when role
    evidence is thin. It must not be interpreted as a statistical confidence
    interval or win probability.
    """
    score = player_start_score(player, gameweek)
    points_per_90 = max(0.0, _intel(player, "points_per_90"))
    expected_minutes = _clamp(_number(score.get("expected_minutes")), 0.0, 90.0)
    availability = _clamp(_number(score.get("availability"), 100.0), 0.0, 100.0)
    fixture_score = _clamp(_number(score.get("next_fixture"), 60.0), 0.0, 100.0)
    confidence = _clamp(_number(score.get("sample_confidence"), 0.0), 0.0, 100.0)

    fixture_multiplier = _clamp(1.0 + (fixture_score - 60.0) / 250.0, 0.78, 1.16)
    availability_factor = 0.25 + 0.75 * availability / 100.0
    central = points_per_90 * expected_minutes / 90.0 * fixture_multiplier * availability_factor
    if _fixture_label(player, gameweek) == "Blank":
        central = 0.0

    uncertainty = 0.32 + 0.38 * (1.0 - confidence / 100.0)
    half_width = max(1.2, central * uncertainty)
    low = max(0.0, central - half_width)
    high = central + half_width
    return {
        "projected_points": round(central, 1),
        "range_low": round(low, 1),
        "range_high": round(high, 1),
        "points_per_90": round(points_per_90, 2),
        "expected_minutes": round(expected_minutes, 1),
        "fixture_multiplier": round(fixture_multiplier, 3),
        "availability": round(availability, 1),
        "sample_confidence": round(confidence, 1),
        "role_evidence": score.get("role_evidence"),
    }


def _lineup_projection(lineup: dict[str, Any], gameweek: int) -> dict[str, Any]:
    starters = [row for row in lineup.get("starters") or [] if isinstance(row, dict)]
    rows = []
    for player in starters:
        projection = player_projected_points(player, gameweek)
        rows.append({
            "player_id": player.get("player_id"),
            "player": player.get("player"),
            "position": player.get("position"),
            **projection,
        })
    central = sum(_number(row.get("projected_points")) for row in rows)
    low = sum(_number(row.get("range_low")) for row in rows)
    high = sum(_number(row.get("range_high")) for row in rows)
    return {
        "total": round(central, 1),
        "range_low": round(low, 1),
        "range_high": round(high, 1),
        "players": rows,
        "note": "Point range is an uncertainty band from player-level role evidence; it is not a calibrated statistical interval.",
    }


def _lineup_summary(lineup: dict[str, Any], gameweek: int) -> dict[str, Any]:
    if not lineup.get("is_valid"):
        return {
            "formation": None,
            "average_start_score": 0.0,
            "average_roster_value": 0.0,
            "average_fixture_score": 0.0,
            "bench_start_score": 0.0,
            "evidence": "LOW",
            "projection": {"total": 0.0, "range_low": 0.0, "range_high": 0.0, "players": []},
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
        "projection": _lineup_projection(lineup, gameweek),
    }


def _position_edges(my_lineup: dict[str, Any], opponent_lineup: dict[str, Any], gameweek: int) -> list[dict[str, Any]]:
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
        my_points = sum(_number(player_projected_points(player, gameweek).get("projected_points")) for player in mine)
        opp_points = sum(_number(player_projected_points(player, gameweek).get("projected_points")) for player in theirs)
        edge = my_start - opp_start
        output.append({
            "position": position,
            "my_count": len(mine),
            "opponent_count": len(theirs),
            "my_start_score": round(my_start, 1),
            "opponent_start_score": round(opp_start, 1),
            "start_score_edge": round(edge, 1),
            "fixture_edge": round(my_fixture - opp_fixture, 1),
            "projected_points_edge": round(my_points - opp_points, 1),
            "my_projected_points": round(my_points, 1),
            "opponent_projected_points": round(opp_points, 1),
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
            "projected_points": player_projected_points(player, gameweek)["projected_points"],
            "fixture": _fixture_label(player, gameweek),
            "role_evidence": (player.get("selection") or {}).get("role_evidence"),
        }
        for player in ranked
    ]


def _scouting_report(squad: list[dict[str, Any]], lineup: dict[str, Any], gameweek: int) -> dict[str, Any]:
    starters = [row for row in lineup.get("starters") or [] if isinstance(row, dict)]
    bench = [row for row in lineup.get("bench") or [] if isinstance(row, dict)]
    reserve = lineup.get("reserve_goalkeeper")
    if isinstance(reserve, dict):
        bench.append(reserve)
    position_strength = []
    for position in ("GKP", "DEF", "MID", "FWD"):
        rows = [player for player in starters if player.get("position") == position]
        if rows:
            position_strength.append((position, _mean([_selection(player, "start_score") for player in rows])))
    strongest = max(position_strength, key=lambda row: row[1])[0] if position_strength else None
    weakest = min(position_strength, key=lambda row: row[1])[0] if position_strength else None
    weakest_starter = min(starters, key=_player_strength) if starters else None
    low_evidence = sum(1 for player in starters if str((player.get("selection") or {}).get("role_evidence") or "LOW") != "HIGH")
    unavailable = sum(1 for player in squad if _intel(player, "availability_score", 100.0) < 75.0)
    bench_avg = _mean([_selection(player, "start_score") for player in bench])
    depth = "STRONG" if bench_avg >= 78 else "AVERAGE" if bench_avg >= 65 else "THIN"
    return {
        "strongest_group": strongest,
        "weakest_group": weakest,
        "bench_depth": depth,
        "bench_start_score": round(bench_avg, 1),
        "non_high_evidence_starters": low_evidence,
        "availability_concerns": unavailable,
        "weakest_starter": ({
            "player_id": weakest_starter.get("player_id"),
            "player": weakest_starter.get("player"),
            "position": weakest_starter.get("position"),
            "club": weakest_starter.get("club"),
            "start_score": round(_selection(weakest_starter, "start_score"), 1),
            "projected_points": player_projected_points(weakest_starter, gameweek)["projected_points"],
        } if weakest_starter else None),
    }


def _simulate_best_move(
    available_players: list[dict[str, Any]],
    my_squad: list[dict[str, Any]],
    gameweek: int,
    baseline_lineup: dict[str, Any],
) -> dict[str, Any] | None:
    baseline_projection = _lineup_projection(baseline_lineup, gameweek)["total"]
    by_id = {str(player.get("player_id")): player for player in my_squad}
    candidates = []
    for candidate in available_players:
        replacement = candidate.get("replacement") or {}
        action = str(replacement.get("action") or "")
        if action == "KEEP ROSTER" or not action:
            continue
        score = player_start_score(candidate, gameweek)
        if str(score.get("role_evidence") or "LOW") == "LOW" or _number(score.get("availability")) < 75:
            continue
        drop = by_id.get(str(replacement.get("drop_player_id")))
        if not drop or drop.get("position") != candidate.get("position"):
            continue
        swapped = [candidate if str(player.get("player_id")) == str(drop.get("player_id")) else player for player in my_squad]
        lineup = recommend_lineup(swapped, gameweek)
        if not lineup.get("is_valid"):
            continue
        projected_total = _lineup_projection(lineup, gameweek)["total"]
        points_delta = projected_total - baseline_projection
        roster_delta = _intel(candidate, "roster_score") - _intel(drop, "roster_score")
        if points_delta <= 0:
            continue
        candidates.append({
            "add_player_id": candidate.get("player_id"),
            "add_player": candidate.get("player"),
            "add_club": candidate.get("club"),
            "team_code": candidate.get("team_code"),
            "drop_player_id": drop.get("player_id"),
            "drop_player": drop.get("player"),
            "position": candidate.get("position"),
            "projected_points_delta": round(points_delta, 1),
            "roster_value_delta": round(roster_delta, 1),
            "projected_xi_after": round(projected_total, 1),
            "replacement_action": action,
            "role_evidence": score.get("role_evidence"),
        })
    if not candidates:
        return None
    candidates.sort(key=lambda row: (_number(row["projected_points_delta"]), _number(row["roster_value_delta"])), reverse=True)
    return candidates[0]


def _matchup_pressure(projected_edge: float, best_move: dict[str, Any] | None) -> dict[str, str]:
    if projected_edge >= 2.0:
        level = "LOW"
        headline = "Hold the stronger position"
        detail = "Your projected XI currently has the edge. Do not manufacture a short-term transaction just to react to the opponent."
    elif projected_edge >= -2.0:
        level = "MEDIUM" if best_move and _number(best_move.get("projected_points_delta")) >= 1.5 else "LOW"
        headline = "Fine margins"
        detail = "The matchup projects close. Review legitimate upgrades and lineup close calls, but protect season-long roster value."
    elif projected_edge >= -5.0:
        level = "MEDIUM"
        headline = "Review one targeted improvement"
        detail = "You project slightly behind. One evidence-backed move could matter, but avoid paying a large long-term roster cost."
    elif projected_edge >= -9.0:
        level = "HIGH"
        headline = "Act if the upgrade is real"
        detail = "The projected deficit is meaningful. Prioritise a move that improves this Gameweek and does not materially weaken Roster Value."
    else:
        level = "VERY HIGH"
        headline = "Active intervention warranted"
        detail = "The projected gap is large enough to justify active waiver and lineup review, while still rejecting destructive short-term punts."
    if best_move and _number(best_move.get("roster_value_delta")) < -8.0:
        detail += " The best short-term move currently carries a large Roster Value cost, so treat it as a watch rather than an automatic swap."
    return {"level": level, "headline": headline, "detail": detail}


def _tactical_priorities(
    position_edges: list[dict[str, Any]],
    best_move: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    priorities = []
    trailing = sorted(position_edges, key=lambda row: _number(row.get("projected_points_edge")))
    for edge in trailing:
        if _number(edge.get("projected_points_edge")) >= -1.5:
            continue
        priorities.append({
            "action": "POSITION FOCUS",
            "position": edge.get("position"),
            "reason": f"Opponent projects {abs(_number(edge.get('projected_points_edge'))):.1f} points better at {edge.get('position')} in the likely XIs.",
            "counter": best_move if best_move and best_move.get("position") == edge.get("position") else None,
        })
    if best_move and not any(priority.get("counter") for priority in priorities):
        priorities.insert(0, {
            "action": "MATCHUP UPGRADE",
            "position": best_move.get("position"),
            "reason": f"The strongest evidence-backed move adds about {_number(best_move.get('projected_points_delta')):.1f} projected XI points this Gameweek.",
            "counter": best_move,
        })
    if not priorities:
        priorities.append({
            "action": "HOLD SHAPE",
            "position": None,
            "reason": "No meaningful projected position deficit or evidence-backed tactical upgrade is present. Avoid forcing a matchup-specific move.",
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
    phase: str = "SCHEDULED",
    manager_profiles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an opponent scouting report for the next H2H Draft matchup."""
    my_entry = _find_entry(league_details, str(my_entry_id))
    if not my_entry:
        return {"model": "v1.0", "available": False, "gameweek": int(gameweek), "reason": "Could not map the configured Draft entry to a league entry."}
    my_league_id = _league_entry_id(my_entry)
    if my_league_id is None:
        return {"model": "v1.0", "available": False, "gameweek": int(gameweek), "reason": "The league entry does not expose an internal H2H identifier."}
    match = _find_match(league_details, my_league_id, int(gameweek))
    if not match:
        return {"model": "v1.0", "available": False, "gameweek": int(gameweek), "reason": "No upcoming H2H match was exposed by the league details payload."}
    match_gameweek = _match_event(match) or int(gameweek)
    first, second = _match_side_ids(match)
    opponent_league_id = second if first == my_league_id else first
    if opponent_league_id is None:
        return {"model": "v1.0", "available": False, "gameweek": match_gameweek, "reason": "The upcoming H2H match did not expose an opponent league entry."}

    opponent_entry = _entry_by_league_id(league_details, opponent_league_id) or {}
    opponent_entry_id = _entry_id(opponent_entry)
    opponent_profile = _manager_profile(manager_profiles, opponent_league_id, opponent_entry_id)
    opponent_squad = _squad_for_entry(ownership, opponent_league_id, opponent_entry_id)
    if len(opponent_squad) < 11:
        return {
            "model": "v1.0", "available": False, "gameweek": match_gameweek,
            "opponent": {"display_name": opponent_entry.get("entry_name") or opponent_entry.get("short_name") or "League opponent", "league_entry_id": opponent_league_id, "entry_id": opponent_entry_id, **_standing(league_details, opponent_league_id)},
            "reason": f"Opponent ownership resolved to only {len(opponent_squad)} players; a legal comparison would be unreliable.",
        }

    mine = my_lineup or recommend_lineup(my_squad, match_gameweek)
    theirs = recommend_lineup(opponent_squad, match_gameweek)
    if not mine.get("is_valid") or not theirs.get("is_valid"):
        return {"model": "v1.0", "available": False, "gameweek": match_gameweek, "reason": "A legal toolkit XI could not be generated for both sides."}

    my_summary = _lineup_summary(mine, match_gameweek)
    opponent_summary = _lineup_summary(theirs, match_gameweek)
    start_edge = _number(my_summary.get("average_start_score")) - _number(opponent_summary.get("average_start_score"))
    roster_edge = _number(my_summary.get("average_roster_value")) - _number(opponent_summary.get("average_roster_value"))
    fixture_edge = _number(my_summary.get("average_fixture_score")) - _number(opponent_summary.get("average_fixture_score"))
    projected_edge = _number((my_summary.get("projection") or {}).get("total")) - _number((opponent_summary.get("projection") or {}).get("total"))
    position_edges = _position_edges(mine, theirs, match_gameweek)
    evidence_floor = min(_number(my_summary.get("average_sample_confidence")), _number(opponent_summary.get("average_sample_confidence")))
    matchup_evidence = "HIGH" if evidence_floor >= 70 else "MEDIUM" if evidence_floor >= 40 else "LOW"
    best_move = _simulate_best_move(available_players, my_squad, match_gameweek, mine)
    pressure = _matchup_pressure(projected_edge, best_move)

    return {
        "model": "v1.0",
        "available": True,
        "gameweek": match_gameweek,
        "opponent": {
            "display_name": opponent_entry.get("entry_name") or opponent_entry.get("short_name") or "League opponent",
            "league_entry_id": opponent_league_id,
            "entry_id": opponent_entry_id,
            **_standing(league_details, opponent_league_id),
        },
        "opponent_profile": opponent_profile,
        "my_standing": _standing(league_details, my_league_id),
        "result": _match_result(match, my_league_id, phase),
        "matchup": {
            "signal": _signal(start_edge),
            "start_score_edge": round(start_edge, 1),
            "roster_value_edge": round(roster_edge, 1),
            "fixture_edge": round(fixture_edge, 1),
            "projected_points_edge": round(projected_edge, 1),
            "evidence": matchup_evidence,
            "pressure": pressure,
            "my": my_summary,
            "opponent": opponent_summary,
            "position_edges": position_edges,
        },
        "scouting": {
            "opponent": _scouting_report(opponent_squad, theirs, match_gameweek),
            "mine": _scouting_report(my_squad, mine, match_gameweek),
            "best_matchup_move": best_move,
        },
        "my_lineup": mine,
        "opponent_lineup": theirs,
        "opponent_squad": opponent_squad,
        "opponent_threats": _threat_rows(theirs, match_gameweek),
        "my_counterweights": _threat_rows(mine, match_gameweek),
        "tactical_priorities": _tactical_priorities(position_edges, best_move),
        "note": "Projected points v1.0 converts blended points-per-90, expected minutes, availability and fixture difficulty into a conservative next-GW estimate. Ranges widen for weaker role evidence. They are decision-support estimates, not calibrated statistical intervals or win probabilities.",
    }


def _outlook_projection(summary: dict[str, Any]) -> dict[str, Any]:
    projection = summary.get("projection") or {}
    return {
        "formation": summary.get("formation"),
        "total": projection.get("total"),
        "range_low": projection.get("range_low"),
        "range_high": projection.get("range_high"),
        "evidence": summary.get("evidence"),
    }


def _freeze_current_outlook(card: dict[str, Any], frozen_current: dict[str, Any] | None) -> None:
    if not frozen_current or int(frozen_current.get("gameweek") or -1) != int(card.get("gameweek") or -2):
        return
    forecast = frozen_current.get("forecast") or {}
    recommended = forecast.get("recommended") or {}
    h2h = forecast.get("h2h") or {}
    if recommended.get("projected_total") is not None:
        card["my"]["total"] = recommended.get("projected_total")
        card["my"]["range_low"] = recommended.get("range_low")
        card["my"]["range_high"] = recommended.get("range_high")
    if h2h.get("projected_opponent_total") is not None:
        card["opponent_projection"]["total"] = h2h.get("projected_opponent_total")
    edge = h2h.get("projected_edge")
    if edge is None:
        edge = _number(card["my"].get("total")) - _number(card["opponent_projection"].get("total"))
    card["projected_edge"] = round(_number(edge), 1)
    card["signal"] = _signal(_number(edge))
    card["projection_source"] = "frozen_gameweek_forecast"


def _outlook_summary(cards: list[dict[str, Any]]) -> dict[str, Any]:
    available = [card for card in cards if card.get("available")]
    counts = {signal: sum(1 for card in available if card.get("signal") == signal) for signal in ("EDGE", "EVEN", "TRAIL")}
    projected_for = sum(_number((card.get("my") or {}).get("total")) for card in available)
    projected_against = sum(_number((card.get("opponent_projection") or {}).get("total")) for card in available)
    toughest = min(available, key=lambda card: _number(card.get("projected_edge"))) if available else None
    best = max(available, key=lambda card: _number(card.get("projected_edge"))) if available else None
    position_edges: dict[str, list[float]] = {}
    for card in available:
        for row in card.get("position_edges") or []:
            position = str(row.get("position") or "")
            if position:
                position_edges.setdefault(position, []).append(_number(row.get("projected_points_edge")))
    recurring_weakness = None
    if position_edges:
        candidates = [
            (position, values)
            for position, values in position_edges.items()
            if _mean(values) < 0 and sum(1 for value in values if value < 0) >= 2
        ]
        if candidates:
            position, values = min(candidates, key=lambda item: _mean(item[1]))
            recurring_weakness = {
                "position": position,
                "average_projected_edge": round(_mean(values), 1),
                "trailing_gameweeks": sum(1 for value in values if value < 0),
            }

    def highlight(card: dict[str, Any] | None) -> dict[str, Any] | None:
        if not card:
            return None
        return {
            "gameweek": card.get("gameweek"),
            "opponent": (card.get("opponent") or {}).get("display_name"),
            "projected_edge": card.get("projected_edge"),
        }

    return {
        "available_gameweeks": len(available),
        "signals": counts,
        "projected_for": round(projected_for, 1),
        "projected_against": round(projected_against, 1),
        "projected_net": round(projected_for - projected_against, 1),
        "toughest_matchup": highlight(toughest),
        "best_opportunity": highlight(best),
        "recurring_weakness": recurring_weakness,
    }


def build_h2h_outlook(
    league_details: dict[str, Any],
    my_entry_id: str,
    my_squad: list[dict[str, Any]],
    ownership: list[dict[str, Any]],
    gameweeks: list[int],
    frozen_current: dict[str, Any] | None = None,
    manager_profiles: dict[str, dict[str, Any]] | None = None,
    scoring_gameweek: int | None = None,
) -> dict[str, Any]:
    """Project the next four exact H2H schedule matches from current rosters."""
    my_entry = _find_entry(league_details, str(my_entry_id))
    my_league_id = _league_entry_id(my_entry or {})
    if not my_entry or my_league_id is None:
        return {
            "model": "v1.1",
            "available": False,
            "gameweeks": [],
            "summary": _outlook_summary([]),
            "reason": "Could not map the configured Draft entry to the H2H schedule.",
        }

    cards = []
    active_gameweek = int(scoring_gameweek) if scoring_gameweek is not None else min(gameweeks) if gameweeks else None
    for gameweek in gameweeks[:4]:
        match = _find_exact_match(league_details, my_league_id, int(gameweek))
        if not match:
            cards.append({"gameweek": int(gameweek), "available": False, "reason": "No exact H2H schedule match was exposed."})
            continue
        first, second = _match_side_ids(match)
        opponent_league_id = second if first == my_league_id else first
        opponent_entry = _entry_by_league_id(league_details, opponent_league_id or "") or {}
        opponent_entry_id = _entry_id(opponent_entry)
        opponent_profile = _manager_profile(manager_profiles, opponent_league_id, opponent_entry_id)
        opponent_squad = _squad_for_entry(ownership, opponent_league_id, opponent_entry_id)
        mine = recommend_lineup(my_squad, int(gameweek))
        theirs = recommend_lineup(opponent_squad, int(gameweek))
        if len(opponent_squad) < 11 or not mine.get("is_valid") or not theirs.get("is_valid"):
            cards.append({
                "gameweek": int(gameweek),
                "available": False,
                "reason": f"A legal current-roster comparison could not be built for GW{gameweek}.",
            })
            continue

        my_summary = _lineup_summary(mine, int(gameweek))
        opponent_summary = _lineup_summary(theirs, int(gameweek))
        my_projection = _outlook_projection(my_summary)
        opponent_projection = _outlook_projection(opponent_summary)
        decision_adjustment = 0.0
        if active_gameweek is not None and int(gameweek) > int(active_gameweek):
            decision_adjustment = _apply_decision_adjustment(opponent_projection, opponent_profile)
        projected_edge = _number(my_projection.get("total")) - _number(opponent_projection.get("total"))
        position_edges = _position_edges(mine, theirs, int(gameweek))
        threat = (_threat_rows(theirs, int(gameweek), 1) or [None])[0]
        card = {
            "gameweek": int(gameweek),
            "available": True,
            "opponent": {
                "display_name": opponent_entry.get("entry_name") or opponent_entry.get("short_name") or "League opponent",
                "league_entry_id": opponent_league_id,
                "entry_id": opponent_entry_id,
                **_standing(league_details, opponent_league_id or ""),
            },
            "my": my_projection,
            "opponent_projection": opponent_projection,
            "opponent_profile": opponent_profile,
            "decision_adjustment": decision_adjustment,
            "projected_edge": round(projected_edge, 1),
            "signal": _signal(projected_edge),
            "projection_source": "current_roster_plus_decision_profile" if decision_adjustment else "current_rosters",
            "position_edges": position_edges,
            "weakest_position": min(position_edges, key=lambda row: _number(row.get("projected_points_edge"))) if position_edges else None,
            "strongest_position": max(position_edges, key=lambda row: _number(row.get("projected_points_edge"))) if position_edges else None,
            "key_threat": threat,
        }
        _freeze_current_outlook(card, frozen_current)
        cards.append(card)

    return {
        "model": "v1.1",
        "available": any(card.get("available") for card in cards),
        "gameweeks": cards,
        "summary": _outlook_summary(cards),
        "note": "The outlook begins with the next actionable Gameweek. Future matchups use current rosters plus an explicitly labelled, capped opponent-decision adjustment. The model cannot see unsubmitted waivers or future lineups; the locked scoring Gameweek remains in outcome diagnostics.",
    }
