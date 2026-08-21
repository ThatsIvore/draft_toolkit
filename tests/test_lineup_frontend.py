from pathlib import Path


def test_official_lineup_reuses_the_fpl_kit_and_card_components():
    app = Path("public/app.js").read_text(encoding="utf-8")
    recommended = Path("public/recommended-xi.js").read_text(encoding="utf-8")

    assert "function recommendedKit" in app
    assert "function recommendedKit" not in recommended
    assert 'class="pitch-player recommended-player official-player' in app
    assert 'class="bench-card recommended-bench-card official-bench-card"' in app
    assert 'class="pitch-shell recommended-xi-shell official-lineup-shell"' in app
    assert '<span class="shirt">' not in app
    assert '<span class="bench-shirt">' not in app
    assert "Recommended · v0.6.3" in recommended
    assert "event_points" in app
    assert "Live score" in app
    assert "h2hOutcomePanel" in Path("public/h2h-v08.js").read_text(encoding="utf-8")
    assert "Estimated live score" in Path("public/h2h-v08.js").read_text(encoding="utf-8")
