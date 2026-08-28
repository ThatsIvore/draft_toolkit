# Maintainer onboarding

Last reviewed: 28 August 2026

This is the repository-owned handoff for agents and maintainers. The source and tests remain authoritative; update this document when a durable data boundary or recommendation meaning changes.

## Product boundary

The public product is an advisory FPL Draft Head-to-Head dashboard. It may recommend actions but never submits them. The repository also contains an isolated private Standard FPL proof of concept. Standard squad, price, bank, transfer, captaincy, and chip state must never enter the Draft collector or `public/data/latest.json`.

FPL Draft Classic scoring and odd-sized H2H average-team fixtures remain unsupported until their separate report paths are implemented and validated. See [Authenticated FPL Draft Setup Audit](FPL_DRAFT_LIVE_SETUP_AUDIT.md).

## Sources of truth

| Output | Authoritative input | Gameweek | Important rule |
|---|---|---:|---|
| Current squad and opponent ownership | Current Draft `element-status` ownership | Now | Ownership can change after a deadline and must not rewrite a locked historical lineup. |
| Official Lineup | Draft entry-event picks | Scoring Gameweek | Resolve all 15 historical picks against the complete normalized player pool, because a post-deadline waiver may have removed one from the current squad. Reject an incomplete exact lineup instead of displaying 14 players. |
| Recommended XI | Current squad and selection model | Decision Gameweek | This is toolkit advice, not a submitted lineup. Start Score is not projected FPL points. |
| Recent Match Evidence | Finalized and data-checked Standard FPL event feed | Completed Gameweeks | Standard and Draft element IDs can differ. Map them through the official stable player `code`; never join cross-feed evidence by numeric element ID alone. |
| Transfer eligibility | Official availability plus curated, expiring transfer evidence | Decision horizon | A reliable agreed or confirmed league exit is a hard selection/acquisition block. Every lineup, waiver, H2H, threat, outlook, and planner consumer must enforce it independently. |
| Available recommendation | Same-position waiver comparison | Decision Gameweek and four-Gameweek value | `SWAP NOW`, `STASH SWAP`, `CONSIDER`, or `KEEP ROSTER` is the primary roster-action verdict. |
| H2H tactical move | Simulation of a waiver-supported candidate in the likely XI | Next matchup | This is a secondary one-Gameweek countermeasure. It must be labelled as tactical and must not silently override a stronger season-value verdict on Available. When the surfaces differ, inspect both models and explain the criteria rather than presenting either as universally authoritative. |
| Frozen outcome | First eligible pre-deadline forecast | Scoring Gameweek | Never rewrite a frozen forecast with later information. Exclude first-time mid-Gameweek baselines from calibration. |

## Main data flow

1. `collector.py` fetches Draft ownership, Draft bootstrap, fixtures, and the separate Standard bootstrap/event feed used for recent evidence.
2. `normalize.py`, `fixtures.py`, `transfer_intel.py`, `recent_match_evidence.py`, and `intelligence.py` build the shared player evidence.
3. `waivers.py`, `optimizer.py`, `injury_stash.py`, `h2h.py`, `planner.py`, `outcomes.py`, and `changefeed.py` produce distinct decision surfaces.
4. `privacy.py` is the final public redaction boundary.
5. `public/data/latest.json` is rendered by the feature-versioned dashboard assets. `public/about.html` defines user-facing terminology and limitations.

Do not assume that attaching a field once guarantees every consumer uses it safely. Eligibility rules that prevent a player from being selected or treated as a threat require downstream regression coverage.

## Recommendation precedence

The dashboard deliberately answers different questions:

1. **Available:** Is this a sufficiently strong same-position roster upgrade after immediate value, floor, upside, future value, and evidence are considered?
2. **H2H:** If a waiver-supported candidate were added, which legal swap produces the largest projected XI gain for the next matchup?

The H2H simulation currently considers positive waiver actions, including `CONSIDER`, and sorts primarily by next-Gameweek projected gain. It can therefore show a different player from Available's best season-long `SWAP NOW`. Treat that disagreement as a close decision requiring explanation, not as permission for the H2H card to replace the primary waiver verdict.

## Gameweek lifecycle

- `current_gameweek` is the live or most recent scoring round.
- `decision_gameweek` is the first round a new lineup or transaction can affect.
- During a live round, keep official lineup, live score, and outcome diagnostics on the scoring Gameweek while advancing Recommended XI, Available, Health & Transfers, H2H scouting, and Planner.
- Require the planning window to begin with the decision Gameweek.

## Privacy and state

- The Draft entry ID in repository configuration is intentionally public, but it must not leak into the published report.
- Public opponent labels may use chosen league team names. Remove real manager names and internal entry/owner identifiers.
- Raw payloads, full snapshots, and private Standard reports remain gitignored.
- Compact ownership and decision state may be committed only through the established collection workflow.
- Do not infer unsubmitted waiver, trade, or lineup intent.

## Change workflow

1. Fetch current `main` and inspect `git status`, recent commits, and applicable instructions.
2. For old work, run `git rev-list --left-right --count origin/main...<branch>` and inspect changes made since the merge base. Refresh before trusting previous tests.
3. Trace a behavior through generator, report schema, renderer, About documentation, and tests.
4. Add focused behavioral coverage; then run the full suite and `git diff --check`.
5. Open an unmerged pull request. Merge only after explicit approval for that PR and its verified head.
6. Report merge, Pages deployment, collection, and live-data behavior as separate states.

## Test map

| Concern | Primary coverage |
|---|---|
| Scoring versus decision horizon and collector integration | `tests/test_collector_horizon.py` |
| Current ownership versus locked lineup | `tests/test_collector_horizon.py`, `tests/test_lineup_frontend.py` |
| Cross-feed player identity and recent grades | `tests/test_recent_match_evidence.py`, `tests/test_collector_horizon.py` |
| Transfer eligibility and downstream H2H behavior | `tests/test_transfer_intel.py`, `tests/test_optimizer.py`, `tests/test_h2h.py` |
| Waiver semantics | `tests/test_waivers.py` |
| Public privacy | `tests/test_h2h_privacy.py`, mode-isolation and POC tests |
| Dashboard behavior | `tests/*frontend.py` plus rendered desktop/mobile inspection |

## Version vocabulary

`pyproject.toml` and `fpl_toolkit.__version__` contain the installable Python package version. Model and dashboard components use independent feature versions such as intelligence v0.6, H2H v1.3, and Overview v1.0. Do not infer deployment or model behavior from the package version alone.

## Documentation status

Feature documents should identify whether they describe **implemented**, **discovery**, **unsupported**, or **superseded** behavior and include a review date when rules or external interfaces can change. Keep `README.md` as the product and local-run overview, this file as the maintainer handoff, and `public/about.html` as the user-facing explanation.
