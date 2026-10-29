from datetime import datetime, timezone
import json
import pytest
from fpl_toolkit.fotmob_ratings import collect_fotmob

BOOT = {'events':[{'id':1,'deadline_time':'2026-08-22T11:00:00Z'}], 'elements':[{'code':123,'id':999,'team':1}], 'teams':[{'id':1,'name':'Bournemouth'}, {'id':2,'name':'Leeds'}]}
FIX = [{'event':8,'finished':True,'team_h':1,'team_a':2,'kickoff_time':'2026-10-25T14:00:00Z'}]
MAPPING = [{'code':123,'provider_id':7}]
NOW = datetime(2026,10,29,14,tzinfo=timezone.utc)

def page(**changes):
    p = dict(id=7,primaryTeam={'teamName':'AFC Bournemouth'},mainLeague={'leagueId':47,'season':'2026/2027','stats':[{'localizedTitleId':k,'value':v} for k,v in dict(rating=7.4,matches_uppercase=8,started=8,minutes_played=700).items()]},recentMatches=[{'leagueId':47,'matchDate':{'utcTime':'2026-10-25T14:00:00Z'},'opponentTeamName':'Leeds','isHomeTeam':True}])
    p.update(changes)
    return '<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'props':{'pageProps':{'data':p}}})+'</script>'

def test_public_page_collection_maps_and_validates():
    rows, summary=collect_fotmob(BOOT,FIX,[8],mappings=MAPPING,now=NOW,fetch=lambda u:page())
    assert rows[0]['code']==123 and rows[0]['rating']==7.4
    assert summary['accepted']==1

@pytest.mark.parametrize('html',[page(id=9),page(recentMatches=[]),page(primaryTeam={'teamName':'Arsenal'}),'<html>Challenge</html>',page(mainLeague={'leagueId':133,'season':'2026/2027'})])
def test_stale_wrong_identity_and_unavailable_fail_closed(html):
    rows, summary=collect_fotmob(BOOT,FIX,[8],mappings=MAPPING,now=NOW,fetch=lambda u:html)
    assert rows==[] and summary['failed_or_ineligible']==1

def test_goalkeeper_without_starts_preserves_unknown():
    league={'leagueId':47,'season':'2026/2027','stats':[{'localizedTitleId':k,'value':v} for k,v in dict(rating=7.1,matches_uppercase=8,minutes_played=720).items()]}
    rows,summary=collect_fotmob(BOOT,FIX,[8],mappings=MAPPING,now=NOW,fetch=lambda u:page(mainLeague=league))
    assert summary['accepted']==1
    assert rows[0]['starts'] is None
