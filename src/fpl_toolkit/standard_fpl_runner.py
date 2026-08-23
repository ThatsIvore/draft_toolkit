from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
from typing import Any, Callable
from urllib.parse import urlsplit

from .api import FPLApiError, FantasyApiClient
from .config import StandardFplSettings, standard_entry_id_from_url
from .intelligence import MODEL_VERSION
from .standard_fpl import StandardFplDataError, collect_standard_fpl
from .standard_fpl_snapshot import StandardFplSnapshotError


SERVICE_VERSION = "standard-fpl-runner-v1"
DEFAULT_MAX_REQUEST_BYTES = 256 * 1024
MAX_ENTRY_URL_BYTES = 512
ASSET_NAMES = {
    "standard-fpl-runner.html": "text/html; charset=utf-8",
    "standard-fpl-runner.js": "text/javascript; charset=utf-8",
    "standard-fpl-viewer.js": "text/javascript; charset=utf-8",
    "standard-fpl-viewer.css": "text/css; charset=utf-8",
}
FORBIDDEN_PRIVATE_KEYS = {
    "access_token",
    "authorization",
    "cookie",
    "credentials",
    "id_token",
    "password",
    "refresh_token",
    "session",
    "session_id",
}
FORBIDDEN_REPORT_KEYS = FORBIDDEN_PRIVATE_KEYS | {
    "entry_id",
    "owner_entry_id",
    "owner_name",
    "owner_raw",
}
FORBIDDEN_CREDENTIAL_MARKERS = (
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "session",
    "token",
)


class RunnerRequestError(ValueError):
    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class RunnerConfig:
    bind: str = "127.0.0.1"
    port: int = 8787
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES
    request_timeout_seconds: int = 15
    upstream_timeout_seconds: int = 15
    planning_horizon: int = 4
    asset_dir: Path = Path("public")
    performance_baseline_path: str = "data/state/performance-baseline.json"

    @classmethod
    def from_env(cls) -> "RunnerConfig":
        bind = os.getenv("FPL_RUNNER_BIND", "127.0.0.1").strip() or "127.0.0.1"
        asset_dir = Path(os.getenv("FPL_RUNNER_ASSET_DIR", "public").strip() or "public")
        baseline_path = os.getenv(
            "FPL_PERFORMANCE_BASELINE_PATH", "data/state/performance-baseline.json"
        ).strip()
        try:
            port = int(os.getenv("FPL_RUNNER_PORT", "8787"))
            max_request_bytes = int(
                os.getenv("FPL_RUNNER_MAX_REQUEST_BYTES", str(DEFAULT_MAX_REQUEST_BYTES))
            )
            request_timeout = int(os.getenv("FPL_RUNNER_REQUEST_TIMEOUT_SECONDS", "15"))
            upstream_timeout = int(os.getenv("FPL_RUNNER_UPSTREAM_TIMEOUT_SECONDS", "15"))
            planning_horizon = int(os.getenv("FPL_PLANNING_HORIZON", "4"))
        except ValueError as exc:
            raise RunnerRequestError("Runner numeric configuration is invalid.") from exc
        if not 1 <= port <= 65535:
            raise RunnerRequestError("FPL_RUNNER_PORT must be between 1 and 65535.")
        if not 16 * 1024 <= max_request_bytes <= 1024 * 1024:
            raise RunnerRequestError(
                "FPL_RUNNER_MAX_REQUEST_BYTES must be between 16384 and 1048576."
            )
        if not 1 <= request_timeout <= 60 or not 1 <= upstream_timeout <= 60:
            raise RunnerRequestError("Runner timeouts must be between 1 and 60 seconds.")
        if not 1 <= planning_horizon <= 10:
            raise RunnerRequestError("FPL_PLANNING_HORIZON must be between 1 and 10.")
        if not asset_dir.is_dir():
            raise RunnerRequestError(f"Runner asset directory does not exist: {asset_dir}.")
        missing = sorted(name for name in ASSET_NAMES if not (asset_dir / name).is_file())
        if missing:
            raise RunnerRequestError(f"Runner assets are missing: {', '.join(missing)}.")
        return cls(
            bind=bind,
            port=port,
            max_request_bytes=max_request_bytes,
            request_timeout_seconds=request_timeout,
            upstream_timeout_seconds=upstream_timeout,
            planning_horizon=planning_horizon,
            asset_dir=asset_dir,
            performance_baseline_path=baseline_path,
        )


def _scan_forbidden_keys(value: Any, forbidden: set[str], path: str = "payload") -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _scan_forbidden_keys(item, forbidden, f"{path}[{index}]")
        return
    if not isinstance(value, dict):
        return
    for key, child in value.items():
        normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
        if normalized in forbidden or any(marker in normalized for marker in FORBIDDEN_CREDENTIAL_MARKERS):
            raise RunnerRequestError(
                f"The upload contains forbidden credential or identity field {path}.{key}.",
                HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        _scan_forbidden_keys(child, forbidden, f"{path}.{key}")


def parse_multipart_request(content_type: str, body: bytes) -> tuple[str, dict[str, Any]]:
    if not content_type.lower().startswith("multipart/form-data;"):
        raise RunnerRequestError("Use multipart/form-data for the private snapshot upload.")
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
        + body
    )
    if not message.is_multipart():
        raise RunnerRequestError("The multipart upload could not be parsed.")
    fields: dict[str, bytes] = {}
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            raise RunnerRequestError("Every upload part must use form-data disposition.")
        name = part.get_param("name", header="content-disposition")
        if name not in {"entry_url", "snapshot"}:
            raise RunnerRequestError(f"Unexpected upload field: {name or 'unnamed'}.")
        if name in fields:
            raise RunnerRequestError(f"Upload field {name} must appear exactly once.")
        fields[name] = part.get_payload(decode=True) or b""
    missing = sorted({"entry_url", "snapshot"} - set(fields))
    if missing:
        raise RunnerRequestError(f"Upload is missing fields: {', '.join(missing)}.")
    if len(fields["entry_url"]) > MAX_ENTRY_URL_BYTES:
        raise RunnerRequestError("The FPL entry URL is too long.")
    try:
        entry_url = fields["entry_url"].decode("utf-8").strip()
        snapshot = json.loads(fields["snapshot"].decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise RunnerRequestError("Upload fields must use UTF-8 text.") from exc
    except json.JSONDecodeError as exc:
        raise RunnerRequestError("The snapshot file is not valid JSON.") from exc
    if standard_entry_id_from_url(entry_url) is None:
        raise RunnerRequestError(
            "Use an ordinary fantasy.premierleague.com entry URL, for example "
            "https://fantasy.premierleague.com/en/entry/123456/event/1."
        )
    if not isinstance(snapshot, dict):
        raise RunnerRequestError("The snapshot file must contain one JSON object.")
    _scan_forbidden_keys(snapshot, FORBIDDEN_PRIVATE_KEYS)
    return entry_url, snapshot


def build_ephemeral_report(
    entry_url: str,
    snapshot: dict[str, Any],
    config: RunnerConfig,
    client: FantasyApiClient | None = None,
) -> dict[str, Any]:
    entry_id = standard_entry_id_from_url(entry_url)
    if entry_id is None:
        raise RunnerRequestError("The Standard FPL entry URL is invalid.")
    settings = StandardFplSettings(
        entry_id=entry_id,
        planning_horizon=config.planning_horizon,
        output_path="data/private/runner-unused.json",
        performance_baseline_path=config.performance_baseline_path,
    )
    report = collect_standard_fpl(
        settings,
        client=client or FantasyApiClient(
            timeout_seconds=config.upstream_timeout_seconds,
            max_attempts=2,
        ),
        previous_report={},
        private_snapshot=snapshot,
    )
    _scan_forbidden_keys(report, FORBIDDEN_REPORT_KEYS, path="report")
    return report


ReportBuilder = Callable[[str, dict[str, Any], RunnerConfig], dict[str, Any]]


def make_handler(
    config: RunnerConfig,
    report_builder: ReportBuilder = build_ephemeral_report,
) -> type[BaseHTTPRequestHandler]:
    class StandardFplRunnerHandler(BaseHTTPRequestHandler):
        server_version = "FPLToolkitRunner/1"
        sys_version = ""

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(config.request_timeout_seconds)

        def log_message(self, format: str, *args: Any) -> None:
            # Request bodies, query strings and reports must never enter logs.
            return

        def _headers(self, status: HTTPStatus, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()

        def _send_bytes(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
            self._headers(status, content_type, len(body))
            self.wfile.write(body)

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            self._send_bytes(status, "application/json; charset=utf-8", body)

        def _asset(self, name: str) -> None:
            if name not in ASSET_NAMES:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            try:
                body = (config.asset_dir / name).read_bytes()
            except OSError:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "asset_unavailable"})
                return
            self._send_bytes(HTTPStatus.OK, ASSET_NAMES[name], body)

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/health":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "status": "ok",
                        "service": SERVICE_VERSION,
                        "model": MODEL_VERSION,
                        "storage": "ephemeral",
                    },
                )
                return
            if path == "/":
                self._asset("standard-fpl-runner.html")
                return
            if path.startswith("/"):
                self._asset(path[1:])

        def do_POST(self) -> None:
            if urlsplit(self.path).path != "/api/standard-fpl/report":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            if self.headers.get("Transfer-Encoding"):
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "unsupported_transfer_encoding", "message": "Chunked uploads are not supported."},
                )
                return
            origin = self.headers.get("Origin")
            host = self.headers.get("Host")
            fetch_site = (self.headers.get("Sec-Fetch-Site") or "").lower()
            if fetch_site == "cross-site" or (
                origin and host and (urlsplit(origin).netloc or "").lower() != host.lower()
            ):
                self._send_json(
                    HTTPStatus.FORBIDDEN,
                    {"error": "cross_origin_request", "message": "Use the runner page on this server."},
                )
                return
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                self._send_json(
                    HTTPStatus.LENGTH_REQUIRED,
                    {"error": "length_required", "message": "Content-Length is required."},
                )
                return
            try:
                content_length = int(raw_length)
            except ValueError:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_length", "message": "Content-Length is invalid."},
                )
                return
            if content_length <= 0 or content_length > config.max_request_bytes:
                self._send_json(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    {
                        "error": "request_too_large",
                        "message": f"Upload must be smaller than {config.max_request_bytes} bytes.",
                    },
                )
                return
            try:
                body = self.rfile.read(content_length)
                if len(body) != content_length:
                    raise RunnerRequestError("The upload ended before Content-Length bytes arrived.")
                entry_url, snapshot = parse_multipart_request(
                    self.headers.get("Content-Type", ""), body
                )
                report = report_builder(entry_url, snapshot, config)
                self._send_json(HTTPStatus.OK, report)
            except RunnerRequestError as exc:
                self._send_json(exc.status, {"error": "invalid_request", "message": str(exc)})
            except (StandardFplSnapshotError, StandardFplDataError) as exc:
                self._send_json(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {"error": "invalid_snapshot", "message": str(exc)},
                )
            except FPLApiError:
                self._send_json(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "error": "fpl_unavailable",
                        "message": "Official FPL data is temporarily unavailable. Try again shortly.",
                    },
                )
            except (ConnectionError, TimeoutError, socket.timeout):
                self._send_json(
                    HTTPStatus.GATEWAY_TIMEOUT,
                    {"error": "request_timeout", "message": "The report request timed out."},
                )
            except Exception:
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "internal_error", "message": "The private report could not be generated."},
                )

        def do_PUT(self) -> None:
            self._send_json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "read_only"})

        do_PATCH = do_PUT
        do_DELETE = do_PUT

    return StandardFplRunnerHandler


def create_server(
    config: RunnerConfig,
    report_builder: ReportBuilder = build_ephemeral_report,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((config.bind, config.port), make_handler(config, report_builder))


def main() -> int:
    try:
        config = RunnerConfig.from_env()
        server = create_server(config)
    except (OSError, RunnerRequestError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(
        f"Standard FPL runner {SERVICE_VERSION} listening on "
        f"http://{config.bind}:{server.server_port} (ephemeral, read-only)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
