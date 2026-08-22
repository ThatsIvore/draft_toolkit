# Standard FPL Squad and Single-Transfer Legality

Last reviewed: 22 August 2026

## Implemented boundary

The toolkit now contains a season-versioned 2026/27 Standard FPL ruleset and a read-only evaluator for one proposed transfer. This layer answers **whether a move is legal, affordable and subject to an incremental points deduction**. It does not decide whether the move is strategically good.

The implementation is in `src/fpl_toolkit/standard_fpl_rules.py`. It remains separate from player projections so a high model score can never bypass an FPL rule.

## Verified 2026/27 rules

| Rule | Encoded value |
|---|---|
| Initial squad budget | £100.0m |
| Squad | 15 players |
| Position quotas | 2 goalkeepers, 5 defenders, 5 midfielders, 3 forwards |
| Club quota | Maximum 3 players from one club |
| Single transfer | Incoming and outgoing players must have the same position |
| Free-transfer allowance | One per Gameweek; unused transfers may roll to a maximum of 5 |
| Additional transfer | 4-point deduction |
| Wildcard or Free Hit | Transfers are free while the chip is active and banked transfers are preserved |

Primary references: [official squad-selection guide](https://www.premierleague.com/en/news/2174419/fpl-basics-how-to-pick-a-squad), [official transfer guide](https://www.premierleague.com/en/news/2174907), [official 2026/27 changes](https://www.premierleague.com/en/news/4679873), [official chip rules](https://www.premierleague.com/en/news/2174900) and [official 2026/27 chip guide](https://www.premierleague.com/en/news/4362085).

The collector records the rules season in every private Standard FPL report. If the official bootstrap dates indicate a later season than the newest verified ruleset, collection fails instead of silently applying old rules.

## Current-squad validation

`validate_squad_legality` checks:

- exactly 15 unique player IDs;
- the exact 2/5/5/3 position shape;
- a valid current club for every player; and
- no more than three players from one club.

The result is included in the private Standard FPL report as `squad_legality`, alongside the compact `rules` summary. It returns machine-readable issue codes rather than changing or repairing the squad automatically.

## Single-transfer evaluation

`evaluate_single_transfer` checks one specified outgoing and incoming player against:

1. current ownership;
2. same-position replacement;
3. the outgoing player's **selling price**, not current market price;
4. the incoming player's current price and cash in the bank;
5. the three-per-club limit after the move;
6. the complete resulting 15-player squad shape; and
7. free-transfer allowance, transfers already made and an active Wildcard or Free Hit.

Money is calculated in integer tenths of a million. The output reports bank before and after, both relevant prices, whether a free transfer is consumed, free transfers remaining after the move and the incremental points deduction.

The hit calculation is incremental. For example:

| Allowance | Already made | Proposed move | Incremental cost |
|---:|---:|---|---:|
| 2 | 0 | First transfer | 0 points |
| 2 | 1 | Second transfer | 0 points |
| 2 | 2 | Third transfer | 4 points |
| 1 | 2 | Third transfer | 4 additional points; previous deductions are not charged again |
| Any valid allowance | Any | Wildcard/Free Hit active | 0 points; banked transfers are preserved |

In the private snapshot contract, `free_transfers` means the total free-transfer allowance for the decision Gameweek and `transfers_made` means transfers already confirmed in that Gameweek. The remaining allowance is derived from both values.

## Deliberate non-goals

This slice does not:

- rank transfer candidates;
- estimate whether projected gains repay a points deduction;
- optimize two or more coordinated transfers;
- model the temporary squad reversion after a Free Hit;
- recommend when to activate a chip; or
- submit, stage or confirm an FPL transfer.

The next analytical layer may combine this legality result with shared player and fixture scores. It must report gross projected improvement separately from the four-point deduction and preserve `advisory_only: true`.
