from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
BOOKMARKLET = PUBLIC / "standard-fpl-snapshot-bookmarklet.js"
INSTALLER = PUBLIC / "standard-fpl-snapshot-helper.js"
PAGE = PUBLIC / "standard-fpl-snapshot-helper.html"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_snapshot_helper_is_standalone_from_the_draft_dashboard():
    dashboard = _text(PUBLIC / "index.html")
    helper = _text(PAGE)

    assert "standard-fpl-snapshot-helper" not in dashboard
    assert "standard-fpl-snapshot-helper.css" in helper
    assert "standard-fpl-snapshot-helper.js" in helper
    assert "app.js" not in helper
    assert "data.js" not in helper


def test_bookmarklet_has_a_narrow_origin_and_network_boundary():
    source = _text(BOOKMARKLET)

    assert 'const FPL_ORIGIN = "https://fantasy.premierleague.com"' in source
    assert 'location.origin !== FPL_ORIGIN' in source
    assert "/api/bootstrap-static/" in source
    assert 'credentials: "omit"' in source
    assert "/api/my-team" not in source
    assert source.count("fetch(") == 1
    assert 'window.open(historyUrl.href, "draft_toolkit_fpl_history"' in source
    assert '/^\\/en\\/entry\\/\\d+\\/transfers' in source
    assert '/^\\/en\\/entry\\/\\d+\\/event\\/\\d+' in source


def test_bookmarklet_does_not_read_credentials_or_existing_browser_state():
    source = _text(BOOKMARKLET)
    forbidden = (
        "localStorage",
        "document.cookie",
        "Authorization",
        "access_token",
        "refresh_token",
        "id_token",
        "indexedDB",
    )

    for marker in forbidden:
        assert marker not in source

    assert source.count("sessionStorage.setItem(STAGE_KEY") == 1
    assert source.count("sessionStorage.getItem(STAGE_KEY") == 1
    assert source.count("sessionStorage.removeItem(STAGE_KEY") == 2
    assert "sessionStorage.key(" not in source
    assert "Object.keys(sessionStorage" not in source


def test_bookmarklet_emits_only_the_private_snapshot_contract():
    source = _text(BOOKMARKLET)

    assert 'const SNAPSHOT_VERSION = "standard-fpl-private-snapshot-v1"' in source
    for field in (
        "player_id",
        "lineup_position",
        "multiplier",
        "is_captain",
        "is_vice_captain",
        "purchase_price_tenths",
        "selling_price_tenths",
        "bank_tenths",
        "squad_value_tenths",
        "free_transfers",
        "transfers_made",
        "played_gameweek",
    ):
        assert field in source

    final_block = source[source.index("const snapshot = validateSnapshot({") :]
    for forbidden_field in ("entry_id", "account_id", "email", "team_name"):
        assert forbidden_field not in final_block


def test_bookmarklet_is_read_only_for_fpl_team_controls():
    source = _text(BOOKMARKLET)

    assert 'assertNoPendingChanges("Save Team")' in source
    assert 'assertNoPendingChanges("Make Transfers")' in source
    assert "button.click(" not in source
    assert re.search(r"\blink\.click\(\)", source)
    assert 'location.assign("/en/transfers")' in source


def test_installer_builds_bookmarklet_without_request_credentials():
    source = _text(INSTALLER)

    assert 'fetch("standard-fpl-snapshot-bookmarklet.js"' in source
    assert 'credentials: "omit"' in source
    assert "encodeURIComponent(source)" in source
    assert "javascript:${encodeURIComponent(source)}" in source
    assert "javascript:${source}" not in source


def test_helper_page_explains_two_stage_capture_and_private_destination():
    page = _text(PAGE)

    for marker in (
        "Pick Team",
        "Selling Price",
        "Transfers",
        "Transfer History window",
        "data/private/current-team.json",
        "never handles the sign-in",
        "never presses Save Team, Make Transfers or a chip control",
        "not the future paid onboarding flow",
    ):
        assert marker in page
