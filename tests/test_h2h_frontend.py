from pathlib import Path


def test_h2h_renderer_uses_the_defined_my_matchup_reference():
    source = Path("public/h2h-v08.js").read_text(encoding="utf-8")

    assert "esc(mine.formation" in source
    assert "esc(my.formation" not in source
