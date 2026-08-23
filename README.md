# FPL Draft Season Toolkit

This project turns public FPL and FPL Draft data into an in-season decision toolkit:

1. fetch the official Draft player pool;
2. fetch league details and ownership/availability;
3. normalize every player's owner and status;
4. persist a minimal, name-free ownership state across GitHub Actions runs;
5. infer opponent adds/drops by diffing state snapshots;
6. attach a four-Gameweek fixture matrix;
7. score roster value, floor, upside, role evidence and return-aligned stash value;
8. compare same-position waiver replacements and recommend a legal starting XI;
9. project and audit H2H matchups across a four-Gameweek window;
10. retain aggregate opponent transfer and completed-lineup decisions;
11. use a verified 90-pick draft history as a small, decaying opponent prior;
12. retain material updates throughout each actionable Gameweek decision cycle and surface decision-relevant injury/stash cases;
13. produce a redacted machine-readable report for a GitHub Pages dashboard.

## Identifier

The live Draft entry ID for this repository is `336654`, from:

`https://draft.premierleague.com/entry/336654/`

If league auto-discovery is unavailable for the current API response, set the repository variable `FPL_DRAFT_LEAGUE_ID` once. No Premier League password or session cookie is stored.

## Local run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
export FPL_DRAFT_ENTRY_ID=336654
# Optional fallback if entry payload does not expose league ID:
export FPL_DRAFT_LEAGUE_ID=12345
fpl-toolkit --publish
```

Open `public/index.html` through a local web server after collection.

## Private Standard FPL Phase 1 POC

The repository also contains an isolated, read-only proof of concept for the budget-and-transfer game at `fantasy.premierleague.com`. It does not alter or publish to the existing Draft dashboard.

Supply an ordinary standard FPL entry URL; developer tools and authentication data are not required for the public locked-squad prototype:

```bash
export FPL_STANDARD_ENTRY_URL='https://fantasy.premierleague.com/en/entry/123456/event/1'
fpl-toolkit --mode standard-fpl
```

The command writes `data/private/standard-fpl-poc.json`, which is gitignored because it contains squad and recommendation state. The configured entry identifier is used only during collection and is omitted from the saved report. The report:

- imports the newest publicly locked 15-player squad;
- reuses the shared player, availability, fixture and role intelligence;
- recommends a legal XI and orders the three outfield substitutes;
- recommends a captain and vice-captain using a transparent heuristic; and
- preserves the scoring-Gameweek versus next-actionable-Gameweek distinction.

Public picks can be stale for the next deadline after the manager makes a transfer. The POC labels that limitation and does not claim to know current purchase/selling prices, banked free transfers or chip availability. It does not submit any FPL action, and `--publish` is deliberately rejected in Standard FPL mode.

The source-independent [private snapshot contract](docs/STANDARD_FPL_PRIVATE_SNAPSHOT.md) is also implemented. When a trusted future connector produces `standard-fpl-private-snapshot-v1`, set `FPL_STANDARD_PRIVATE_SNAPSHOT` to that JSON file under `data/private/`. The toolkit will then validate and use the exact decision-Gameweek squad, purchase/selling prices, bank, free transfers and chip state. The exporter is not yet implemented, and credentials or raw browser storage must not be used to create this file.

The private report now validates the squad against the season-versioned 2026/27 rules. The isolated [single-transfer legality and ranking layer](docs/STANDARD_FPL_TRANSFER_LEGALITY.md) checks same-position replacement, selling-price affordability, club quota, free-transfer use and incremental point-hit cost, then ranks legal candidates with transparent heuristics. Point hits remain a separate `HIT REVIEW` warning, not a fake net-points projection. Without exact private team state, transfer ranking is explicitly unavailable.

With an exact private snapshot, the report now turns that shortlist into one conservative `CONSIDER` or `HOLD` decision with plain-language reasons. It can explain an insufficient heuristic gain, low evidence, a point hit, weak fixture or Start Score improvement, selling-value risk and the option to bank a transfer. The first pre-deadline decision is frozen in the private report and compared with the same Gameweek's player points afterward. This is a bounded counterfactual, not proof that the manager followed the advice or a claim about total-team causality.

The [four-Gameweek squad outlook](docs/STANDARD_FPL_SQUAD_OUTLOOK.md) now adds a legal XI, ordered bench, captaincy, availability pressure, bench-cover count, core starters and rotation players for every actionable round. It stays inside the private Standard report and uses Start Score and Captain Score only as transparent selection heuristics.

The future toolkit page is planned to offer `Draft H2H` and `Standard FPL` as separate modes in a shared shell. That selector is intentionally not exposed on the public Draft dashboard until secure private Standard report delivery exists; switching modes must never mix their report objects.

## GitHub Actions

The workflow runs every four hours at minute 17 and can also be run manually. `FPL_DRAFT_ENTRY_ID` is configured as `336654` in the workflow. `FPL_DRAFT_LEAGUE_ID` is optional unless live API validation shows it is needed.

The notification email address is deliberately not committed. When email alerts are implemented, the address and provider API key should be GitHub Actions secrets.

## Privacy

League payloads can contain manager names. Raw API responses and full historical snapshots are gitignored. Minimal ownership and aggregate manager-decision states persist only what is needed for change detection and opponent profiling. The public report strips real manager names and entry IDs, but keeps each manager's chosen league team name as the H2H label.

## Current boundary

The toolkit now includes projections, recommendation scoring, injury-return timing, stash/roster value, opponent-drop monitoring, personalised add/drop comparisons, Recommended XI, H2H scouting and evidence-weighted opponent decision profiles. Material Decision Updates persist through the current actionable Gameweek, while the previous two completed decision cycles remain available as a compact archive. Once a Gameweek locks, live scoring and outcome diagnostics remain attached to that round while every actionable recommendation advances to the next open Gameweek. It remains decision support rather than an automated transaction system. Opponent profiles observe outcomes rather than intent: unsubmitted waiver requests are invisible, draft influence is deliberately small, and early samples are pulled toward neutral. Return dates come only from readable official FPL news, expected minutes and projected points remain transparent heuristics, and the model does not ingest press conferences or specialist medical reporting.

## Commercial-access concept

The current feasibility findings, agreed product directions, league-configuration research, model-generalization risks and paid-beta release gates are maintained in [Commercial Access Feasibility and Onboarding Concept](docs/COMMERCIAL_FEASIBILITY.md). It is the handover record for future work on selling access to the toolkit; it does not describe features that are already implemented unless explicitly marked as confirmed.

The separate [Standard FPL Mode Analysis](docs/STANDARD_FPL_MODE_ANALYSIS.md) records the feasibility, reusable modules, new calculations, data risks and phased design for supporting the budget-and-transfer game at `fantasy.premierleague.com`. It deliberately distinguishes standard FPL from Classic scoring inside FPL Draft. The [current-team authentication discovery](docs/STANDARD_FPL_AUTH_DISCOVERY.md) documents why FPL's login client cannot be reused by the GitHub Pages app, the no-credentials boundary and the next bounded personal experiment. The [private snapshot contract](docs/STANDARD_FPL_PRIVATE_SNAPSHOT.md) defines the strict source-independent handoff into the current analysis pipeline, while [Standard FPL Squad and Single-Transfer Legality](docs/STANDARD_FPL_TRANSFER_LEGALITY.md) records the dated rules and evaluator boundary.
