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
