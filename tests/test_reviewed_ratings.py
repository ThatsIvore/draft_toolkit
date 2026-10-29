from datetime import datetime, timezone
import pytest
from fpl_toolkit.reviewed_ratings import reviewed_ratings

BOOT = {'events':[{'id':1,'deadline_time':'2026-08-22T11:00:00Z'}], 'elements':[{'code':123,'id':999}]}
NOW = datetime(2026,10,29,14,tzinfo=timezone.utc)
ROW = dict(code=123,provider='fotmob',source_url='https://www.fotmob.com/players/1',observed_at='2026-10-29T12:00:00Z',season=2026,competition='Premier League',through_gameweek=8,rating=7.4,appearances=4,starts=2,minutes=216)

def test_mapping_sample_and_privacy():
    players, summary = reviewed_ratings(BOOT,[8],rows=[dict(ROW,owner_name='secret')],now=NOW)
    assert players[999][0]['small_sample']
    assert 'owner_name' not in players[999][0]
    assert 'code' not in players[999][0]
    assert summary['recommendations_affected'] is False

@pytest.mark.parametrize('change', [dict(observed_at='2026-10-25T00:00:00Z'),dict(observed_at='2026-10-30T00:00:00Z'),dict(observed_at='2026-10-29'),dict(season=2025),dict(through_gameweek=7),dict(competition='EFL Cup'),dict(rating=float('nan')),dict(code=999),dict(source_url='https://www.fotmob.com.evil.test/a'),dict(starts=5)])
def test_invalid_evidence_is_neutral(change):
    players, summary = reviewed_ratings(BOOT,[8],rows=[dict(ROW,**change)],now=NOW)
    assert players == {}
    assert summary['rejected_records'] == 1

def test_duplicate_provider_not_double_counted():
    players,_ = reviewed_ratings(BOOT,[8],rows=[ROW,ROW],now=NOW)
    assert len(players[999]) == 1
