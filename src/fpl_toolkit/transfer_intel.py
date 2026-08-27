from __future__ import annotations

from datetime import datetime, timezone
from importlib.resources import files
import json
import os
from pathlib import Path
from typing import Any


TRANSFER_INTEL_MODEL = "v1.0"
VALID_STATUSES = {"talks", "deal_agreed", "confirmed"}
VALID_MOVE_KINDS = {"exit_league", "within_league", "arrival"}
VALID_SOURCE_TIERS = {"official_club", "reliable_report", "rumour"}
VALID_ROLE_OUTLOOKS = {"projected_starter", "strong_rotation", "uncertain"}
ACTION_RANK = {
    "EXIT CONFIRMED": 7,
    "EXIT AGREED": 6,
    "EARLY PICKUP": 5,
    "MOVE CONFIRMED": 4,
    "MOVE WATCH": 3,
    "RUMOUR WATCH": 2,
    "ARRIVAL WATCH": 1,
}


class TransferIntelError(ValueError):
    pass


def transfer_blocks_selection(player: dict[str, Any]) -> bool:
    """Return whether reliable transfer evidence makes a player unusable."""
    return bool((player.get("transfer_intel") or {}).get("blocks_selection"))


def transfer_blocks_acquisition(player: dict[str, Any]) -> bool:
    """Return whether reliable transfer evidence removes a player from claims."""
    return bool((player.get("transfer_intel") or {}).get("blocks_acquisition"))


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise TransferIntelError(f"Transfer intel {field} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise TransferIntelError(f"Transfer intel {field} must include a timezone.")
    return parsed.astimezone(timezone.utc)


def _fixture_window_score(gameweeks: list[dict[str, Any]]) -> float:
    weights = [1.0, 0.82, 0.67, 0.55]
    total = weight_total = 0.0
    for index, gameweek in enumerate(gameweeks[:4]):
        matches = [row for row in (gameweek.get("matches") or []) if isinstance(row, dict)]
        values = []
        for match in matches:
            difficulty = max(1, min(5, int(_number(match.get("difficulty"), 3.0))))
            values.append(float((6 - difficulty) * 20))
        gameweek_score = sum(values) / len(values) if values else 0.0
        if len(values) > 1:
            gameweek_score = min(100.0, gameweek_score + 12.0 * (len(values) - 1))
        weight = weights[min(index, len(weights) - 1)]
        total += gameweek_score * weight
        weight_total += weight
    return max(0.0, min(100.0, total / weight_total if weight_total else 0.0))


def _validate_record(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TransferIntelError(f"Transfer intel record {index} must be an object.")
    record = dict(raw)
    required = {
        "id", "player", "player_ids", "status", "move_kind", "source_tier",
        "reported_at", "expires_at", "destination", "role_outlook", "summary", "sources",
    }
    missing = sorted(required - set(record))
    unexpected = sorted(set(record) - required)
    if missing or unexpected:
        raise TransferIntelError(
            f"Transfer intel record {index} fields invalid; missing={missing}, unexpected={unexpected}."
        )
    if record["status"] not in VALID_STATUSES:
        raise TransferIntelError(f"Transfer intel record {record['id']} has an invalid status.")
    if record["move_kind"] not in VALID_MOVE_KINDS:
        raise TransferIntelError(f"Transfer intel record {record['id']} has an invalid move_kind.")
    if record["source_tier"] not in VALID_SOURCE_TIERS:
        raise TransferIntelError(f"Transfer intel record {record['id']} has an invalid source_tier.")
    if record["role_outlook"] not in VALID_ROLE_OUTLOOKS:
        raise TransferIntelError(f"Transfer intel record {record['id']} has an invalid role_outlook.")
    if not isinstance(record["player_ids"], list) or not record["player_ids"]:
        raise TransferIntelError(f"Transfer intel record {record['id']} requires player_ids.")
    record["player_ids"] = [int(value) for value in record["player_ids"]]
    destination = record["destination"]
    if not isinstance(destination, dict) or set(destination) != {"club", "league", "team_id"}:
        raise TransferIntelError(f"Transfer intel record {record['id']} has an invalid destination.")
    if destination["team_id"] is not None:
        destination["team_id"] = int(destination["team_id"])
    if not isinstance(record["sources"], list) or not record["sources"]:
        raise TransferIntelError(f"Transfer intel record {record['id']} requires at least one source.")
    for source in record["sources"]:
        if not isinstance(source, dict) or set(source) != {"label", "url"}:
            raise TransferIntelError(f"Transfer intel record {record['id']} has an invalid source.")
        if not str(source["url"]).startswith("https://"):
            raise TransferIntelError(f"Transfer intel record {record['id']} source must use HTTPS.")
    reported_at = _parse_datetime(record["reported_at"], "reported_at")
    expires_at = _parse_datetime(record["expires_at"], "expires_at")
    if expires_at <= reported_at:
        raise TransferIntelError(f"Transfer intel record {record['id']} must expire after it was reported.")
    return record


def load_transfer_intel(path: str | Path | None = None) -> list[dict[str, Any]]:
    configured = str(path or os.getenv("FPL_TRANSFER_INTEL_PATH", "")).strip()
    if configured:
        payload = json.loads(Path(configured).read_text(encoding="utf-8"))
    else:
        resource = files("fpl_toolkit").joinpath("data/transfer-intel.json")
        payload = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {"model", "records"}:
        raise TransferIntelError("Transfer intel payload must contain exactly model and records.")
    if payload["model"] != TRANSFER_INTEL_MODEL or not isinstance(payload["records"], list):
        raise TransferIntelError("Transfer intel payload has an unsupported model or records value.")
    return [_validate_record(record, index) for index, record in enumerate(payload["records"])]


def _record_for_player(player: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any] | None:
    player_id = player.get("player_id")
    name = str(player.get("player") or "").casefold()
    for record in records:
        record_name = str(record["player"]).casefold()
        if player_id is not None and int(player_id) in record["player_ids"] and name == record_name:
            return record
        if name and name == record_name:
            return record
    return None


def _action(record: dict[str, Any], destination_score: float | None, fixture_delta: float | None) -> str:
    if record["move_kind"] == "exit_league":
        return "EXIT CONFIRMED" if record["status"] == "confirmed" else "EXIT AGREED"
    if record["move_kind"] == "arrival":
        return "ARRIVAL WATCH"
    if record["status"] == "talks":
        return "RUMOUR WATCH"
    if (
        destination_score is not None
        and destination_score >= 65.0
        and _number(fixture_delta) >= 5.0
        and record["role_outlook"] in {"projected_starter", "strong_rotation"}
    ):
        return "EARLY PICKUP"
    if record["status"] == "confirmed":
        return "MOVE CONFIRMED"
    return "MOVE WATCH"


def attach_transfer_intel(
    players: list[dict[str, Any]],
    fixture_matrix: dict[str, list[dict[str, Any]]],
    *,
    records: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    records = records if records is not None else load_transfer_intel()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    output = []
    for player in players:
        row = dict(player)
        record = _record_for_player(row, records)
        if record is None:
            output.append(row)
            continue
        reported_at = _parse_datetime(record["reported_at"], "reported_at")
        expires_at = _parse_datetime(record["expires_at"], "expires_at")
        if now < reported_at or now > expires_at:
            output.append(row)
            continue

        destination = dict(record["destination"])
        destination_team_id = destination.get("team_id")
        destination_fixtures = (
            fixture_matrix.get(str(destination_team_id), [])
            if destination_team_id is not None
            else []
        )
        current_score = _fixture_window_score(list(row.get("fixtures") or []))
        destination_score = (
            _fixture_window_score(destination_fixtures)
            if destination_team_id is not None
            else None
        )
        fixture_delta = (
            destination_score - current_score
            if destination_score is not None
            else None
        )
        feed_synced = (
            destination_team_id is not None
            and str(row.get("team_id")) == str(destination_team_id)
        )
        blocks_acquisition = (
            record["move_kind"] == "exit_league"
            and record["status"] in {"deal_agreed", "confirmed"}
            and record["source_tier"] in {"official_club", "reliable_report"}
        )
        # A reliable exit from the Premier League is a hard availability event.
        # An intra-league agreement remains advisory until the destination club
        # confirms it; the official FPL feed still owns current-match availability.
        blocks_selection = blocks_acquisition
        action = _action(record, destination_score, fixture_delta)
        row["transfer_intel"] = {
            "model": TRANSFER_INTEL_MODEL,
            "record_id": record["id"],
            "status": record["status"],
            "move_kind": record["move_kind"],
            "source_tier": record["source_tier"],
            "reported_at": record["reported_at"],
            "expires_at": record["expires_at"],
            "destination": destination,
            "destination_fixture_score": None if destination_score is None else round(destination_score, 1),
            "current_fixture_score": round(current_score, 1),
            "fixture_delta": None if fixture_delta is None else round(fixture_delta, 1),
            "role_outlook": record["role_outlook"],
            "feed_synced": feed_synced,
            "blocks_selection": blocks_selection,
            "blocks_acquisition": blocks_acquisition,
            "action": action,
            "summary": record["summary"],
            "sources": [dict(source) for source in record["sources"]],
        }
        if (
            record["move_kind"] == "within_league"
            and record["status"] == "confirmed"
            and destination_fixtures
            and not feed_synced
        ):
            row["fixtures"] = destination_fixtures
        output.append(row)
    return output


def transfer_action_rank(player: dict[str, Any]) -> int:
    action = str((player.get("transfer_intel") or {}).get("action") or "")
    return ACTION_RANK.get(action, 0)
