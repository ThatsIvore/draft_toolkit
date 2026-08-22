from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .api import FPLApiError
from .collector import collect
from .config import ConfigError, Settings, StandardFplSettings
from .normalize import LeagueDiscoveryError
from .privacy import sanitize_public_report
from .standard_fpl import StandardFplDataError, collect_standard_fpl
from .storage import write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an FPL Draft or private standard FPL decision report.")
    parser.add_argument(
        "--mode",
        choices=("draft", "standard-fpl"),
        default="draft",
        help="Keep the existing Draft collector or run the private Standard FPL Phase 1 POC.",
    )
    parser.add_argument("--publish", action="store_true", help="Write a redacted report to public/data/latest.json")
    args = parser.parse_args()
    try:
        if args.mode == "standard-fpl":
            if args.publish:
                raise ConfigError("The Standard FPL POC is private and cannot be used with --publish.")
            standard_settings = StandardFplSettings.from_env()
            report = collect_standard_fpl(standard_settings)
            output_path = Path(standard_settings.output_path)
            write_json(output_path, report)
            summary = dict(report["summary"])
            summary.update({
                "mode": report["mode"],
                "squad_source_gameweek": report["squad_source"]["gameweek"],
                "decision_gameweek": report["decision_gameweek"],
                "output": str(output_path),
            })
            print(json.dumps(summary, indent=2))
            return 0
        settings = Settings.from_env()
        report = collect(settings)
        if args.publish:
            write_json(Path("public/data/latest.json"), sanitize_public_report(report))
        print(json.dumps(report["summary"], indent=2))
        return 0
    except (ConfigError, FPLApiError, LeagueDiscoveryError, StandardFplDataError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
