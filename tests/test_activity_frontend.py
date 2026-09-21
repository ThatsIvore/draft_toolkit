import json
from pathlib import Path
import subprocess


def render(data):
    source = Path('public/app.js').read_text()
    start = source.index('function renderActivity()')
    end = source.index('\nfunction renderPlanner()', start)
    script = '''const DATA = JSON.parse(process.argv[1]);
    const esc = s => String(s ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    ''' + source[start:end] + '\nconsole.log(renderActivity());'
    return subprocess.run(['node', '-e', script, json.dumps(data)], check=True, capture_output=True, text=True).stdout


def test_activity_renderer_explains_retention_and_escapes_names():
    html = render({'league_activity': [{'type': 'add', 'player': '<script>', 'from_team': 'Free pool', 'to_team': 'Alpha', 'captured_at': '2026-09-21', 'gameweek': 6}], 'league_activity_summary': {'retained': 1, 'new_this_collection': 0}})
    assert '1 retained changes · 0 new this collection' in html
    assert 'Free pool → Alpha' in html
    assert '&lt;script&gt;' in html and '<script>' not in html
    assert '2026-09-21' in html


def test_activity_renderer_does_not_claim_no_transfers_ever_or_fake_zero_results():
    assert 'since monitoring started' not in render({})
    html = render({'transfer_reviews': [{'team_name': 'Alpha', 'adds': ['New'], 'drops': ['Old'], 'outcome': {'status': 'pending', 'points_gain': None}}]})
    assert 'Player points gain: Pending' in html
    assert 'Incoming started points: Pending' in html
