# Commercial Access Feasibility and Onboarding Concept

Last reviewed: 22 August 2026

This document preserves the concept work for turning the current single-manager FPL Draft Toolkit into a product that can be sold to other FPL Draft managers. It is a product and technical feasibility record, not a claim that the commercial features described below have been implemented.

## Status vocabulary

- **Confirmed**: verified against the current project or an official Premier League source.
- **Decided**: a product direction agreed during concept work.
- **Proposed**: the recommended approach, still open to implementation choices.
- **Open**: requires research, testing, legal review or a product decision.

## Executive conclusion

Selling access appears technically feasible, but the current GitHub Pages deployment is a public, static, single-league dashboard. It is not by itself a secure subscription product.

A commercial version needs an authenticated application around the toolkit, server-side entitlement checks, tenant-separated league data, automated onboarding, supported-league validation and league-size-aware models. The existing collector and decision models remain valuable foundations; they should not be discarded.

The most credible first market is an individual FPL Draft manager who wants an analytical edge over the other managers in their league. The product should not depend on a league administrator inviting every participant, because those participants are the customer's competitors.

## Decisions already made

1. **Customer** — The customer is an individual league manager, not an entire league.
2. **Product boundary** — The toolkit remains decision support. It must not submit lineups, waivers or trades automatically.
3. **Onboarding quality** — A paying user must not have to inspect browser developer tools, find API payloads or configure repository variables.
4. **Draft history** — Draft-history input should be incorporated by merging suitable parts of the earlier Draft Assistant into this repository or recreating that workflow here.
5. **Visual assets** — Original, generic team shirts may use user-selected solid colours or simple stripe patterns. They should omit sponsors, crests and official marks.
6. **Privacy** — Real manager names and internal Draft entry identifiers must remain outside public reports. Chosen league team names can be used where the existing privacy boundary permits them.

## Access model

The Seerr/Plex experience is a useful interaction analogy: the user signs in once and the service decides whether that account has access. The authorization source should be different for this product.

League membership alone should not grant paid access. A Draft league is a data source, while a subscription or trial is the commercial entitlement. Treating every league participant as entitled would expose the customer's paid analysis to their competitors.

### Proposed authorization layers

| Layer | Purpose | Example |
|---|---|---|
| Identity | Establish who the user is | Email magic link or a supported identity provider |
| Entitlement | Establish whether the user may use the product | Active subscription, trial or manually granted access |
| League connection | Select the data to analyse | FPL Draft entry URL supplied during onboarding |
| Tenant authorization | Restrict every request and generated report | Server checks that the signed-in account owns the league connection |

The browser URL does not need to contain authentication tokens or Draft identifiers. A normal implementation can maintain the signed-in session in a secure, `HttpOnly` cookie and use non-sensitive route names. However, an identifier being absent from the address bar is not a security control. Every protected request must still be authorized on the server.

GitHub Pages cannot enforce these checks because published Pages assets and JSON files are publicly retrievable. A paid version therefore needs protected application hosting and a server-side component. The exact hosting, identity, database and payment providers remain open architecture choices.

## Required onboarding experience

The desired onboarding is:

1. The manager creates an account or signs in.
2. The manager starts a trial or purchases access.
3. The manager pastes their ordinary FPL Draft entry or team URL.
4. The application extracts the entry identifier and discovers the league automatically.
5. It detects league size, scoring mode and other available settings.
6. It presents a plain-language confirmation screen and clearly rejects unsupported configurations.
7. It imports or reconstructs draft history where available.
8. It performs the initial collection and opens the personalized dashboard.

Any fallback should be a normal form with clear instructions. Developer tools, raw JSON, GitHub variables and manual workflow runs are unacceptable onboarding requirements for paid users.

Draft entry and league IDs should be treated as identifiers rather than passwords. They should still be minimized in logs, excluded from public reports and protected by tenant authorization so that changing an ID cannot expose another customer's report.

## Draft-history integration

The current repository contains a verified six-manager, 90-pick draft history. That is useful for the present league, but it must not become a universal product assumption.

The integrated Draft Assistant workflow needs to:

- support `15 × manager count` total selections;
- derive manager order and each selection without hard-coded initials;
- handle players selected outside a recommendation shortlist;
- preserve the existing skip-turn behaviour where manual drafting is necessary;
- store only the minimum history needed for analysis;
- degrade gracefully when the official source does not expose complete historical data; and
- explain whether the history was automatically verified, manually supplied or unavailable.

Draft history is a small, decaying opponent prior in the existing model. It must not override observed in-season decisions.

## Team-shirt assets

Creating original assets is feasible. The preferred approach is a small procedural design system based on:

- a generic shirt silhouette;
- one or two user-selected colours;
- solid, vertical stripe, horizontal stripe or simple split patterns; and
- no sponsor, manufacturer logo, club crest or league mark.

For a paid release, the designs should also avoid deliberately reproducing a club's distinctive current kit arrangement. A legal/brand review is still required; omitting sponsors alone does not automatically remove every copyright or trademark concern.

## Confirmed FPL Draft league configuration

Official FPL Draft guidance confirms that private leagues allow **2–16 managers**. Public leagues are offered in **4-, 6- and 8-manager** formats, and the official guide describes leagues of up to eight as the practical optimum. Every manager still drafts 15 players: two goalkeepers, five defenders, five midfielders and three forwards. See the [official FPL Draft guide](https://www.premierleague.com/en/news/1245444/fpl-draft-what-you-need-to-know).

### League-manager choices

| Setting | Confirmed choices | Product impact |
|---|---|---|
| League type and size | Private: 2–16 managers; public: 4, 6 or 8 | Access/onboarding and major model input |
| Scoring mode | Classic or Head-to-Head | Changes or removes opponent-specific features |
| Initial draft schedule | Administrator selects date and time for a private league | Draft Assistant scheduling |
| Draft order | Random; renewed/redraft leagues can use reversed prior standings | Draft-history interpretation |
| Pick clock | Official guidance describes a 30–120 second range | Draft Assistant responsiveness; exact live choices still require UI verification |
| Trade policy | No trades, all trades, administrator approval or manager approval | Controls whether trade analysis is applicable |
| Redrafts | Up to three additional drafts during the season | Requires a new roster-history epoch |
| Redraft schedule | Target Gameweek, date and time | Collection and model lifecycle |

The four trade modes and their processing rules are documented in the [official trade guide](https://www.premierleague.com/en/news/1245445). Additional drafts and their scheduling are confirmed in the [2026/27 FPL Draft announcement](https://www.premierleague.com/en/news/4683615/fpl-draft-is-live-for-202627-register-now).

### Fixed rules relevant to the product

- A squad always contains 15 players: 2 GK, 5 DEF, 5 MID and 3 FWD.
- A player can belong to only one manager in a league.
- There is no transfer budget and no captain multiplier.
- The initial draft uses a snake order.
- Weekly waivers are followed by free agency.
- Before Gameweek 1, waiver priority is the reverse of draft order; later priority follows league position.

## League-size model impact

The current models were designed and calibrated around a six-manager league. That means 90 players are rostered. Official support up to 16 managers raises the rostered pool to 240 players and dramatically lowers replacement quality.

| Managers | Total owned | GK | DEF | MID | FWD |
|---:|---:|---:|---:|---:|---:|
| 2 | 30 | 4 | 10 | 10 | 6 |
| 4 | 60 | 8 | 20 | 20 | 12 |
| 6 | 90 | 12 | 30 | 30 | 18 |
| 8 | 120 | 16 | 40 | 40 | 24 |
| 10 | 150 | 20 | 50 | 50 | 30 |
| 12 | 180 | 24 | 60 | 60 | 36 |
| 14 | 210 | 28 | 70 | 70 | 42 |
| 16 | 240 | 32 | 80 | 80 | 48 |

### Components that require recalibration or parameterization

- free-agent and waiver replacement level;
- positional scarcity;
- add/drop upgrade thresholds;
- injury stash and hold value;
- roster-value percentiles;
- player availability and draft rankings;
- draft progress and expected remaining pool;
- H2H matchup strength relative to the league;
- opponent-profile confidence and sample-size shrinkage; and
- waiver competition estimates, without inferring unsubmitted opponent intentions.

Recommended XI is comparatively portable because it optimizes within the customer's own 15-player squad. Its player scoring can remain shared, but any comparison to replacements or league-relative strength must use the detected league context.

### Required league context

The commercial collector should create a validated league-context record containing at least:

- manager count;
- scoring mode;
- trade mode;
- public/private league type when exposed;
- draft timer and order method when relevant;
- redraft count, status and effective Gameweek;
- current roster-history epoch; and
- the customer's current waiver position when available.

This context should be discovered automatically and included in model inputs. It must not be trusted merely because it came from a browser form; server-side collection should verify it against the official data available.

## Scoring modes and redrafts

### Classic versus Head-to-Head

The current product is built around Head-to-Head play. In a Classic league, weekly opponent scouting and H2H matchup projections do not have the same meaning. Supporting Classic properly would require a table/rank-oriented replacement for those views, not merely hiding the opponent's name.

The paid application should either implement that separate experience or detect Classic scoring during onboarding and clearly state that it is unsupported.

### Redrafts

A redraft changes league ownership without resetting the season standings. The collector should treat each draft or redraft as a new **roster epoch**:

- preserve season standings and completed results;
- close the previous ownership and opponent-decision history;
- reset ownership-derived baselines;
- associate the new draft history with the new epoch; and
- prevent mass ownership changes from appearing as ordinary waiver activity.

## Proposed first commercial scope

A practical paid beta would support private **4-, 6- and 8-manager Head-to-Head leagues**. Six-manager behaviour is the existing baseline; four and eight should be explicitly calibrated and tested before accepting payment. Larger H2H leagues can follow after scarcity and opponent-sample behaviour have been validated. Classic scoring should be a separate milestone.

An even narrower invitation beta limited to six-manager H2H leagues would reduce initial model risk, but it would measure a smaller market. This is still an open product choice.

Every unsupported combination must be detected before payment or trial activation where possible. The toolkit should never silently run six-manager assumptions against another league size.

## Remaining commercial hurdles

| Hurdle | Why it matters | Proposed response |
|---|---|---|
| Official data rights and terms | Public technical accessibility does not establish permission to resell a derived service | Review current Premier League/FPL terms and obtain legal advice before launch |
| Authentication and entitlements | Static URLs cannot protect a paid dashboard | Add server-side identity, subscription state and authorization checks |
| Multi-tenant isolation | League data from one customer must never be returned to another | Namespace storage per account/league and test object-level authorization |
| API stability and uptime | An unofficial or changing endpoint can break onboarding and reports | Contract tests, health monitoring, cached last-known-good data and visible freshness states |
| Model validity | Advice calibrated for one six-manager league may not generalize | Back-test by league size and position; publish supported configurations |
| Classic and redraft handling | Current H2H assumptions can produce misleading output | Detect settings, implement explicit modes or block unsupported leagues |
| Payments and lifecycle | Trials, renewals, cancellations, refunds and failed payments affect access | Use a payment provider with webhooks and an auditable entitlement state |
| Privacy and retention | League payloads may contain manager names and persistent behavioural history | Minimize data, document retention/deletion and preserve the public-report redaction boundary |
| Supportability | Paying users expect actionable errors and recovery | Add onboarding diagnostics, retry controls and support-visible event logs without raw personal payloads |
| Security | Hidden identifiers and obscure URLs are not authorization | Threat-model account takeover, ID enumeration, session handling and data access |
| Visual branding | Official-looking assets may create legal or customer confusion | Use clearly original generic designs and complete a brand/legal review |
| Product proof | Technical feasibility does not prove willingness to pay | Test a small manager-focused beta, pricing and retention before major infrastructure work |

## Validation backlog

The next concept and discovery work should answer these questions:

1. Audit the authenticated live **Create League** and **League Admin** screens to confirm every setup field, exact timer choices and odd-manager H2H behaviour.
2. Record which league settings and draft-history fields are available from current official responses without browser developer tools.
3. Verify the current Premier League/FPL terms and commercial data-use position.
4. Define the recalibration and acceptance tests for 4-, 6- and 8-manager leagues.
5. Decide whether the first beta supports only six-manager H2H or all public-size equivalents: 4, 6 and 8.
6. Select a protected hosting, identity, database and payment architecture.
7. Define subscription boundaries: number of connected leagues, trial length, seasonality and cancellation behaviour.
8. Specify customer-facing data deletion, league switching and redraft recovery.

## Paid-beta release gates

Do not accept general paid sign-ups until all of the following are true:

- onboarding succeeds without developer tools or repository access;
- authentication and entitlement are enforced server-side;
- object-level tenant-isolation tests pass;
- the application detects league size, scoring mode and redrafts;
- unsupported configurations are blocked with clear explanations;
- supported league sizes have regression and calibration evidence;
- no raw manager identities or internal entry identifiers enter public output;
- data freshness and collection failures are visible to the customer;
- payment cancellation and failed-payment access transitions are tested; and
- data-use terms and original visual assets have received appropriate review.

## Continuation notes for a future maintainer

Start with this document and `README.md`, then inspect the current source and tests because implementation may have advanced beyond this concept record.

Preserve these project rules while commercializing:

- scoring-Gameweek facts and next-actionable-Gameweek advice are different concepts;
- Decision Updates must not be erased prematurely;
- Start Score is not projected FPL points;
- opponent models may observe completed actions but not infer unsubmitted intentions;
- draft influence remains a conservative, decaying prior;
- the dashboard is advisory and must not automate FPL transactions; and
- server-side authorization must protect commercial reports even when public identifiers are discoverable.

When a question is resolved, update its status here and link the implementation pull request or design decision. This file should remain the durable handover record for the commercial-access project.
