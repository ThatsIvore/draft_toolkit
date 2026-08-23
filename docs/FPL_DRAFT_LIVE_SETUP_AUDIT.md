# Authenticated FPL Draft Setup Audit

Last reviewed: 22 August 2026

## Purpose and boundary

This audit checked the current signed-in 2026/27 FPL Draft interface for league settings and lifecycle rules that can change toolkit behaviour. It used normal rendered pages only. No league was created, joined, left, edited or deleted; no draft, waiver, free-agent move, trade or lineup action was submitted; and no private league, manager or entry identifier is recorded here.

The rendered pages inspected were Create Private League, Join Public League, Transactions, League and the official in-app Help/Rules page. A direct League Admin form was not available from the inspected live league, so administrator-only timer behaviour is recorded from the current official in-app answer rather than claimed as a directly observed form control.

## Confirmed configuration

| Area | Current rendered choices or rule | Toolkit consequence |
|---|---|---|
| Private league size | Independent minimum and maximum manager selectors, each offering 2–16 | Detect actual joined count and configured bounds; never infer six managers from the current repository |
| Public league size | 4, 6 or 8 | Public onboarding can validate these three formats explicitly |
| Scoring | Head-to-Head or Classic for private and public leagues | Route to an H2H experience or block/route to the future League Race mode |
| Initial draft target | Select a target Gameweek and a future date/time more than three hours before that Gameweek deadline | Draft Assistant scheduling and actionable-Gameweek validation must use both values |
| Initial draft order | Random | Treat the initial snake order as random unless a later official source says otherwise |
| Pick clock | 30, 60, 90 or 120 seconds; default 90; changed by the administrator on League Admin | Draft Assistant responsiveness must use the detected clock rather than a hard-coded 90 seconds |
| Time zone | Full time-zone selector; the signed-in browser selected its local zone | Store an IANA zone with schedules and avoid converting deadlines twice |
| Redrafts | Up to three after the initial draft | A redraft starts a new roster-history epoch rather than hundreds of ordinary transfers |
| Redraft order | Random or descending/reverse current league rank | Preserve the selected method with each draft-history epoch |
| Redraft lock | A redraft for Gameweek N locks when Gameweek N-1 starts | Warn before the edit boundary and stop treating the schedule as mutable afterward |
| Trades | None, all, administrator veto or manager veto | Trade recommendations are applicable only when the detected mode permits them |

The Create League form also contains team name, favourite team, email-notification consent, league name and terms fields. They are onboarding/UI state, not inputs to the decision models, and should not be copied into a public report.

## Confirmed transaction rules

- A waiver request swaps one player for an unowned player in the same position and can lose to a manager with higher priority.
- Free agency normally begins after waivers are processed and stays open until the Gameweek deadline; an available player can then be signed immediately in a same-position swap.
- Trade mode can be changed before the draft but becomes fixed once the draft is under way.
- A trade must exchange equal player counts and match positions across both sides.
- An accepted trade that requires approval proceeds unless vetoed by the applicable deadline.
- Manager-veto mode rejects a trade when at least 50% of managers object.
- Trade offers must be accepted by the waiver deadline. Where approval is required, the trade deadline is 24 hours before the waiver deadline.
- If too few managers have joined by the scheduled draft, the draft moves back 24 hours. After three such pushbacks the league is deleted; changing league settings resets that counter.

The live Transactions screen showed the next transaction deadline, player search, an available-only filter, position/club filters, watchlist/proposed views and official sort choices including Draft rank, current/total points, form, starts, expected metrics and defensive contribution. These controls support discovery and QA but do not expose unsubmitted waiver intent.

## Odd-manager Head-to-Head leagues

The official current Help/Rules answer resolves the previous bye uncertainty:

- an odd-sized H2H league receives an **average team** so every real manager has a fixture;
- that synthetic opponent scores the league's average Gameweek score; and
- it is not a normal manager with a 15-player roster to scout.

The present H2H builder requires an opponent league entry and at least 11 owned players. It will therefore return an unavailable or unreliable matchup for an average-team fixture rather than model the official rule. Supporting every permitted H2H size requires a distinct average-opponent branch:

1. detect the official average-team representation in league fixtures;
2. label it **League average**, not a manager or chosen team name;
3. use official average points for live/final scoring;
4. estimate future average fixtures from the mean projected legal XI total of real league managers;
5. omit roster threats, positional weaknesses, counterweights and opponent decision profiles because no synthetic roster exists; and
6. retain normal Recommended XI, waivers, injuries, stashes and Planner advice for the customer's own team.

The exact fixture/standings payload representation remains unverified. Obtain a sanitized odd-sized H2H league payload before implementing this branch; do not guess a magic entry ID or null shape.

## Classic and redraft implications

The live UI reconfirmed that Classic is a first-class league choice rather than an edge-case flag. The current H2H dashboard must remain blocked for Classic until the planned League Race report exists.

Redrafts also need explicit lifecycle detection. The collector should preserve standings and completed results, close the old ownership/opponent-decision epoch, reset ownership-derived baselines and prevent the mass roster replacement from appearing as waiver activity. The selected redraft order and effective Gameweek belong in the new epoch metadata.

## Recommended next Draft work

1. Capture sanitized league-details, standings and fixture rows from an odd-sized H2H league containing the average team.
2. Add a normalized `league_context` containing scoring mode, manager count, configured size bounds, trade mode, pick clock and roster epoch.
3. Implement the average-team H2H branch with fixtures for 3-, 5-, 7-, 9-, 11-, 13- and 15-manager leagues.
4. Add redraft detection and epoch reset before offering redraft leagues as supported.
5. Continue treating Classic as unsupported until its separate League Race experience is implemented.

These are compatibility requirements for multi-league access, not blockers for the repository's current six-manager H2H league.
