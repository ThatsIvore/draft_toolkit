from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import requests


class FPLApiError(RuntimeError):
    pass


def _get_json(url: str, timeout_seconds: int, user_agent: str) -> Any:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise FPLApiError(f"GET {url} failed: {exc}") from exc


@dataclass
class DraftApiClient:
    base_url: str = "https://draft.premierleague.com/api"
    timeout_seconds: int = 25
    user_agent: str = "fpl-season-toolkit/0.1"

    def _get(self, path: str) -> Any:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        return _get_json(url, self.timeout_seconds, self.user_agent)

    def bootstrap_static(self) -> dict[str, Any]:
        return self._get("bootstrap-static")

    def entry_public(self, entry_id: str) -> dict[str, Any]:
        return self._get(f"entry/{entry_id}/public")

    def entry_event(self, entry_id: str, gameweek: int) -> dict[str, Any] | list[dict[str, Any]]:
        return self._get(f"entry/{entry_id}/event/{gameweek}")

    def league_details(self, league_id: str) -> dict[str, Any]:
        return self._get(f"league/{league_id}/details")

    def element_status(self, league_id: str) -> dict[str, Any] | list[dict[str, Any]]:
        return self._get(f"league/{league_id}/element-status")

    def transactions(self, entry_id: str) -> dict[str, Any] | list[dict[str, Any]]:
        return self._get(f"draft/entry/{entry_id}/transactions")


@dataclass
class FantasyApiClient:
    base_url: str = "https://fantasy.premierleague.com/api"
    timeout_seconds: int = 25
    user_agent: str = "fpl-season-toolkit/0.1"

    def fixtures(self) -> list[dict[str, Any]]:
        payload = _get_json(
            f"{self.base_url.rstrip('/')}/fixtures/",
            self.timeout_seconds,
            self.user_agent,
        )
        if not isinstance(payload, list):
            raise FPLApiError("FPL fixtures endpoint returned an unexpected payload.")
        return [row for row in payload if isinstance(row, dict)]
