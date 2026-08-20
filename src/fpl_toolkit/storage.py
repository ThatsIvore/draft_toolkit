from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def newest_snapshot(snapshot_dir: Path) -> Path | None:
    paths = sorted(snapshot_dir.glob("ownership-*.json"))
    return paths[-1] if paths else None
