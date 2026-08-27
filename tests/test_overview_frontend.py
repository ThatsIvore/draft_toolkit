from pathlib import Path


def test_overview_is_the_default_and_has_a_dedicated_navigation_route():
    app = Path("public/app.js").read_text(encoding="utf-8")
    index = Path("public/index.html").read_text(encoding="utf-8")
    interaction = Path("public/interaction.js").read_text(encoding="utf-8")

    assert "let VIEW = 'overview'" in app
    assert 'data-view="overview">Overview' in index
    assert "overview-v1.css?v=20260827.1" in index
    assert "overview-v1.js?v=20260827.1" in index
    assert "['overview','squad'" in interaction


def test_overview_uses_existing_guarded_decisions_for_urgency():
    source = Path("public/overview-v1.js").read_text(encoding="utf-8")

    assert "function overviewUrgentItems" in source
    assert "overviewRelevantUpdates(data)" in source
    assert "overviewAvailabilityActions(data)" in source
    assert "overviewH2HAction(data)" in source
    assert "['critical', 'important']" in source
    assert "['HIGH', 'VERY HIGH']" in source
    assert "['SWAP NOW', 'STASH SWAP']" in source
    assert "row.dashboard_action === 'EARLY PICKUP'" in source
    assert "const deduplicated = new Map()" in source
    assert "No urgent action clears the guardrails" in source


def test_specialist_views_no_longer_repeat_the_global_hero():
    source = Path("public/overview-v1.js").read_text(encoding="utf-8")
    styles = Path("public/overview-v1.css").read_text(encoding="utf-8")

    assert "function overviewViewMeta" in source
    assert "hero.hidden = true" in source
    assert "compact-view-hero" in source
    assert ".hero[hidden]{display:none}" in styles
    assert "My Team" in source
    assert "Available players" in source
    assert "League activity" in source
    assert "Four-Gameweek planner" in source


def test_overview_keeps_start_score_and_h2h_projection_semantics_distinct():
    source = Path("public/overview-v1.js").read_text(encoding="utf-8")

    assert "average Start Score" in source
    assert "Projected XI" in source
    assert "projected_points_edge" in source
