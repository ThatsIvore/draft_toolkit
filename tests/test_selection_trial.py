from copy import deepcopy

from fpl_toolkit.optimizer import recommend_lineup
from fpl_toolkit.outcomes import build_outcome_diagnostics
from fpl_toolkit.selection_trial import points_challenger


def report(gw=1, timestamp='2026-08-01T10:00:00+00:00'):
    positions = ['GKP'] * 2 + ['DEF'] * 5 + ['MID'] * 5 + ['FWD'] * 3
    squad = [{
        'player_id': i, 'player': f'P{i}', 'position': pos, 'event_points': i,
        'fixtures': [{'gameweek': gw, 'matches': [{'difficulty': 3}]}],
        'intelligence': {'points_per_90': i / 2, 'expected_minutes': 90,
                         'availability_score': 100, 'sample_confidence': 80,
                         'floor_score': 50, 'upside_score': 50},
    } for i, pos in enumerate(positions, 1)]
    return {'my_squad': squad, 'generated_at': timestamp, 'current_gameweek': gw,
            'decision_gameweek': gw, 'decision_gameweek_phase': 'SCHEDULED',
            '_forecast_before_deadline': True, 'recommended_lineup': recommend_lineup(squad, gw)}


def test_shadow_is_legal_deterministic_and_does_not_use_results_or_mutate_squad():
    p = report()
    before = deepcopy(p)
    shadow = points_challenger(p['my_squad'], 1)
    assert p == before
    ids = [x['player_id'] for x in shadow['starters']]
    assert len(ids) == len(set(ids)) == 11
    assert shadow['formation'] == '3-4-3'
    for x in p['my_squad']:
        x['event_points'] = -9999 if x['player_id'] in ids else 9999
    assert [x['player_id'] for x in points_challenger(list(reversed(p['my_squad'])), 1)['starters']] == ids
    assert points_challenger(p['my_squad'][:-1], 1) is None
    assert points_challenger(p['my_squad'], 2) is None


def test_original_stays_frozen_latest_pair_updates_then_locks_even_before_kickoff():
    p = report()
    initial = build_outcome_diagnostics(None, p, 'SCHEDULED')
    later = deepcopy(p)
    later['generated_at'] = '2026-08-01T11:00:00+00:00'
    later['my_squad'][0]['intelligence']['points_per_90'] = 100
    refreshed = build_outcome_diagnostics({'outcome_diagnostics': initial}, later, 'SCHEDULED')
    assert refreshed['current']['forecast'] == initial['current']['forecast']
    pair = refreshed['current']['deadline_selection']
    assert pair['baseline']['captured_at'] == later['generated_at']
    assert 1 in [x['player_id'] for x in pair['challenger']['recommended']['starters']]
    late = deepcopy(later)
    late['_forecast_before_deadline'] = False
    late['generated_at'] = '2026-08-01T12:00:00+00:00'
    for phase in ['SCHEDULED', 'LIVE', 'FINAL']:
        locked = build_outcome_diagnostics({'outcome_diagnostics': refreshed}, late, phase)
        assert locked['current']['deadline_selection'] == pair
    assert locked['current']['selection_comparison']['complete']
    # Older snapshots cannot roll the last collected record backward.
    assert build_outcome_diagnostics({'outcome_diagnostics': refreshed}, p, 'SCHEDULED')['current']['deadline_selection'] == pair


def test_pending_pair_refreshes_and_promotes_without_retroactive_capture():
    scoring = report()
    scoring['_forecast_before_deadline'] = False
    next_round = report(2)
    first = build_outcome_diagnostics(None, scoring, 'FINAL', decision_report=next_round)
    next_round['generated_at'] = '2026-08-02T11:00:00+00:00'
    later = build_outcome_diagnostics({'outcome_diagnostics': first}, scoring, 'FINAL', decision_report=next_round)
    assert later['pending_forecasts'] == first['pending_forecasts']
    assert later['pending_deadline_selections']['2']['baseline']['captured_at'] == next_round['generated_at']
    next_round['_forecast_before_deadline'] = False
    final = build_outcome_diagnostics({'outcome_diagnostics': later}, next_round, 'FINAL')
    assert final['current']['deadline_selection'] == later['pending_deadline_selections']['2']
    assert final['pending_deadline_selections'] == {}
    assert build_outcome_diagnostics(None, next_round, 'FINAL')['current']['deadline_selection'] is None


def test_missing_actuals_are_not_zero_or_an_experimental_win():
    p = report()
    initial = build_outcome_diagnostics(None, p, 'SCHEDULED')
    p['_forecast_before_deadline'] = False
    final = build_outcome_diagnostics({'outcome_diagnostics': initial}, p, 'FINAL', scoring_players=[])
    comparison = final['current']['selection_comparison']
    assert not comparison['complete']
    assert comparison['challenger_gain'] is None
    assert comparison['baseline']['actual_points'] is None
    assert comparison['challenger']['absolute_error'] is None


def test_shadow_excludes_blocked_players_and_keeps_public_identity_boundary():
    from fpl_toolkit.privacy import sanitize_public_report
    p = report()
    p['my_squad'][-1]['transfer_intel'] = {'blocks_selection': True}
    p['my_squad'][-1]['intelligence']['points_per_90'] = 999
    assert 15 not in [x['player_id'] for x in points_challenger(p['my_squad'], 1)['starters']]
    for player in p['my_squad']:
        player['owner_entry_id'] = 'private-entry'
        player['owner_name'] = 'Private Manager'
    result = build_outcome_diagnostics(None, p, 'SCHEDULED')
    public = sanitize_public_report({'outcome_diagnostics': result})
    assert 'private-entry' not in str(public)
    assert 'Private Manager' not in str(public)
