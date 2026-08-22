from pathlib import Path


def test_decision_updates_frontend_exposes_persistent_cycle_sections_and_unread_badge():
    script = Path("public/changefeed-v09.js").read_text()
    page = Path("public/index.html").read_text()

    assert "Decision Updates" in page
    assert "GW${esc(gameweek)} decision cycle" in script
    assert "Action needed" in script
    assert "Worth monitoring" in script
    assert "Resolved and recent" in script
    assert "Earlier decision cycles" in script
    assert "localStorage" in script
    assert "unseenDecisionUpdateCount" in script


def test_about_explains_decision_cycle_retention_and_archive():
    about = Path("public/about.html").read_text()

    assert "Decision Updates · v1.0" in about
    assert "entire actionable Gameweek" in about
    assert "two most recent cycles are retained" in about
