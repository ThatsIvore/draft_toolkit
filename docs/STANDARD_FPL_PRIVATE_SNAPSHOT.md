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

The exporter is not implemented yet. Do not obtain the file by copying credentials or raw browser storage. Until the safe same-origin experiment is proved, the existing public locked-squad mode remains the usable input path.

## Version 1 fields

| Area | Required fields | Rules |
|---|---|---|
| Snapshot | `schema_version`, `captured_at`, `decision_gameweek` | Exact version string; timezone-aware capture time; Gameweek 1–38 |
| Squad | 15 rows containing `player_id`, `lineup_position`, `multiplier`, captain flags and purchase/selling prices in tenths | Unique current-season players; every lineup position 1–15; exactly one captain and vice-captain |
| Transfers | `bank_tenths`, `squad_value_tenths`, `free_transfers`, `transfers_made` | Integer source units preserve exact FPL money; free transfers are constrained to the current 0–5 range |
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
