from pathlib import Path
import subprocess


def test_h2h_renderer_uses_the_defined_my_matchup_reference():
    source = Path("public/h2h-v08.js").read_text(encoding="utf-8")

    assert "esc(mine.formation" in source
    assert "esc(my.formation" not in source


def test_outcome_renderer_keeps_missing_points_unknown_and_labels_exclusions():
    subprocess.run(["node", "-e", r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const context = {controls: () => '', renderPlanner: () => '', allPlayers: () => [], esc: String,
  DATA: {outcome_diagnostics: {current: {phase: 'FINAL', gameweek: 3,
    forecast: {calibration_eligible: true, recommended: {projected_total: 6}},
    actual: {recommended_points: null}, evaluation: {calibration_eligible: false}}}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('public/h2h-v08.js', 'utf8'), context);
assert.equal(context.h2hScore(null), '-');
assert.equal(context.h2hScore(0), '0.0');
const html = context.h2hOutcomePanel();
assert(html.includes('Excluded from calibration'));
assert(html.includes('Toolkit Recommended XI</small><strong>-</strong>'));
"""], check=True)


def test_h2h_renderer_exposes_four_gameweek_outlook():
    source = Path("public/h2h-v08.js").read_text(encoding="utf-8")
    styles = Path("public/h2h-outlook-v11.css").read_text(encoding="utf-8")
    index = Path("public/index.html").read_text(encoding="utf-8")

    assert "function renderH2HOutlook" in source
    assert "Four-Gameweek H2H Outlook · v1.1" in source
    assert "Frozen current-GW forecast" in source
    assert "Current-roster projection" in source
    assert ".h2h-outlook-grid" in styles
    assert "h2h-outlook-v11.css?v=20260821.1" in index
    assert "h2h-v08.js?v=20260909.1" in index


def test_h2h_visual_hierarchy_uses_progressive_disclosure_and_mobile_scrolling():
    source = Path("public/h2h-v08.js").read_text(encoding="utf-8")
    styles = Path("public/h2h-visual-v12.css").read_text(encoding="utf-8")
    index = Path("public/index.html").read_text(encoding="utf-8")
    about = Path("public/about.html").read_text(encoding="utf-8")

    assert "function h2hDisclosure" in source
    assert '<details class="h2h-disclosure' in source
    assert "h2h-detail-stack" in source
    assert "Opponent scout & position matchups" in source
    assert "Likely starting lineups" in source
    assert "Threats & tactical priorities" in source
    assert ".h2h-hero" in styles
    assert "scroll-snap-type: inline mandatory" in styles
    assert "h2h-visual-v12.css?v=20260822.2" in index
    assert "Progressive scouting v1.2" in about


def test_h2h_surfaces_team_name_and_opponent_decision_profile_without_overloading_the_summary():
    source = Path("public/h2h-v08.js").read_text(encoding="utf-8")
    styles = Path("public/h2h-visual-v12.css").read_text(encoding="utf-8")
    about = Path("public/about.html").read_text(encoding="utf-8")

    assert "function h2hDecisionProfile" in source
    assert "decision threat" in source
    assert "Draft prior" in source
    assert "Transfer value" in source
    assert "Lineup efficiency" in source
    assert ".h2h-manager-profile" in styles
    assert "chosen team name" in about
