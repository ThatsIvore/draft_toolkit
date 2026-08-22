# Standard FPL Mode: Feasibility and Module Reuse

Last reviewed: 22 August 2026

This document evaluates adding the **standard Fantasy Premier League game** at `fantasy.premierleague.com` to the FPL Draft Toolkit. It is not an analysis of the **Classic scoring mode inside FPL Draft**. The two products have different squad-acquisition rules and must remain separate modes in the code and interface.

## Conclusion

Adding a useful standard FPL mode is feasible, and a majority of the toolkit's analytical foundation can be reused. Player normalization, fixture horizons, availability and role modelling, floor/upside calculations, legal-XI optimization, injury analysis, snapshots and much of the dashboard are portable.

The acquisition and strategy layer is not portable unchanged. Draft asks which unowned player to claim or which unique opponent roster to target. Standard FPL asks which affordable legal transfer or transfer sequence improves a shared-player squad after accounting for budget, selling prices, club limits, free transfers, point hits, captaincy and chips. That decision layer should be implemented alongside the Draft layer, not folded into it through scattered conditionals.

A sensible first release is a read-only personal standard FPL assistant: import the squad, show the Recommended XI, order the bench, recommend captain and vice-captain, surface injury/fixture risks and provide a short planning horizon. Legal transfer recommendations should follow once authenticated current-team discovery and the price model are reliable. Chip planning belongs later.

## Technical POC status

The first isolated technical path is now implemented behind `fpl-toolkit --mode standard-fpl`. It:

- accepts an ordinary manager-facing standard FPL entry URL;
- reads public bootstrap, fixture, entry-history and locked-picks responses;
- maps the complete standard player pool onto the shared player contract;
- reuses the fixture horizon, performance baseline, player intelligence and legal-XI optimizer;
- orders the outfield bench and adds captain/vice-captain heuristics;
- writes a private, gitignored JSON report without retaining the configured entry identifier; and
- prevents this private report from being sent through the existing `--publish` path.

The source-independent `standard-fpl-private-snapshot-v1` contract is also implemented and documented in [Standard FPL Private Snapshot Contract](STANDARD_FPL_PRIVATE_SNAPSHOT.md). When a trusted future connector produces that file, the same command validates and uses the exact decision-Gameweek squad, purchase/selling prices, bank, free-transfer balance and chip state. It fails closed on stale Gameweeks, unknown players, malformed squad/captaincy state and unexpected fields that could contain identity or credentials. The connector itself is still gated by the authentication discovery.

The 2026/27 squad rules and single-transfer legality layer are also implemented, as documented in [Standard FPL Squad and Single-Transfer Legality](STANDARD_FPL_TRANSFER_LEGALITY.md). Private reports now include the active rules version and structural squad validation. The evaluator can reject an illegal or unaffordable one-for-one move and calculate its incremental points deduction, but candidate ranking and projected net benefit remain future work.

The POC has also been exercised against a live 2026/27 entry without committing its identifier or report. It correctly separated live GW1 facts from GW2–GW5 advice and generated a legal 15-player/11-starter result.

This is intentionally not full Phase 1 completion. The public locked squad can become stale after a transfer, and the report does not claim access to current pre-deadline picks, purchase/selling prices, free-transfer balance or chip state. Authentication discovery has now confirmed that the toolkit cannot reuse FPL's OAuth client on GitHub Pages: the callback is rejected and the private team API does not permit the toolkit origin through CORS. The evidence, design boundary and next personal experiment are recorded in [Standard FPL Current-Team Authentication Discovery](STANDARD_FPL_AUTH_DISCOVERY.md).

## Terminology and product boundary

| Mode | Host | Player ownership | Main decisions | Current status |
|---|---|---|---|---|
| FPL Draft Head-to-Head | `draft.premierleague.com` | One manager per player, no budget | Lineup, waivers, free agents, trades and weekly opponent | Implemented baseline |
| FPL Draft Classic scoring | `draft.premierleague.com` | One manager per player, no budget | Lineup, waivers and season-points league race | Unsupported; separate future discovery |
| Standard FPL | `fantasy.premierleague.com` | Players may be owned by many managers | Transfers, budget, captaincy, bench, chips and rank | Next personal product direction |

The word **Classic** should only describe FPL Draft's Classic scoring option when discussing Draft. This standard FPL mode should be labelled **Standard FPL** or simply **FPL** in code, documentation and navigation.

## Confirmed standard FPL rules that affect the design

The official standard FPL squad structure is close enough to Draft to support substantial reuse: 15 players consisting of two goalkeepers, five defenders, five midfielders and three forwards. A legal starting XI has one goalkeeper, at least three defenders, at least two midfielders and at least one forward. The important additional constraints are:

- a £100.0m initial squad budget;
- no more than three players from one Premier League club;
- one free transfer per Gameweek, with up to five free transfers banked;
- a four-point deduction for every transfer beyond the free allowance;
- changing player prices and a selling price that does not always equal the current market price;
- a captain whose points are doubled and a vice-captain who inherits the multiplier only if the captain does not play;
- an ordered substitute bench and automatic substitutions; and
- two each of Wildcard, Free Hit, Triple Captain and Bench Boost during 2026/27, with one set available in each half of the season and only one chip playable in a Gameweek.

Primary references: [official squad selection guide](https://www.premierleague.com/en/news/2174419/fpl-basics-how-to-pick-a-squad), [official transfer guide](https://www.premierleague.com/en/news/2174907), [official team-management guide](https://www.premierleague.com/en/news/2174899/fpl-basics-managing-your-team), [official chip guide](https://www.premierleague.com/en/news/4362085), [official scoring guide](https://www.premierleague.com/en/news/2174909) and [2026/27 rule changes](https://www.premierleague.com/en/news/4679873).

Rules must be versioned by season. Price behaviour, scoring and chip availability can change, so they must not be treated as permanent constants merely because they are correct for 2026/27.

## Data feasibility

The public standard FPL responses already expose much of the data needed for a read-only assistant:

- global player, club, Gameweek, price, selection and performance data;
- an entry's completed-Gameweek picks, captain flags, multipliers, automatic substitutions and active chip;
- completed-Gameweek team value, bank, transfer count, transfer cost, rank and points; and
- public entry history and completed transfer history.

The standard player response includes fields that map directly to the current normalized player model, including minutes, starts, goals, assists, clean sheets, bonus, expected goal involvement, form, points per game, expected next points, status, playing chance and news. It also adds standard-FPL-specific fields such as current cost, price movement, selection percentage and transfer volume.

The major implementation gate is **the manager's current pre-deadline state**. Completed-Gameweek public picks are suitable for historical evaluation, but the current editable squad endpoint rejects unauthenticated access. The official FPL web application uses OpenID Connect authorization-code flow with PKCE, yet its registered client rejects the toolkit's callback URL and the protected API does not allow the GitHub Pages origin through CORS. A genuinely useful personal assistant still needs the latest squad, bank, purchase/selling prices, free-transfer balance and chip availability before the deadline, but it cannot obtain them by imitating the official login. See [the authentication discovery](STANDARD_FPL_AUTH_DISCOVERY.md) for the supported hosted architecture, prohibited credential workarounds and bounded browser-local experiment.

Public endpoints and identifiers are not proof that commercial reuse is permitted. The data-rights gate recorded in `COMMERCIAL_FEASIBILITY.md` still applies before selling access.

## Current module reuse assessment

| Current area | Reuse level | Standard FPL treatment |
|---|---|---|
| Fixture collection and actionable-Gameweek logic | High | Reuse the fixture horizon and deadline-aware distinction between scoring and actionable Gameweeks. |
| Player normalization | High, with adapter | Populate the common player shape from standard FPL data; add price, popularity and transaction fields without placing FPL-specific rules in the shared schema. |
| Performance baseline and player intelligence | High | Reuse form, role, minutes, availability, floor, upside, fixture and injury calculations. Replace ownership-status recommendation labels such as `CLAIM` with mode-specific actions. |
| Recommended XI optimizer | High | The squad shape and legal formations match. Add captain, vice-captain, bench order, automatic-substitution risk and Bench Boost context. |
| Multi-Gameweek planner | Medium–high | Reuse player and fixture scores. Replace Draft streamer/free-agent assumptions with transfer horizons, retained value and chip context. |
| Waiver replacement analysis | Medium | The same-position add/drop comparison is a useful primitive, but every proposal needs affordability, bank, selling price, club-quota, free-transfer and point-hit checks. |
| Injury stash model | Medium–high | Reuse health and return modelling. Add the monetary and transfer opportunity costs of holding or selling a player. |
| Roster value | Medium | Keep projected football value; add value per cost, money tied up, selling loss and alternative combinations. Draft scarcity and replacement level do not transfer directly. |
| H2H matchup and opponent profiles | Low | Draft's unique-roster matchup model does not fit. Build rank, rival, ownership and differential analysis for standard mini-leagues instead. |
| Outcome diagnostics | Medium–high | Reuse forecast-versus-actual player and lineup evaluation. Add captain, bench, chip and transfer-hit attribution; omit H2H result fields. |
| Decision Updates and snapshots | High, with new event types | Reuse the state/diff mechanism for injury, projection and lineup changes; add price, transfer-plan, captain, chip and rank changes. |
| Dashboard shell and player views | High | Reuse cards, filters, player drawer, pitch and responsive layout. Rename Draft-specific surfaces such as Available and H2H. |
| Privacy boundary | High, with expansion | Continue removing entry IDs and real manager identities from public reports; also treat bank, squad value, transfer plans and current pre-deadline picks as private account data. |

### Calculations that can remain shared

The following calculations are game-mode independent when they operate only on players and fixtures:

- fixture difficulty over one or more Gameweeks;
- availability, injury-return and expected-minutes signals;
- performance baselines and sample confidence;
- floor, upside, roster and stash-style football value;
- projected legal starting-XI selection; and
- forecast-versus-actual diagnostics after a Gameweek.

Their outputs should be treated as shared analytical primitives. The final recommendation text and action threshold belong to the selected game mode. For example, the same player score can support a Draft `CLAIM` recommendation or a standard FPL `BUY IF AFFORDABLE` candidate, but those actions are not equivalent.

### Calculations that need standard FPL wrappers

The existing same-position replacement comparison is a strong starting point for a one-transfer model. The standard FPL wrapper must reject or price every proposed move using:

1. the outgoing player's actual selling price, not merely current market price;
2. cash in the bank;
3. the incoming player's current cost;
4. the maximum-three-per-club rule after the move;
5. positional squad quotas;
6. the number of available free transfers;
7. any point deduction; and
8. the expected benefit over a multi-Gameweek horizon.

A useful transfer score should report both gross improvement and net improvement after a hit. It should not present a four-point deduction as an automatic four-point break-even calculation because the transfer can affect captaincy, bench cover and several future Gameweeks.

## New standard FPL capabilities

These components do not have safe Draft equivalents and should be new mode-specific modules:

- `StandardFplApiClient` and a normalized standard entry/squad state;
- budget, purchase-price and selling-price accounting;
- a squad-legality validator for budget, positions and club quotas;
- one- and multi-transfer optimization, including free transfers and point hits;
- captain and vice-captain recommendations;
- ordered-bench and automatic-substitution analysis;
- chip state and chip-planning models;
- standard mini-league rank, rival and differential analysis; and
- season-versioned standard FPL rules.

An official price-change predictor exists for 2026/27, but price-change planning should remain advisory. Transfer recommendations should not trade away expected points merely to chase uncertain team value.

## Recommended architecture

Use an explicit game-mode boundary instead of adding `if standard_fpl` checks throughout the Draft collector:

```text
shared core
  player normalization contract
  fixtures and Gameweek horizon
  performance, availability and projection primitives
  legal-XI optimizer and outcome evaluation

Draft mode
  unique ownership, waivers and free agents
  trades, scarcity, H2H and Draft Classic scoring

Standard FPL mode
  budget, prices, transfers and hits
  captaincy, bench order, chips, rank and rivals
```

The report should carry a validated mode such as `draft_h2h`, `draft_classic` or `standard_fpl`. Shared code should calculate football value; mode builders should turn that value into legal decisions and user-facing recommendations. This separation protects the current Draft dashboard while allowing both products to improve from shared model work.

## Suggested delivery sequence

### Phase 0 — private data contract

- **Implemented:** define and validate the source-independent current squad, price, transfer and chip snapshot schema.
- For a personal experiment, prove or reject a user-initiated same-origin snapshot that does not extract or replay browser credentials.
- For any hosted product, obtain Premier League approval and a registered client before implementing account connection.
- Keep entry identifiers and account details out of committed fixtures and public reports.
- Add season-versioned rule fixtures and failure states for unavailable authentication.

### Phase 1 — personal read-only assistant

- Import the 15-player squad.
- Reuse player intelligence, fixtures, injury analysis and Recommended XI.
- Add legal bench ordering, captain and vice-captain recommendations.
- Show the next actionable Gameweek and a four-Gameweek squad outlook.

This phase provides personal value without attempting to solve the harder transfer-combination problem.

### Phase 2 — legal transfer assistant

- **Foundation implemented:** model bank, current prices, purchase/selling prices, squad shape, club quotas, free-transfer use and incremental hit cost for a specified single transfer.
- Rank legal one-transfer moves using the existing add/drop comparison as a primitive.
- Add hold recommendations and explicit reasons for rejected candidates.
- Attribute actual results to transfer decisions after the Gameweek.

### Phase 3 — transfer sequences and hits

- Optimize two- and multi-transfer combinations across the planning horizon.
- Account for banked free transfers and point deductions.
- Separate short-term gains from longer-term squad restructuring.
- Add price-change risk as context, not the dominant objective.

### Phase 4 — chips and mini-league intelligence

- Add chip-aware lineup and transfer planning.
- Model blanks, doubles and fixture rescheduling conservatively.
- Add rank gaps, rival squads after deadlines, effective ownership and differentials.
- Explain uncertainty rather than presenting long-horizon chip forecasts as precise.

## Difficulty and risk summary

| Capability | Relative difficulty | Main uncertainty |
|---|---|---|
| Historical/public standard FPL import | Low | Schema drift and season rule changes |
| Current personal squad connection | High / externally gated | Registered hosted integration, or a constrained personal same-origin snapshot that never exports credentials |
| Existing player intelligence on an FPL squad | Low | Mode-specific labels and thresholds |
| Recommended XI and bench | Low–medium | Autosub ordering and special chip context |
| Captain and vice-captain | Medium | Upside, minutes risk and effective-ownership trade-offs |
| Legal single-transfer recommendations | Medium | Accurate selling price, bank and free-transfer state |
| Multi-transfer/hit optimizer | Medium–high | Combinatorial search and multi-Gameweek uncertainty |
| Chip planner | High | Doubles, blanks, schedule changes and long-horizon uncertainty |
| Mini-league rival intelligence | Medium | Deadline visibility and shared-player ownership semantics |

## Recommendation

Proceed with the bounded Standard FPL proof of concept, but treat authenticated current-team access as an explicit external gate. Do not implement a hosted FPL login by reusing the official client, and do not ask for credentials or browser tokens. The next success criterion is narrower: prove or reject a browser-local, same-origin, read-only snapshot that exports only sanitized team state. If that requires helper access to a bearer token, stop and retain public locked picks plus manual private state until a sanctioned integration exists.

Only after that proof is reliable should the project turn the current waiver comparison into a budget-aware transfer engine. This sequence maximizes reuse, produces early personal value and isolates the genuinely new risks.
