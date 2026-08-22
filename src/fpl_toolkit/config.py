from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from urllib.parse import urlparse


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    draft_entry_id: str
    draft_league_id: str | None = None
    planning_horizon: int = 4
    output_dir: str = "data"

    @classmethod
    def from_env(cls) -> "Settings":
        entry_id = os.getenv("FPL_DRAFT_ENTRY_ID", "").strip()
        league_id = os.getenv("FPL_DRAFT_LEAGUE_ID", "").strip() or None
        horizon_raw = os.getenv("FPL_PLANNING_HORIZON", "4").strip()
        output_dir = os.getenv("FPL_OUTPUT_DIR", "data").strip() or "data"

        if not entry_id:
            raise ConfigError("FPL_DRAFT_ENTRY_ID is required.")
        if not re.fullmatch(r"[0-9]+", entry_id):
            raise ConfigError(
                "FPL_DRAFT_ENTRY_ID must be the numeric Draft entry ID from a URL "
                "such as https://draft.premierleague.com/entry/23977/edit. "
                "A Premier League account/profile UUID is not the Draft entry ID."
            )
        if league_id is not None and not re.fullmatch(r"[0-9]+", league_id):
            raise ConfigError("FPL_DRAFT_LEAGUE_ID must be numeric when provided.")
        try:
            horizon = int(horizon_raw)
        except ValueError as exc:
            raise ConfigError("FPL_PLANNING_HORIZON must be an integer.") from exc
        if horizon < 1 or horizon > 10:
            raise ConfigError("FPL_PLANNING_HORIZON must be between 1 and 10.")

        return cls(
            draft_entry_id=entry_id,
            draft_league_id=league_id,
            planning_horizon=horizon,
            output_dir=output_dir,
        )


def standard_entry_id_from_url(value: str) -> str | None:
    """Extract a standard FPL entry ID from an ordinary manager-facing URL."""
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    if (parsed.hostname or "").lower() != "fantasy.premierleague.com":
        return None
    match = re.search(r"/(?:en/)?entry/([0-9]+)(?:/|$)", parsed.path)
    return match.group(1) if match and int(match.group(1)) > 0 else None


@dataclass(frozen=True)
class StandardFplSettings:
    entry_id: str
    planning_horizon: int = 4
    output_path: str = "data/private/standard-fpl-poc.json"
    squad_gameweek: int | None = None
    performance_baseline_path: str = "data/state/performance-baseline.json"

    @classmethod
    def from_env(cls) -> "StandardFplSettings":
        entry_id = os.getenv("FPL_STANDARD_ENTRY_ID", "").strip()
        entry_url = os.getenv("FPL_STANDARD_ENTRY_URL", "").strip()
        if entry_url:
            url_entry_id = standard_entry_id_from_url(entry_url)
            if url_entry_id is None:
                raise ConfigError(
                    "FPL_STANDARD_ENTRY_URL must be an ordinary standard FPL entry URL such as "
                    "https://fantasy.premierleague.com/en/entry/123456/event/1."
                )
            if entry_id and entry_id != url_entry_id:
                raise ConfigError("FPL_STANDARD_ENTRY_ID and FPL_STANDARD_ENTRY_URL refer to different entries.")
            entry_id = url_entry_id
        if not entry_id:
            raise ConfigError("FPL_STANDARD_ENTRY_URL or FPL_STANDARD_ENTRY_ID is required.")
        if not re.fullmatch(r"[0-9]+", entry_id) or int(entry_id) <= 0:
            raise ConfigError("FPL_STANDARD_ENTRY_ID must be a positive numeric standard FPL entry ID.")

        horizon_raw = os.getenv("FPL_PLANNING_HORIZON", "4").strip()
        output_path = os.getenv("FPL_STANDARD_OUTPUT", "data/private/standard-fpl-poc.json").strip()
        baseline_path = os.getenv(
            "FPL_PERFORMANCE_BASELINE_PATH", "data/state/performance-baseline.json"
        ).strip()
        squad_gameweek_raw = os.getenv("FPL_STANDARD_SQUAD_GAMEWEEK", "").strip()
        try:
            horizon = int(horizon_raw)
        except ValueError as exc:
            raise ConfigError("FPL_PLANNING_HORIZON must be an integer.") from exc
        if horizon < 1 or horizon > 10:
            raise ConfigError("FPL_PLANNING_HORIZON must be between 1 and 10.")
        try:
            squad_gameweek = int(squad_gameweek_raw) if squad_gameweek_raw else None
        except ValueError as exc:
            raise ConfigError("FPL_STANDARD_SQUAD_GAMEWEEK must be an integer.") from exc
        if squad_gameweek is not None and not 1 <= squad_gameweek <= 38:
            raise ConfigError("FPL_STANDARD_SQUAD_GAMEWEEK must be between 1 and 38.")
        if not output_path:
            raise ConfigError("FPL_STANDARD_OUTPUT must not be empty.")
        private_root = Path("data/private").resolve()
        resolved_output = Path(output_path).resolve()
        if resolved_output != private_root and private_root not in resolved_output.parents:
            raise ConfigError("FPL_STANDARD_OUTPUT must remain inside the gitignored data/private directory.")

        return cls(
            entry_id=entry_id,
            planning_horizon=horizon,
            output_path=output_path,
            squad_gameweek=squad_gameweek,
            performance_baseline_path=baseline_path,
        )
