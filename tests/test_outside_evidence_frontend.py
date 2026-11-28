from pathlib import Path
import shutil
import subprocess

import pytest


def test_outside_evidence_release_is_optional_and_scoped():
    page = Path("public/index.html").read_text()
    drawer = Path("public/intelligence-v3.js").read_text()
    assert page.index("outside-evidence-v01.js?v=0.1.0") < page.index("intelligence-v3.js")
    assert "window.draftOutsideEvidence?.render(p, DATA?.decision_gameweek) || ''" in drawer


@pytest.mark.skipif(not shutil.which("node"), reason="Node required for JS behavior checks")
def test_outside_evidence_visibility_rollbacks_and_safe_links():
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const code = fs.readFileSync('public/outside-evidence-v01.js', 'utf8');
function load(text = code) {
  const ctx = {window: {}, URL, esc: value => String(value)};
  vm.runInNewContext(text, ctx);
  return ctx.window.draftOutsideEvidence.render;
}
const rayan = {player_id: '67', club: 'BOU', player: 'Rayan'};
const before = Date.parse('2026-11-30T18:29:59Z');
const atWaivers = Date.parse('2026-11-30T18:30:00Z');
const atLineup = Date.parse('2026-12-01T18:30:00Z');
const render = load();
assert.match(render(rayan, 13, before), /Used substitute at 68′/);
assert.match(render(rayan, 13, before), /Pre-deadline context/);
assert.match(render(rayan, 13, atWaivers), /Lineup context only/);
assert.match(render(rayan, 13, atWaivers), /does not predict a Premier League start/);
assert.equal(render(rayan, 13, atLineup), '');
assert.equal(render(rayan, 12, before), '');
assert.equal(render({...rayan, club: 'CHE'}, 13, before), '');
assert.equal(render({...rayan, player: 'Another Rayan'}, 13, before), '');
assert.equal(render(rayan, 13, Date.parse('2026-11-27T00:00:00Z')), '');
assert.equal(render(rayan, 13, NaN), '');
assert.equal(load(code.replace('enabled: true', 'enabled: false'))(rayan, 13, before), '');
assert.equal(load(code.replace('https://www.afcb.co.uk/', 'https://www.afcb.co.uk.evil.example/'))(rayan, 13, before), '');
assert.equal(load(code.replace('https://www.afcb.co.uk/', 'http://www.afcb.co.uk/'))(rayan, 13, before), '');
"""
    subprocess.run(["node", "-e", script], check=True)
