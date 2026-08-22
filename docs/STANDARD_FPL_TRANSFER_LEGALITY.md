# Standard FPL Squad and Single-Transfer Legality

Last reviewed: 22 August 2026

## Implemented boundary

The toolkit now contains a season-versioned 2026/27 Standard FPL ruleset, a read-only evaluator for one proposed transfer and an isolated candidate-ranking layer. The rules layer answers **whether a move is legal, affordable and subject to an incremental points deduction**. The ranking layer considers only moves that pass those rules and compares their football heuristics; it does not turn those heuristics into projected FPL points.

The implementations are in `src/fpl_toolkit/standard_fpl_rules.py` and `src/fpl_toolkit/standard_fpl_transfers.py`. Both remain outside the Draft/H2H engines, and the legality check remains separate from player scoring so a high model score can never bypass an FPL rule.

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

## Single-transfer candidate ranking

When an exact private snapshot is available, `rank_single_transfers` evaluates every unowned same-position replacement and retains only legal moves. The private Standard FPL report exposes up to ten candidates under `single_transfer_candidates`.

The ranking score is a weighted delta between the incoming and outgoing player:

| Component | Weight |
|---|---:|
| Shared roster heuristic | 30% |
| Next-Gameweek Start Score | 25% |
| Future fixture score | 20% |
| Floor score | 15% |
| Upside score | 10% |

The score is a comparison of normalized model signals, not an estimate of FPL points. Candidate confidence is the lower sample confidence of the two players: `HIGH` at 70 or above, `MEDIUM` from 40 to 69.9 and `LOW` below 40.

Action labels are deliberately conservative:

- `CONSIDER` requires a score improvement of at least 5.0, at least medium confidence and no incremental points deduction;
- `LOW PRIORITY` covers smaller improvements, declines and low-evidence candidates; and
- `HIT REVIEW` is mandatory whenever the move incurs a points deduction, regardless of its heuristic rank.

The four-point deduction is reported alongside the candidate but is never subtracted from the heuristic score. These are unlike units, and presenting their subtraction as a net points forecast would be misleading. Wildcard and Free Hit state continues to follow the legality evaluator.

Without exact current selling prices, bank, free-transfer balance and chip state, the report returns an explicit unavailable object and no candidates. Public locked picks therefore cannot produce apparently legal current transfer advice.

## Deliberate non-goals

This slice does not:

- estimate whether a heuristic improvement repays a points deduction;
- optimize two or more coordinated transfers;
- model the temporary squad reversion after a Free Hit;
- recommend when to activate a chip; or
- submit, stage or confirm an FPL transfer.

Every ranking result preserves `advisory_only: true`. The next analytical layer should add hold explanations and decision-outcome evaluation before attempting coordinated multi-transfer optimization.
