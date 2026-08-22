from pathlib import Path


def test_frontend_exposes_snapshot_freshness_states_and_mobile_warning():
    app = Path("public/app.js").read_text(encoding="utf-8")
    styles = Path("public/styles.css").read_text(encoding="utf-8")
    index = Path("public/index.html").read_text(encoding="utf-8")

    assert "STALE_AFTER_MS = 6 * 60 * 60 * 1000" in app
    assert "CRITICAL_AFTER_MS = 12 * 60 * 60 * 1000" in app
    assert "REPORT_POLL_MS = 15 * 60 * 1000" in app
    assert "function snapshotHealth" in app
    assert "function snapshotWarningMarkup" in app
    assert "function loadReport" in app
    assert "setInterval(loadReport, REPORT_POLL_MS)" in app
    assert 'role="status"' in app
    assert ".freshness-warning" in styles
    assert "app.js?v=20260822.1" in index
    assert "styles.css?v=20260821.3" in index


def test_collection_workflow_prevents_overlap_and_has_timeouts():
    workflow = Path(".github/workflows/collect.yml").read_text(encoding="utf-8")

    assert "group: collect-fpl-draft-state" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "timeout-minutes: 15" in workflow
    assert "timeout-minutes: 10" in workflow
