from __future__ import annotations

from contextlib import contextmanager
from http.client import HTTPConnection
from http import HTTPStatus
import json
from pathlib import Path
from threading import Thread

from fpl_toolkit.standard_fpl import StandardFplDataError
from fpl_toolkit.standard_fpl_runner import RunnerConfig, create_server


ENTRY_URL = "https://fantasy.premierleague.com/en/entry/123456/event/1"


def _config(**overrides):
    values = {
        "bind": "127.0.0.1",
        "port": 0,
        "max_request_bytes": 16 * 1024,
        "request_timeout_seconds": 3,
        "upstream_timeout_seconds": 3,
        "planning_horizon": 4,
        "asset_dir": Path("public"),
        "performance_baseline_path": "data/state/performance-baseline.json",
    }
    values.update(overrides)
    return RunnerConfig(**values)


@contextmanager
def _running(builder, config=None):
    server = create_server(config or _config(), report_builder=builder)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _multipart(fields, boundary="runner-boundary"):
    body = bytearray()
    for name, value in fields:
        body.extend(f"--{boundary}\r\n".encode())
        if name == "snapshot":
            body.extend(
                b'Content-Disposition: form-data; name="snapshot"; filename="snapshot.json"\r\n'
                b"Content-Type: application/json\r\n\r\n"
            )
        else:
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value if isinstance(value, bytes) else str(value).encode())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _request(port, method, path, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    payload = response.read()
    result = response.status, dict(response.getheaders()), payload
    connection.close()
    return result


def _success_report():
    return {
        "mode": "standard_fpl",
        "poc_version": "phase-1-v0.6",
        "decision_gameweek": 2,
        "planning_gameweeks": [2, 3, 4, 5],
        "recommended_lineup": {"starters": []},
        "squad_outlook": {"rounds": []},
        "transfer_decision": {},
    }


def test_health_and_assets_are_private_no_store_responses():
    with _running(lambda *_: _success_report()) as port:
        status, headers, body = _request(port, "GET", "/health")
        page_status, _, page = _request(port, "GET", "/")

    health = json.loads(body)
    assert status == HTTPStatus.OK
    assert health == {
        "status": "ok",
        "service": "standard-fpl-runner-v1",
        "model": "v0.6.0",
        "storage": "ephemeral",
    }
    assert headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "Access-Control-Allow-Origin" not in headers
    assert page_status == HTTPStatus.OK
    assert b"Standard FPL Private Runner" in page


def test_report_endpoint_accepts_only_expected_sanitized_fields():
    captured = {}

    def builder(entry_url, snapshot, config):
        captured.update(entry_url=entry_url, snapshot=snapshot, config=config)
        return _success_report()

    body, content_type = _multipart(
        [("entry_url", ENTRY_URL), ("snapshot", json.dumps({"schema_version": "test"}))]
    )
    with _running(builder) as port:
        status, headers, response_body = _request(
            port,
            "POST",
            "/api/standard-fpl/report",
            body,
            {"Content-Type": content_type, "Content-Length": str(len(body))},
        )

    assert status == HTTPStatus.OK
    assert json.loads(response_body)["mode"] == "standard_fpl"
    assert headers["Cache-Control"] == "no-store"
    assert captured["entry_url"] == ENTRY_URL
    assert captured["snapshot"] == {"schema_version": "test"}


def test_report_endpoint_rejects_malformed_unexpected_and_credential_uploads():
    builder = lambda *_: _success_report()
    cases = [
        _multipart([("entry_url", ENTRY_URL), ("snapshot", b"not-json")]),
        _multipart(
            [
                ("entry_url", ENTRY_URL),
                ("snapshot", b"{}"),
                ("cookie", "secret"),
            ]
        ),
        _multipart(
            [
                ("entry_url", ENTRY_URL),
                ("snapshot", json.dumps({"nested": {"access-token": "secret"}})),
            ]
        ),
    ]
    with _running(builder) as port:
        responses = [
            _request(
                port,
                "POST",
                "/api/standard-fpl/report",
                body,
                {"Content-Type": content_type, "Content-Length": str(len(body))},
            )
            for body, content_type in cases
        ]

    assert [status for status, _, _ in responses] == [400, 400, 422]
    assert b"not valid JSON" in responses[0][2]
    assert b"Unexpected upload field" in responses[1][2]
    assert b"forbidden credential" in responses[2][2]
    assert b"secret" not in b"".join(response[2] for response in responses)


def test_report_endpoint_rejects_oversized_body_before_reading_it():
    with _running(lambda *_: _success_report()) as port:
        status, _, body = _request(
            port,
            "POST",
            "/api/standard-fpl/report",
            b"x" * (16 * 1024 + 1),
            {"Content-Type": "multipart/form-data; boundary=x"},
        )

    assert status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert json.loads(body)["error"] == "request_too_large"


def test_report_endpoint_rejects_cross_origin_browser_posts():
    body, content_type = _multipart([("entry_url", ENTRY_URL), ("snapshot", b"{}")])
    with _running(lambda *_: _success_report()) as port:
        status, _, response_body = _request(
            port,
            "POST",
            "/api/standard-fpl/report",
            body,
            {
                "Content-Type": content_type,
                "Content-Length": str(len(body)),
                "Origin": "https://attacker.example",
                "Sec-Fetch-Site": "cross-site",
            },
        )

    assert status == HTTPStatus.FORBIDDEN
    assert json.loads(response_body)["error"] == "cross_origin_request"


def test_stale_snapshot_errors_are_actionable_and_write_methods_are_blocked():
    def stale(*_):
        raise StandardFplDataError(
            "The private snapshot is for Gameweek 1, but the next actionable Gameweek is 2. Capture a fresh snapshot."
        )

    body, content_type = _multipart([("entry_url", ENTRY_URL), ("snapshot", b"{}")])
    with _running(stale) as port:
        stale_status, _, stale_body = _request(
            port,
            "POST",
            "/api/standard-fpl/report",
            body,
            {"Content-Type": content_type, "Content-Length": str(len(body))},
        )
        delete_status, _, delete_body = _request(port, "DELETE", "/api/standard-fpl/report")

    assert stale_status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert b"Capture a fresh snapshot" in stale_body
    assert delete_status == HTTPStatus.METHOD_NOT_ALLOWED
    assert json.loads(delete_body)["error"] == "read_only"


def test_runner_frontend_uses_same_origin_memory_only_flow():
    html = Path("public/standard-fpl-runner.html").read_text(encoding="utf-8")
    script = Path("public/standard-fpl-runner.js").read_text(encoding="utf-8")
    viewer = Path("public/standard-fpl-viewer.js").read_text(encoding="utf-8")

    assert "LAN-only POC" in html
    assert "without being written to disk" in html
    assert 'fetch("/api/standard-fpl/report"' in script
    assert 'credentials: "same-origin"' in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "window.standardFplReportViewer" in viewer


def test_runner_packaging_keeps_private_state_out_of_the_image_and_public_pipeline():
    dockerfile = Path("Dockerfile.standard-fpl-runner").read_text(encoding="utf-8")
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")
    project = Path("pyproject.toml").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/collect.yml").read_text(encoding="utf-8")

    assert 'fpl-toolkit-runner = "fpl_toolkit.standard_fpl_runner:main"' in project
    assert "USER app" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "VOLUME" not in dockerfile
    assert "data/private" in dockerignore
    assert "public/data" in dockerignore
    assert "fpl-toolkit-runner" not in workflow


def test_runner_defaults_to_loopback_outside_the_container(monkeypatch):
    monkeypatch.delenv("FPL_RUNNER_BIND", raising=False)
    monkeypatch.setenv("FPL_RUNNER_ASSET_DIR", "public")

    config = RunnerConfig.from_env()

    assert config.bind == "127.0.0.1"
    assert config.max_request_bytes == 256 * 1024
