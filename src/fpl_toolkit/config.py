from __future__ import annotations

from dataclasses import dataclass
import os
import re


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
