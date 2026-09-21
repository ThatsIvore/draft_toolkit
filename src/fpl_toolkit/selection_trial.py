"""Prospective points-only challenger; never used to select the public XI."""
from itertools import combinations
from typing import Any

from .h2h import player_projected_points
from .transfer_intel import transfer_blocks_selection


def points_challenger(squad: list[dict[str, Any]], gameweek: int) -> dict[str, Any] | None:
    if len(squad) != 15 or len({p.get('player_id') for p in squad}) != 15:
        return None
    if any(p.get('player_id') is None or not any(w.get('gameweek') == gameweek for w in p.get('fixtures', [])) for p in squad):
        return None
    if {pos: sum(p.get('position') == pos for p in squad) for pos in ('GKP', 'DEF', 'MID', 'FWD')} != {'GKP': 2, 'DEF': 5, 'MID': 5, 'FWD': 3}:
        return None
    eligible = [p for p in squad if not transfer_blocks_selection(p)]
    projections = {p['player_id']: player_projected_points(p, gameweek) for p in eligible}
    best = None
    # Stable IDs settle equal rounded projections; no result or event_points is read.
    for xi in combinations(sorted(eligible, key=lambda p: p['player_id']), 11):
        counts = {pos: sum(p.get('position') == pos for p in xi) for pos in ('GKP', 'DEF', 'MID', 'FWD')}
        if counts['GKP'] != 1 or not 3 <= counts['DEF'] <= 5 or not 2 <= counts['MID'] <= 5 or not 1 <= counts['FWD'] <= 3:
            continue
        total = round(sum(projections[p['player_id']]['projected_points'] for p in xi), 1)
        if best is None or total > best[0]:
            best = (total, xi, counts)
    if best is None:
        return None
    _, xi, counts = best
    return {
        'model': 'points-shadow-v1', 'is_valid': True,
        'formation': f"{counts['DEF']}-{counts['MID']}-{counts['FWD']}",
        'starters': list(xi),
    }
