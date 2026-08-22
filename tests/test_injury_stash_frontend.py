from pathlib import Path


def test_injury_stash_dashboard_is_wired_into_navigation_and_hash_routing():
    index = Path("public/index.html").read_text(encoding="utf-8")
    app = Path("public/app.js").read_text(encoding="utf-8")
    interaction = Path("public/interaction.js").read_text(encoding="utf-8")

    assert 'data-view="injury"' in index
    assert "injury-stash-v10.css?v=20260822.1" in index
    assert "injury-stash-v10.js?v=20260822.1" in index
    assert 'data-view-link="injury"' in app
    assert "'injury'" in interaction


def test_injury_dashboard_stays_decision_focused():
    source = Path("public/injury-stash-v10.js").read_text(encoding="utf-8")
    about = Path("public/about.html").read_text(encoding="utf-8")

    assert "Your squad health" in source
    assert "Stash radar" in source
    assert "Return window" in source
    assert "this is not the full injury list" in source
    assert "not a directory of every unavailable Premier League player" in about
    assert "Post-return Fixtures" in about


def test_player_drawer_explains_return_aligned_fixture_score():
    source = Path("public/intelligence-v3.js").read_text(encoding="utf-8")

    assert "post_return_fixture_score" in source
    assert "Fixtures before that return are not credited" in source
