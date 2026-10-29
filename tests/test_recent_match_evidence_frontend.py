from pathlib import Path


def test_player_drawer_explains_recent_match_grades_and_guardrails():
    source = Path("public/intelligence-v3.js").read_text(encoding="utf-8")

    assert "Recent completed-Gameweek evidence" in source
    assert "Only final, officially checked Gameweeks count" in source
    assert "double Gameweeks are aggregated" in source
    assert "capped at ±5 model points" in source


def test_about_page_documents_shared_recent_evidence():
    about = Path("public/about.html").read_text(encoding="utf-8")

    assert "Recent Match Evidence v1" in about
    assert "finished and data-checked" in about
    assert "feed is unavailable" in about


def test_external_ratings_panel_escapes_content_and_rejects_unsafe_sources():
    import subprocess
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const context = {URL, esc: v => String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;')};
vm.createContext(context);
vm.runInContext(fs.readFileSync('public/intelligence-v3.js','utf8'),context);
const render = rows => context.externalRatingsPanel({intelligence:{external_ratings:rows}});
const row = {provider:'fotmob',source_url:'https://www.fotmob.com/players/7',rating:7.4,appearances:4,starts:null,minutes:216,season:2026,through_gameweek:8,observed_at:'<img onerror=alert(1)>',small_sample:true};
const html=render([row]);
assert(html.includes('7.4/10') && html.includes('Small sample') && html.includes('Unavailable'));
assert(html.includes('&lt;img') && !html.includes('<img'));
for(const url of ['javascript:alert(1)','https://www.fotmob.com.evil/7','https://evil@www.fotmob.com/7']) {
 assert(render([{...row,source_url:url}]).includes('No current, validated'));
}
assert(render([]).includes('No current, validated'));
'''
    subprocess.run(['node','-e',script],check=True)
