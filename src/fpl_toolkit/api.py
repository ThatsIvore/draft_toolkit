from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
import requests


class FPLApiError(RuntimeError):
    pass


def _get_json(
    url: str,
    timeout_seconds: int,
    user_agent: str,
    max_attempts: int = 3,
    retry_backoff_seconds: float = 1.0,
) -> Any:
    attempts = max(1, int(max_attempts))
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": user_agent, "Accept": "application/json"},
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            retryable = True
        except requests.HTTPError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else None
            retryable = status == 429 or bool(status and status >= 500)
        except (requests.RequestException, ValueError) as exc:
            raise FPLApiError(f"GET {url} failed: {exc}") from exc
        if not retryable or attempt == attempts - 1:
            raise FPLApiError(f"GET {url} failed after {attempt + 1} attempt(s): {last_error}") from last_error
        time.sleep(max(0.0, retry_backoff_seconds) * (2 ** attempt))
    raise FPLApiError(f"GET {url} failed without a response.")


@dataclass
class DraftApiClient:
    base_url: str = "https://draft.premierleague.com/api"
    timeout_seconds: int = 25
    user_agent: str = "fpl-season-toolkit/0.1"
    max_attempts: int = 3
    retry_backoff_seconds: float = 1.0

    def _get(self, path: str) -> Any:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        return _get_json(
            url,
            self.timeout_seconds,
            self.user_agent,
            self.max_attempts,
            self.retry_backoff_seconds,
        )

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
    max_attempts: int = 3
    retry_backoff_seconds: float = 1.0

    def _get(self, path: str) -> Any:
        return _get_json(
            f"{self.base_url.rstrip('/')}/{path.lstrip('/')}",
            self.timeout_seconds,
            self.user_agent,
            self.max_attempts,
            self.retry_backoff_seconds,
        )

    def bootstrap_static(self) -> dict[str, Any]:
        payload = self._get("bootstrap-static/")
        if not isinstance(payload, dict):
            raise FPLApiError("FPL bootstrap endpoint returned an unexpected payload.")
        return payload

    def fixtures(self) -> list[dict[str, Any]]:
        payload = self._get("fixtures/")
        if not isinstance(payload, list):
            raise FPLApiError("FPL fixtures endpoint returned an unexpected payload.")
        return [row for row in payload if isinstance(row, dict)]

    def event_live(self, gameweek: int) -> dict[str, Any]:
        payload = self._get(f"event/{int(gameweek)}/live/")
        if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
            raise FPLApiError("FPL event-live endpoint returned an unexpected payload.")
        return payload

    def entry(self, entry_id: str) -> dict[str, Any]:
        payload = self._get(f"entry/{entry_id}/")
        if not isinstance(payload, dict):
            raise FPLApiError("FPL entry endpoint returned an unexpected payload.")
        return payload

    def entry_picks(self, entry_id: str, gameweek: int) -> dict[str, Any]:
        payload = self._get(f"entry/{entry_id}/event/{int(gameweek)}/picks/")
        if not isinstance(payload, dict):
            raise FPLApiError("FPL entry picks endpoint returned an unexpected payload.")
        return payload

    def entry_history(self, entry_id: str) -> dict[str, Any]:
        payload = self._get(f"entry/{entry_id}/history/")
        if not isinstance(payload, dict):
            raise FPLApiError("FPL entry history endpoint returned an unexpected payload.")
        return payload

    def entry_transfers(self, entry_id: str) -> list[dict[str, Any]]:
        payload = self._get(f"entry/{entry_id}/transfers/")
        if not isinstance(payload, list):
            raise FPLApiError("FPL entry transfers endpoint returned an unexpected payload.")
        return [row for row in payload if isinstance(row, dict)]
