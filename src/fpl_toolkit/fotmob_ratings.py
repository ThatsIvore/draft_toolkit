"""Small, explicitly mapped FotMob public-page pilot. Never bypass access challenges."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from importlib.resources import files
import json
import requests

from .external_match_evidence import canonical_team_name
from .reviewed_ratings import reviewed_ratings


class PageData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == '__NEXT_DATA__':
            self.active = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def parse_rating(html, mapping, bootstrap, fixtures, completed, now):
    parser = PageData()
    parser.feed(html)
    player = json.loads(''.join(parser.parts))['props']['pageProps']['data']
    official = next(e for e in bootstrap['elements'] if e['code'] == mapping['code'])
    team = next(t for t in bootstrap['teams'] if t['id'] == official['team'])
    if player['id'] != mapping['provider_id'] or canonical_team_name(player['primaryTeam']['teamName']) != canonical_team_name(team['name']):
        raise ValueError('Identity mismatch')
    league = player['mainLeague']
    events = bootstrap['events']
    if isinstance(events, dict):
        events = events['data']
    season = int(next(e['deadline_time'] for e in events if e['id'] == 1)[:4])
    if league['leagueId'] != 47 or league['season'] != f'{season}/{season + 1}':
        raise ValueError('Wrong competition or season')
    club_fixtures = [f for f in fixtures if f.get('event') in completed and f.get('finished') and official['team'] in (f['team_h'], f['team_a'])]
    latest = max(club_fixtures, key=lambda f: f['kickoff_time'])
    opponent = latest['team_a'] if latest['team_h'] == official['team'] else latest['team_h']
    opponent_name = next(t['name'] for t in bootstrap['teams'] if t['id'] == opponent)
    matches = [m for m in player['recentMatches'] if m['leagueId'] == 47]
    # Require an exact latest club fixture, including opponent and home/away.
    if not any(m['matchDate']['utcTime'][:10] == latest['kickoff_time'][:10]
               and canonical_team_name(m['opponentTeamName']) == canonical_team_name(opponent_name)
               and m['isHomeTeam'] == (latest['team_h'] == official['team']) for m in matches):
        raise ValueError('Stale fixture coverage')
    # Do not contaminate a finalized-round snapshot with a later live/unchecked match.
    if any(m['matchDate']['utcTime'][:10] > latest['kickoff_time'][:10] for m in matches):
        raise ValueError('Provider ahead of finalized window')
    stats = {s['localizedTitleId']: s['value'] for s in league['stats']}
    return dict(code=mapping['code'], provider='fotmob', source_url=mapping['source_url'],
                observed_at=now.isoformat(), season=season, competition='Premier League',
                through_gameweek=max(completed), rating=stats['rating'], appearances=stats['matches_uppercase'],
                starts=stats['started'], minutes=stats['minutes_played'])


def collect_fotmob(bootstrap, fixtures, completed, *, mappings=None, now=None, fetch=None):
    now = now or datetime.now(timezone.utc)
    mappings = mappings if mappings is not None else json.loads(files('fpl_toolkit').joinpath('data/fotmob-mappings.json').read_text())
    if not completed:
        return [], {'status': 'no_completed_gameweeks', 'requested': 0, 'accepted': 0}

    def retrieve(mapping):
        try:
            url = f"https://www.fotmob.com/players/{int(mapping['provider_id'])}"
            if fetch:
                html = fetch(url)
            else:
                response = requests.get(url, timeout=15, allow_redirects=False,
                                        headers={'User-Agent': 'draft-toolkit/0.1 public-ratings-pilot'})
                response.raise_for_status()
                if response.status_code != 200:
                    return None
                html = response.text
            row = parse_rating(html, {**mapping, 'source_url': url}, bootstrap, fixtures, completed, now)
            accepted, _ = reviewed_ratings(bootstrap, completed, rows=[row], now=now)
            return row if accepted else None
        except (requests.RequestException, ValueError, TypeError, KeyError, StopIteration, OverflowError):
            return None

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(retrieve, mappings[:30]))
    rows = [r for r in results if r is not None]
    return rows, {'status': 'available' if rows else 'unavailable', 'requested': len(results),
                  'accepted': len(rows), 'failed_or_ineligible': len(results) - len(rows)}
