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
10. surface only material changes and decision-relevant injury/stash cases;
11. produce a redacted machine-readable report for a GitHub Pages dashboard.

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

## GitHub Actions

The workflow runs every four hours at minute 17 and can also be run manually. `FPL_DRAFT_ENTRY_ID` is configured as `336654` in the workflow. `FPL_DRAFT_LEAGUE_ID` is optional unless live API validation shows it is needed.

The notification email address is deliberately not committed. When email alerts are implemented, the address and provider API key should be GitHub Actions secrets.

## Privacy

League payloads can contain manager names. Raw API responses and full historical snapshots are gitignored. A minimal `data/state/ownership.json` persists only the identifiers needed for change detection. The public report strips manager names and entry IDs.

## Current boundary

The toolkit now includes projections, recommendation scoring, injury-return timing, stash/roster value, opponent-drop monitoring, personalised add/drop comparisons, Recommended XI and H2H scouting. It remains decision support rather than an automated transaction system. Return dates come only from readable official FPL news, expected minutes and projected points remain transparent heuristics, and the model does not ingest press conferences or specialist medical reporting.
