from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from .storage import read_json


SCHEMA_VERSION = "standard-fpl-private-snapshot-v1"
CHIP_STATUSES = {"available", "played", "active", "unavailable"}
_CHIP_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")


class StandardFplSnapshotError(RuntimeError):
    pass


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StandardFplSnapshotError(f"{label} must be an object.")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing:
        raise StandardFplSnapshotError(f"{label} is missing fields: {', '.join(missing)}.")
    if extra:
        raise StandardFplSnapshotError(f"{label} contains unsupported fields: {', '.join(extra)}.")


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StandardFplSnapshotError(f"{label} must be an integer.")
    if not minimum <= value <= maximum:
        raise StandardFplSnapshotError(f"{label} must be between {minimum} and {maximum}.")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise StandardFplSnapshotError(f"{label} must be true or false.")
    return value


def _captured_at(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StandardFplSnapshotError("captured_at must be an ISO-8601 timestamp.")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise StandardFplSnapshotError("captured_at must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StandardFplSnapshotError("captured_at must include a timezone.")
    return value.strip()


def _normalize_pick(value: Any, index: int) -> dict[str, Any]:
    pick = _mapping(value, f"squad[{index}]")
    _exact_keys(
        pick,
        {
            "player_id",
            "lineup_position",
            "multiplier",
            "is_captain",
            "is_vice_captain",
            "purchase_price_tenths",
            "selling_price_tenths",
        },
        f"squad[{index}]",
    )
    multiplier = _integer(pick["multiplier"], f"squad[{index}].multiplier", 0, 3)
    lineup_position = _integer(
        pick["lineup_position"], f"squad[{index}].lineup_position", 1, 15
    )
    captain = _boolean(pick["is_captain"], f"squad[{index}].is_captain")
    vice = _boolean(pick["is_vice_captain"], f"squad[{index}].is_vice_captain")
    if captain and vice:
        raise StandardFplSnapshotError(f"squad[{index}] cannot be both captain and vice-captain.")
    if captain and multiplier not in {2, 3}:
        raise StandardFplSnapshotError(f"squad[{index}] captain must have multiplier 2 or 3.")
    if (captain or vice) and lineup_position > 11:
        raise StandardFplSnapshotError(f"squad[{index}] captain and vice-captain must be starters.")
    return {
        "player_id": _integer(pick["player_id"], f"squad[{index}].player_id", 1, 1_000_000),
        "lineup_position": lineup_position,
        "multiplier": multiplier,
        "is_captain": captain,
        "is_vice_captain": vice,
        "purchase_price_tenths": _integer(
            pick["purchase_price_tenths"], f"squad[{index}].purchase_price_tenths", 1, 500
        ),
        "selling_price_tenths": _integer(
            pick["selling_price_tenths"], f"squad[{index}].selling_price_tenths", 1, 500
        ),
    }


def _normalize_transfers(value: Any) -> dict[str, int]:
    transfers = _mapping(value, "transfers")
    _exact_keys(
        transfers,
        {"bank_tenths", "squad_value_tenths", "free_transfers", "transfers_made"},
        "transfers",
    )
    return {
        "bank_tenths": _integer(transfers["bank_tenths"], "transfers.bank_tenths", 0, 2_000),
        "squad_value_tenths": _integer(
            transfers["squad_value_tenths"], "transfers.squad_value_tenths", 1, 2_000
        ),
        "free_transfers": _integer(transfers["free_transfers"], "transfers.free_transfers", 0, 5),
        "transfers_made": _integer(transfers["transfers_made"], "transfers.transfers_made", 0, 100),
    }


def _normalize_chip(value: Any, index: int) -> dict[str, Any]:
    chip = _mapping(value, f"chips[{index}]")
    _exact_keys(chip, {"name", "number", "status", "played_gameweek"}, f"chips[{index}]")
    name = chip["name"]
    if not isinstance(name, str) or not _CHIP_NAME.fullmatch(name):
        raise StandardFplSnapshotError(f"chips[{index}].name is invalid.")
    status = chip["status"]
    if status not in CHIP_STATUSES:
        raise StandardFplSnapshotError(
            f"chips[{index}].status must be one of: {', '.join(sorted(CHIP_STATUSES))}."
        )
    played_gameweek = chip["played_gameweek"]
    if status == "played":
        played_gameweek = _integer(played_gameweek, f"chips[{index}].played_gameweek", 1, 38)
    elif played_gameweek is not None:
        raise StandardFplSnapshotError(
            f"chips[{index}].played_gameweek must be null unless the chip is played."
        )
    return {
        "name": name,
        "number": _integer(chip["number"], f"chips[{index}].number", 1, 10),
        "status": status,
        "played_gameweek": played_gameweek,
    }


def validate_private_snapshot(
    payload: Any,
    known_player_ids: set[int] | None = None,
) -> dict[str, Any]:
    """Validate and return the strict, identifier-free Standard FPL snapshot contract."""
    snapshot = _mapping(payload, "snapshot")
    _exact_keys(
        snapshot,
        {"schema_version", "captured_at", "decision_gameweek", "squad", "transfers", "chips"},
        "snapshot",
    )
    if snapshot["schema_version"] != SCHEMA_VERSION:
        raise StandardFplSnapshotError(f"schema_version must be {SCHEMA_VERSION}.")
    squad_raw = snapshot["squad"]
    if not isinstance(squad_raw, list):
        raise StandardFplSnapshotError("squad must be a list.")
    if len(squad_raw) != 15:
        raise StandardFplSnapshotError(f"squad must contain 15 picks, received {len(squad_raw)}.")
    squad = [_normalize_pick(row, index) for index, row in enumerate(squad_raw)]
    player_ids = [row["player_id"] for row in squad]
    if len(set(player_ids)) != 15:
        raise StandardFplSnapshotError("squad player_id values must be unique.")
    positions = [row["lineup_position"] for row in squad]
    if set(positions) != set(range(1, 16)):
        raise StandardFplSnapshotError("squad lineup_position values must contain every position from 1 to 15.")
    if known_player_ids is not None:
        unknown = sorted(set(player_ids) - known_player_ids)
        if unknown:
            raise StandardFplSnapshotError(f"squad contains unknown player IDs: {unknown}.")
    captains = [row for row in squad if row["is_captain"]]
    vice_captains = [row for row in squad if row["is_vice_captain"]]
    if len(captains) != 1 or len(vice_captains) != 1:
        raise StandardFplSnapshotError("squad must contain exactly one captain and one vice-captain.")

    chips_raw = snapshot["chips"]
    if not isinstance(chips_raw, list):
        raise StandardFplSnapshotError("chips must be a list.")
    if not chips_raw:
        raise StandardFplSnapshotError("chips must contain the current chip state.")
    chips = [_normalize_chip(row, index) for index, row in enumerate(chips_raw)]
    chip_keys = [(row["name"], row["number"]) for row in chips]
    if len(chip_keys) != len(set(chip_keys)):
        raise StandardFplSnapshotError("chips must not repeat the same name and number.")
    if sum(1 for row in chips if row["status"] == "active") > 1:
        raise StandardFplSnapshotError("only one chip can be active.")

    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at": _captured_at(snapshot["captured_at"]),
        "decision_gameweek": _integer(snapshot["decision_gameweek"], "decision_gameweek", 1, 38),
        "squad": sorted(squad, key=lambda row: row["lineup_position"]),
        "transfers": _normalize_transfers(snapshot["transfers"]),
        "chips": chips,
    }


def load_private_snapshot(
    path: str | Path,
    known_player_ids: set[int] | None = None,
) -> dict[str, Any]:
    try:
        payload = read_json(Path(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise StandardFplSnapshotError(f"Could not read private snapshot {path}: {exc}") from exc
    return validate_private_snapshot(payload, known_player_ids=known_player_ids)


def snapshot_to_picks_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    active_chip = next(
        (row["name"] for row in snapshot["chips"] if row["status"] == "active"),
        None,
    )
    return {
        "active_chip": active_chip,
        "automatic_subs": [],
        "entry_history": {},
        "picks": [
            {
                "element": row["player_id"],
                "position": row["lineup_position"],
                "multiplier": row["multiplier"],
                "is_captain": row["is_captain"],
                "is_vice_captain": row["is_vice_captain"],
                "purchase_price": row["purchase_price_tenths"],
                "selling_price": row["selling_price_tenths"],
            }
            for row in snapshot["squad"]
        ],
    }
