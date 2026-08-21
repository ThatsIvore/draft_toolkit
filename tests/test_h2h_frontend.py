from pathlib import Path


def test_h2h_renderer_uses_the_defined_my_matchup_reference():
    source = Path("public/h2h-v08.js").read_text(encoding="utf-8")

    assert "esc(mine.formation" in source
    assert "esc(my.formation" not in source


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
    assert "h2h-v08.js?v=20260821.3" in index
