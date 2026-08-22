# Standard FPL Private Snapshot Contract

Last reviewed: 22 August 2026

## Purpose

`standard-fpl-private-snapshot-v1` is the toolkit's source-independent contract for an exact, current Standard FPL team. It lets the analysis pipeline, privacy checks and later transfer models be built without coupling them to browser authentication or an undocumented raw API response.

The contract is implemented in `src/fpl_toolkit/standard_fpl_snapshot.py`. A future approved connector or bounded browser-local exporter must map into this contract; the rest of the toolkit must not receive an OAuth token, cookie, password, account profile or raw authenticated response.

## Private file boundary

Snapshot files must remain under the gitignored `data/private/` directory. Configure one with:

```bash
export FPL_STANDARD_ENTRY_URL='https://fantasy.premierleague.com/en/entry/123456/event/1'
export FPL_STANDARD_PRIVATE_SNAPSHOT='data/private/current-team.json'
fpl-toolkit --mode standard-fpl
```

The ordinary entry URL still identifies which public entry and player data to analyse. It is not treated as authentication. The snapshot itself deliberately contains no entry or account identifier.

The experimental [browser-local personal exporter](STANDARD_FPL_SNAPSHOT_HELPER.md) is now implemented. It assembles the complete allowlist from normal Pick Team and Transfers views plus the unauthenticated public player bootstrap, without reading a bearer token, credential or existing browser-storage value. The public locked-squad mode remains the lower-friction fallback when the official UI changes or a private current-state capture is not needed.

## Version 1 fields

| Area | Required fields | Rules |
|---|---|---|
| Snapshot | `schema_version`, `captured_at`, `decision_gameweek` | Exact version string; timezone-aware capture time; Gameweek 1–38 |
| Squad | 15 rows containing `player_id`, `lineup_position`, `multiplier`, captain flags and purchase/selling prices in tenths | Unique current-season players; every lineup position 1–15; exactly one captain and vice-captain |
| Transfers | `bank_tenths`, `squad_value_tenths`, `free_transfers`, `transfers_made` | Integer source units preserve exact FPL money; `free_transfers` is the Gameweek allowance and `transfers_made` is the number already confirmed; the allowance is constrained to 0–5 |
| Chips | `name`, `number`, `status`, `played_gameweek` | Status is `available`, `played`, `active` or `unavailable`; at most one active chip |

An abbreviated example shows the field shape; a valid file must contain all 15 squad rows:

```json
{
  "schema_version": "standard-fpl-private-snapshot-v1",
  "captured_at": "2026-08-22T20:00:00+00:00",
  "decision_gameweek": 2,
  "squad": [
    {
      "player_id": 101,
      "lineup_position": 1,
      "multiplier": 1,
      "is_captain": false,
      "is_vice_captain": false,
      "purchase_price_tenths": 45,
      "selling_price_tenths": 45
    }
  ],
  "transfers": {
    "bank_tenths": 7,
    "squad_value_tenths": 1007,
    "free_transfers": 2,
    "transfers_made": 0
  },
  "chips": [
    {
      "name": "wildcard",
      "number": 1,
      "status": "available",
      "played_gameweek": null
    }
  ]
}
```

## Validation and report behavior

The loader fails closed. It rejects:

- unknown or additional fields, including accidental identity or credential fields;
- a schema version it does not understand;
- a timestamp without a timezone;
- anything other than 15 unique current-season players;
- duplicate or missing lineup positions;
- missing or conflicting captaincy;
- invalid money, transfer or chip values; and
- a snapshot whose Gameweek is not the toolkit's next actionable Gameweek.

After validation, the private Standard FPL report:

- uses the snapshot squad for Recommended XI, bench order and captaincy;
- labels the source `private_current_team_snapshot`;
- exposes normalized purchase/selling prices and the current financial/chip state only in the gitignored report;
- retains the snapshot capture time and schema version for freshness and debugging; and
- still refuses `--publish` and never submits an FPL action.

The connector remains a separate trust boundary. A valid contract does not make credential extraction acceptable and does not resolve the Premier League permission gate documented in [Standard FPL Current-Team Authentication Discovery](STANDARD_FPL_AUTH_DISCOVERY.md).

The approved personal-helper direction is DOM-only and fail-closed: capture lineup/captaincy/prices from Pick Team, capture bank/free-transfer/finance state from Transfers, resolve player IDs against public bootstrap data, remove names and club labels from the final payload, validate locally and download only this schema. Temporary browser state may contain only the helper's own sanitized partial capture and must be removed after success or failure.

The implemented [Standard FPL squad and single-transfer legality layer](STANDARD_FPL_TRANSFER_LEGALITY.md) consumes this financial state. It derives remaining free transfers and incremental hit cost rather than treating `free_transfers` and `transfers_made` as interchangeable values.
