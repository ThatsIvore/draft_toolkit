# Standard FPL Four-Gameweek Squad Outlook

Last reviewed: 23 August 2026

## Purpose

The private Standard FPL report now turns the shared lineup and captaincy primitives into a compact outlook for every actionable Gameweek in the configured planning horizon. This gives the manager a forward view of the existing squad before escalating from a single-transfer decision to coordinated multi-transfer optimization.

The implementation is isolated in `src/fpl_toolkit/standard_fpl_lineup.py`. It is not imported by the Draft collector, H2H, waivers, Planner, Draft outcomes, Decision Updates or public privacy modules.

## Per-Gameweek output

For each planning Gameweek, `squad_outlook.rounds` contains:

- a legal formation and eleven recommended starters;
- the three ordered outfield substitutes and separate reserve goalkeeper;
- the recommended captain, vice-captain and five-player captaincy shortlist;
- total and average Start Score, explicitly as heuristics rather than projected FPL points;
- close same-position lineup calls from the shared optimizer;
- starters whose availability is below 75 or expected minutes are below 60;
- the count of playable outfield substitutes; and
- a `LOW`, `MEDIUM` or `HIGH` selection-pressure label.

Selection pressure is deliberately simple and transparent:

| Label | Meaning |
|---|---|
| `LOW` | The legal XI contains no flagged availability or minutes risk |
| `MEDIUM` | At least one recommended starter is flagged, but the high-pressure condition is not met |
| `HIGH` | No legal XI exists, or at least two starters are flagged and no playable outfield substitute meets both thresholds |

These thresholds organize review; they are not medical certainty or predicted appearance points.

## Horizon summary

The outlook also groups players by planned use:

- `core_starters` start every Gameweek in the horizon;
- `rotation_players` start at least once but not in every round; and
- `always_benched` do not enter a recommended XI during the horizon.

This grouping helps distinguish a temporary lineup decision from a persistent squad-structure concern. It does not itself recommend a transfer: legal acquisition, selling value, free-transfer use and point-hit review remain in the separate Standard FPL transfer layer.

## Privacy and advisory boundary

The compact outlook contains player and club labels needed for the private decision report, but strips internal owner fields and does not store the configured entry identifier. It remains under the gitignored private report path, cannot use `--publish`, and submits no lineup, captaincy, chip or transfer action.

The current public Draft dashboard is unchanged. A future shared mode selector still requires secure private Standard FPL report delivery before this outlook can be exposed through a hosted interface.
