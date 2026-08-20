from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .api import FPLApiError
from .collector import collect
from .config import ConfigError, Settings
from .normalize import LeagueDiscoveryError
from .privacy import sanitize_public_report
from .storage import write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect FPL Draft league state and build a POC report.")
    parser.add_argument("--publish", action="store_true", help="Write a redacted report to public/data/latest.json")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        report = collect(settings)
        if args.publish:
            write_json(Path("public/data/latest.json"), sanitize_public_report(report))
        print(json.dumps(report["summary"], indent=2))
        return 0
    except (ConfigError, FPLApiError, LeagueDiscoveryError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
