from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import time
from typing import Any
import unicodedata

import requests


API_FOOTBALL_LEAGUE_ID = 39
RECENCY_WEIGHTS = (1.0, 0.75, 0.55, 0.4)
POSITION_BY_ELEMENT_TYPE = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
PROCESS_WEIGHTS = {
    "DEF": {"shots": 0.25, "shots_on": 0.20, "key_passes": 0.35, "dribbles": 0.20},
    "MID": {"shots": 0.25, "shots_on": 0.25, "key_passes": 0.35, "dribbles": 0.15},
    "FWD": {"shots": 0.35, "shots_on": 0.35, "key_passes": 0.20, "dribbles": 0.10},
}


class ExternalStatsError(RuntimeError):
    pass


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ascii(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return text.encode("ascii", "ignore").decode("ascii")


def _normalized(value: Any) -> str:
    text = _ascii(value).lower().replace("&", " and ")
    return " ".join("".join(char if char.isalnum() else " " for char in text).split())


_TEAM_ALIASES = {
    "afc bournemouth": "bournemouth",
    "brighton and hove albion": "brighton",
    "brighton hove albion": "brighton",
    "coventry city": "coventry",
    "hull city": "hull",
    "ipswich town": "ipswich",
    "leeds united": "leeds",
    "manchester city": "man city",
    "manchester united": "man utd",
    "newcastle united": "newcastle",
    "nott m forest": "nottm forest",
    "nottingham forest": "nottm forest",
    "sunderland afc": "sunderland",
    "tottenham": "spurs",
    "tottenham hotspur": "spurs",
    "west ham united": "west ham",
    "wolverhampton wanderers": "wolves",
}


def canonical_team_name(value: Any) -> str:
    name = _normalized(value)
    for suffix in (" football club", " fc", " afc"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return _TEAM_ALIASES.get(name, name)


def _name_variants(element: dict[str, Any]) -> set[str]:
    first = _normalized(element.get("first_name"))
    second = _normalized(element.get("second_name"))
    web = _normalized(element.get("web_name"))
    variants = {value for value in (web, second) if value}
    if first and second:
        variants.add(f"{first} {second}")
        variants.add(f"{first[0]} {second}")
    return variants


def map_api_football_player_code(
    provider_player: dict[str, Any],
    provider_team_name: str,
    fpl_bootstrap: dict[str, Any],
    overrides: dict[int, int] | None = None,
) -> tuple[int | None, str]:
    """Map one API-Football player to an official FPL stable code, failing closed."""
    provider_id = provider_player.get("id")
    try:
        provider_id_int = int(provider_id)
    except (TypeError, ValueError):
        provider_id_int = None
    if provider_id_int is not None and overrides and provider_id_int in overrides:
        override_code = int(overrides[provider_id_int])
        known_codes = {
            int(row["code"])
            for row in fpl_bootstrap.get("elements") or []
            if isinstance(row, dict) and row.get("code") is not None
        }
        if override_code in known_codes:
            return override_code, "override"
        return None, "invalid_override"

    team_by_id = {
        int(team["id"]): canonical_team_name(team.get("name") or team.get("short_name"))
        for team in fpl_bootstrap.get("teams") or []
        if isinstance(team, dict) and team.get("id") is not None
    }
    provider_team = canonical_team_name(provider_team_name)
    provider_name = _normalized(provider_player.get("name"))
    if not provider_team or not provider_name:
        return None, "unmatched"

    candidates: list[int] = []
    for element in fpl_bootstrap.get("elements") or []:
        if not isinstance(element, dict) or element.get("code") is None or element.get("team") is None:
            continue
        try:
            team_id = int(element["team"])
        except (TypeError, ValueError):
            continue
        if team_by_id.get(team_id) != provider_team:
            continue
        if provider_name in _name_variants(element):
            candidates.append(int(element["code"]))
    unique = sorted(set(candidates))
    if len(unique) == 1:
        return unique[0], "matched"
    if len(unique) > 1:
        return None, "ambiguous"
    return None, "unmatched"


@dataclass
class ApiFootballClient:
    api_key: str
    base_url: str = "https://v3.football.api-sports.io"
    timeout_seconds: int = 25
    user_agent: str = "fpl-season-toolkit/0.1"
    max_attempts: int = 3
    retry_backoff_seconds: float = 1.0

    def _get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        attempts = max(1, int(self.max_attempts))
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers={
                        "x-apisports-key": self.api_key,
                        "User-Agent": self.user_agent,
                        "Accept": "application/json",
                    },
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ExternalStatsError("API-Football returned an unexpected payload.")
                errors = payload.get("errors")
                if errors:
                    raise ExternalStatsError(f"API-Football returned an API error: {errors}")
                rows = payload.get("response")
                if not isinstance(rows, list):
                    raise ExternalStatsError("API-Football response is missing a response list.")
                return [row for row in rows if isinstance(row, dict)]
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                retryable = True
            except requests.HTTPError as exc:
                last_error = exc
                status = exc.response.status_code if exc.response is not None else None
                retryable = status == 429 or bool(status and status >= 500)
            except requests.RequestException as exc:
                raise ExternalStatsError(f"GET {url} failed: {exc}") from exc
            except ValueError as exc:
                raise ExternalStatsError(f"GET {url} returned invalid JSON: {exc}") from exc
            if not retryable or attempt == attempts - 1:
                raise ExternalStatsError(
                    f"GET {url} failed after {attempt + 1} attempt(s): {last_error}"
                ) from last_error
            time.sleep(max(0.0, self.retry_backoff_seconds) * (2**attempt))
        raise ExternalStatsError(f"GET {url} failed without a response.")

    def fixtures(self, **params: Any) -> list[dict[str, Any]]:
        return self._get("fixtures", params)


def _date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10] if len(text) >= 10 else None


def season_from_bootstrap(bootstrap: dict[str, Any]) -> int | None:
    for event in bootstrap.get("events") or []:
        if not isinstance(event, dict):
            continue
        deadline = str(event.get("deadline_time") or "")
        if len(deadline) >= 4 and deadline[:4].isdigit():
            return int(deadline[:4])
    return None


def _selected_fpl_fixtures(
    fixtures: list[dict[str, Any]],
    completed_gameweeks: list[int],
    bootstrap: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], list[tuple[str | None, int]]]]:
    selected_gws = {int(gameweek) for gameweek in completed_gameweeks}
    team_names = {
        int(team["id"]): canonical_team_name(team.get("name") or team.get("short_name"))
        for team in bootstrap.get("teams") or []
        if isinstance(team, dict) and team.get("id") is not None
    }
    selected = [
        fixture
        for fixture in fixtures
        if isinstance(fixture, dict)
        and fixture.get("event") is not None
        and int(fixture["event"]) in selected_gws
    ]
    by_pair: dict[tuple[str, str], list[tuple[str | None, int]]] = defaultdict(list)
    for fixture in selected:
        try:
            home = team_names[int(fixture["team_h"])]
            away = team_names[int(fixture["team_a"])]
            gameweek = int(fixture["event"])
        except (KeyError, TypeError, ValueError):
            continue
        by_pair[(home, away)].append((_date(fixture.get("kickoff_time")), gameweek))
    return selected, by_pair


def _provider_fixture_gameweek(
    fixture: dict[str, Any],
    fpl_by_pair: dict[tuple[str, str], list[tuple[str | None, int]]],
) -> int | None:
    teams = fixture.get("teams") if isinstance(fixture.get("teams"), dict) else {}
    home = teams.get("home") if isinstance(teams.get("home"), dict) else {}
    away = teams.get("away") if isinstance(teams.get("away"), dict) else {}
    pair = (canonical_team_name(home.get("name")), canonical_team_name(away.get("name")))
    candidates = fpl_by_pair.get(pair, [])
    if not candidates:
        return None
    fixture_data = fixture.get("fixture") if isinstance(fixture.get("fixture"), dict) else {}
    provider_date = _date(fixture_data.get("date"))
    exact = {gameweek for date_value, gameweek in candidates if date_value == provider_date}
    if len(exact) == 1:
        return next(iter(exact))
    gameweeks = {gameweek for _, gameweek in candidates}
    if len(gameweeks) == 1 and len(candidates) == 1:
        return next(iter(gameweeks))
    return None


def _stats_row(statistics: dict[str, Any]) -> dict[str, float]:
    games = statistics.get("games") if isinstance(statistics.get("games"), dict) else {}
    shots = statistics.get("shots") if isinstance(statistics.get("shots"), dict) else {}
    passes = statistics.get("passes") if isinstance(statistics.get("passes"), dict) else {}
    dribbles = statistics.get("dribbles") if isinstance(statistics.get("dribbles"), dict) else {}
    return {
        "minutes": _number(games.get("minutes")),
        "shots": _number(shots.get("total")),
        "shots_on": _number(shots.get("on")),
        "key_passes": _number(passes.get("key")),
        "dribbles": _number(dribbles.get("success")),
    }


def _percentiles(values: dict[int, float]) -> dict[int, float]:
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    if not ordered:
        return {}
    if len(ordered) == 1:
        return {ordered[0][0]: 50.0}
    result: dict[int, float] = {}
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[index][1]:
            end += 1
        average_rank = (index + end) / 2.0
        score = 100.0 * average_rank / (len(ordered) - 1)
        for position in range(index, end + 1):
            result[ordered[position][0]] = score
        index = end + 1
    return result


def _grade(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "E"


def _process_scores(
    rows_by_gameweek: dict[int, dict[int, dict[str, float]]],
    position_by_code: dict[int, str],
) -> dict[int, dict[str, Any]]:
    scores_by_gameweek: dict[int, dict[int, float]] = {}
    for gameweek, rows in rows_by_gameweek.items():
        scores: dict[int, float] = {}
        groups: dict[str, list[int]] = defaultdict(list)
        for code, row in rows.items():
            position = position_by_code.get(code, "UNK")
            if position in PROCESS_WEIGHTS and row.get("minutes", 0) > 0:
                groups[position].append(code)
        for position, codes in groups.items():
            percentiles = {
                metric: _percentiles({code: rows[code][metric] for code in codes})
                for metric in PROCESS_WEIGHTS[position]
            }
            for code in codes:
                scores[code] = sum(
                    weight * percentiles[metric][code]
                    for metric, weight in PROCESS_WEIGHTS[position].items()
                )
        scores_by_gameweek[gameweek] = scores

    ordered_gameweeks = sorted(rows_by_gameweek, reverse=True)[: len(RECENCY_WEIGHTS)]
    result: dict[int, dict[str, Any]] = {}
    all_codes = set(position_by_code)
    for code in all_codes:
        appearances: list[tuple[float, float]] = []
        total_minutes = 0.0
        eligible_gameweeks = 0
        for weight, gameweek in zip(RECENCY_WEIGHTS, ordered_gameweeks):
            row = rows_by_gameweek[gameweek].get(code)
            if row is None:
                continue
            eligible_gameweeks += 1
            total_minutes += row.get("minutes", 0.0)
            score = scores_by_gameweek[gameweek].get(code)
            if score is not None:
                appearances.append((weight, score))
        if not appearances:
            continue
        weighted_score = sum(weight * score for weight, score in appearances) / sum(
            weight for weight, _ in appearances
        )
        appearance_confidence = min(1.0, len(appearances) / 3.0)
        minutes_confidence = min(1.0, total_minutes / 270.0)
        confidence = 100.0 * appearance_confidence * minutes_confidence
        result[code] = {
            "process_score": round(weighted_score, 1),
            "process_grade": _grade(weighted_score),
            "confidence": round(confidence, 1),
            "appearances": len(appearances),
            "minutes": int(round(total_minutes)),
            "completed_gameweeks": eligible_gameweeks,
        }
    return result


def build_api_football_shadow(
    *,
    provider: str | None,
    api_key: str | None,
    bootstrap: dict[str, Any],
    fixtures: list[dict[str, Any]],
    completed_gameweeks: list[int],
    official_scores_by_code: dict[int, float] | None = None,
    client: ApiFootballClient | Any | None = None,
    overrides: dict[int, int] | None = None,
) -> dict[str, Any]:
    """Build derived API-Football process evidence without altering recommendations."""
    base = {
        "version": "v1",
        "provider": provider or None,
        "mode": "shadow",
        "status": "disabled" if not provider else "unavailable",
        "completed_gameweeks": [int(value) for value in completed_gameweeks],
        "mapped_appearances": 0,
        "unmapped_appearances": 0,
        "ambiguous_appearances": 0,
        "players": {},
    }
    if not provider:
        return base
    if provider != "api_football":
        base["status"] = "unsupported_provider"
        return base
    if not api_key:
        base["status"] = "missing_api_key"
        return base
    if not completed_gameweeks:
        base["status"] = "no_completed_gameweeks"
        return base

    season = season_from_bootstrap(bootstrap)
    base["season"] = season
    if season is None:
        base["status"] = "season_unavailable"
        return base
    selected_fixtures, fpl_by_pair = _selected_fpl_fixtures(fixtures, completed_gameweeks, bootstrap)
    dates = sorted(
        date_value
        for date_value in (_date(fixture.get("kickoff_time")) for fixture in selected_fixtures)
        if date_value
    )
    if not dates:
        base["status"] = "fixture_window_unavailable"
        return base

    client = client or ApiFootballClient(api_key=api_key)
    try:
        fixture_rows = client.fixtures(
            **{
                "league": API_FOOTBALL_LEAGUE_ID,
                "season": season,
                "from": dates[0],
                "to": dates[-1],
                "status": "FT-AET-PEN",
            }
        )
    except ExternalStatsError:
        base["status"] = "feed_unavailable"
        return base

    matched_fixture_ids: list[int] = []
    gameweek_by_fixture_id: dict[int, int] = {}
    for fixture in fixture_rows:
        gameweek = _provider_fixture_gameweek(fixture, fpl_by_pair)
        fixture_data = fixture.get("fixture") if isinstance(fixture.get("fixture"), dict) else {}
        fixture_id = fixture_data.get("id")
        if gameweek is None or fixture_id is None:
            continue
        try:
            fixture_id_int = int(fixture_id)
        except (TypeError, ValueError):
            continue
        matched_fixture_ids.append(fixture_id_int)
        gameweek_by_fixture_id[fixture_id_int] = gameweek
    if not matched_fixture_ids:
        base["status"] = "no_matching_fixtures"
        return base

    details: list[dict[str, Any]] = []
    try:
        for start in range(0, len(matched_fixture_ids), 20):
            batch = matched_fixture_ids[start : start + 20]
            details.extend(client.fixtures(ids="-".join(str(value) for value in batch)))
    except ExternalStatsError:
        base["status"] = "feed_unavailable"
        return base

    position_by_code = {
        int(element["code"]): POSITION_BY_ELEMENT_TYPE.get(int(element.get("element_type") or 0), "UNK")
        for element in bootstrap.get("elements") or []
        if isinstance(element, dict) and element.get("code") is not None
    }
    rows_by_gameweek: dict[int, dict[int, dict[str, float]]] = defaultdict(dict)
    for fixture in details:
        fixture_data = fixture.get("fixture") if isinstance(fixture.get("fixture"), dict) else {}
        try:
            fixture_id = int(fixture_data.get("id"))
        except (TypeError, ValueError):
            continue
        gameweek = gameweek_by_fixture_id.get(fixture_id)
        if gameweek is None:
            continue
        team_blocks = fixture.get("players") if isinstance(fixture.get("players"), list) else []
        for team_block in team_blocks:
            if not isinstance(team_block, dict):
                continue
            team = team_block.get("team") if isinstance(team_block.get("team"), dict) else {}
            team_name = str(team.get("name") or "")
            appearances = team_block.get("players") if isinstance(team_block.get("players"), list) else []
            for appearance in appearances:
                if not isinstance(appearance, dict):
                    continue
                provider_player = appearance.get("player") if isinstance(appearance.get("player"), dict) else {}
                code, mapping_status = map_api_football_player_code(
                    provider_player,
                    team_name,
                    bootstrap,
                    overrides=overrides,
                )
                if code is None:
                    if mapping_status == "ambiguous":
                        base["ambiguous_appearances"] += 1
                    else:
                        base["unmapped_appearances"] += 1
                    continue
                statistics_list = appearance.get("statistics") if isinstance(appearance.get("statistics"), list) else []
                statistics = next((row for row in statistics_list if isinstance(row, dict)), {})
                row = _stats_row(statistics)
                if row["minutes"] <= 0:
                    continue
                base["mapped_appearances"] += 1
                current = rows_by_gameweek[gameweek].setdefault(
                    code,
                    {"minutes": 0.0, "shots": 0.0, "shots_on": 0.0, "key_passes": 0.0, "dribbles": 0.0},
                )
                for field, value in row.items():
                    current[field] += value

    process = _process_scores(rows_by_gameweek, position_by_code)
    official_scores_by_code = official_scores_by_code or {}
    players: dict[str, dict[str, Any]] = {}
    for code, evidence in sorted(process.items()):
        row = dict(evidence)
        official_score = official_scores_by_code.get(code)
        if official_score is not None:
            confidence = _number(row.get("confidence"))
            effective_weight = 0.20 * max(0.0, min(1.0, confidence / 100.0))
            combined = (1.0 - effective_weight) * float(official_score) + effective_weight * float(row["process_score"])
            row["official_score"] = round(float(official_score), 1)
            row["combined_score"] = round(combined, 1)
            row["effective_external_weight"] = round(effective_weight, 3)
        players[str(code)] = row
    base["players"] = players
    base["status"] = "available" if players else "no_mapped_players"
    return base


def public_shadow_summary(state: dict[str, Any]) -> dict[str, Any]:
    """Return aggregate public metadata only; never expose provider rows or IDs."""
    keys = (
        "version",
        "provider",
        "mode",
        "status",
        "season",
        "completed_gameweeks",
        "mapped_appearances",
        "unmapped_appearances",
        "ambiguous_appearances",
    )
    summary = {key: state[key] for key in keys if key in state}
    summary["derived_players"] = len(state.get("players") or {})
    summary["recommendations_affected"] = False
    return summary
