from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
PAGE = PUBLIC / "standard-fpl-viewer.html"
SCRIPT = PUBLIC / "standard-fpl-viewer.js"
STYLES = PUBLIC / "standard-fpl-viewer.css"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_private_viewer_is_standalone_from_public_draft_dashboard():
    page = _text(PAGE)
    dashboard = _text(PUBLIC / "index.html")

    assert "standard-fpl-viewer" not in dashboard
    assert "standard-fpl-viewer.css" in page
    assert "standard-fpl-viewer.js" in page
    assert "app.js" not in page
    assert "data/latest.json" not in page


def test_viewer_uses_only_a_local_json_file_and_no_browser_persistence():
    page = _text(PAGE)
    script = _text(SCRIPT)

    assert 'type="file"' in page
    assert 'accept="application/json,.json"' in page
    assert "file.text()" in script
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "sendBeacon",
    ):
        assert forbidden not in script


def test_viewer_rejects_identity_credentials_and_wrong_mode():
    script = _text(SCRIPT)

    for marker in (
        '"entry_id"',
        '"owner_entry_id"',
        '"owner_raw"',
        '"access_token"',
        '"refresh_token"',
        '"password"',
        'report.mode !== "standard_fpl"',
        "report.squad_outlook",
        "report.transfer_decision",
    ):
        assert marker in script


def test_viewer_renders_with_dom_text_nodes_instead_of_html_injection():
    script = _text(SCRIPT)

    assert "document.createElement" in script
    assert ".textContent" in script
    assert ".innerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "eval(" not in script


def test_viewer_exposes_current_decision_lineup_outlook_and_outcomes():
    page = _text(PAGE)
    script = _text(SCRIPT)

    for marker in (
        "Hold or transfer",
        "Recommended XI",
        "Four-Gameweek squad outlook",
        "Top single transfers",
        "Outcome tracking",
        "Clear private report",
    ):
        assert marker in page
    for marker in (
        "renderDecision",
        "renderLineup",
        "renderOutlook",
        "renderCandidates",
        "renderOutcomes",
        "selection_pressure",
        "core_starters",
        "rotation_players",
    ):
        assert marker in script


def test_viewer_copy_states_the_hands_on_privacy_boundary():
    page = _text(PAGE)

    for marker in (
        "Nothing is uploaded",
        "this tab’s memory",
        "Refreshing or pressing Clear removes it",
        "not the future hosted Standard FPL mode",
        "shared Draft dashboard remains separate",
    ):
        assert marker in page


def test_viewer_css_has_desktop_and_mobile_layouts():
    styles = _text(STYLES)

    assert "grid-template-columns: repeat(4" in styles
    assert "@media (max-width: 860px)" in styles
    assert "@media (max-width: 560px)" in styles
