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

Commercialization is no longer the near-term project driver. The current priority is the owner's personal enjoyment and decision advantage, with support for the standard Fantasy Premier League game as the next major product direction. Multi-user infrastructure, payments and user acquisition should remain documented as optional future work rather than displacing personally valuable features.

## Decisions already made

1. **Customer** — The customer is an individual league manager, not an entire league.
2. **Product boundary** — The toolkit remains decision support. It must not submit lineups, waivers or trades automatically.
3. **Onboarding quality** — A paying user must not have to inspect browser developer tools, find API payloads or configure repository variables.
4. **Draft history** — Draft-history input should be incorporated by merging suitable parts of the earlier Draft Assistant into this repository or recreating that workflow here.
5. **Visual assets** — Original, generic team shirts may use user-selected solid colours or simple stripe patterns. They should omit sponsors, crests and official marks.
6. **Privacy** — Real manager names and internal Draft entry identifiers must remain outside public reports. Chosen league team names can be used where the existing privacy boundary permits them.
7. **Commercial data permission** — Written permission or a suitable licence is a hard launch gate before accepting payment.
8. **League-size coverage** — The paid H2H product must support every permitted private-league size from 2 through 16 managers, including odd-numbered leagues where the official schedule allows them.
9. **FPL Draft Classic scoring** — Classic-scoring Draft leagues are unsupported until a deliberate Draft Classic mode is implemented. Onboarding must detect and reject them clearly rather than running H2H assumptions.
10. **Roadmap motivation** — Personal value and enjoyment take priority over monetary return or adding users. A separate standard FPL mode is the next major product direction; commercial account and payment work is deferred unless that motivation changes.
11. **Terminology** — Standard FPL at `fantasy.premierleague.com` is not "Classic Draft." It is distinct from the Classic scoring option within FPL Draft and requires budget, transfer, captaincy and chip models.
12. **Future mode navigation** — Once secure private Standard FPL reports exist, the shared toolkit page will use a `Draft H2H` / `Standard FPL` selector (segmented on desktop and compact on mobile). Until then, the public page remains Draft-only; unsupported Draft Classic remains hidden.

## Commercial data permission

The [Premier League Terms of Use](https://www.premierleague.com/en/terms-and-conditions) reserve copyright, database and related rights and prohibit commercial use, reuse, redistribution or creation of a database from website/app material without prior written approval. Public technical access to FPL or FPL Draft responses is therefore not sufficient evidence that a paid derived service is permitted.

The Premier League directs business and data proposals to `partnerships@premierleague.com`. It directs permission requests for match data, including fixture feeds, to Football DataCo. See the [official business, trademark and data guidance](https://www.premierleague.com/en/news/102426).

Before accepting payment, the project must:

- inventory every external field and endpoint it consumes;
- distinguish FPL Draft game data, match/fixture data, branding and independently derived analytics;
- obtain written permission or appropriate licences for the intended subscription use;
- retain the permission scope and any operational conditions as a project record; and
- obtain appropriate legal advice rather than treating this concept document as a legal opinion.

A free, limited discovery or closed beta may continue while permission is investigated, but it must not be presented as evidence that later commercial use is authorised.

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

The Premier League sign-in subject identifier is distinct from a Draft entry identifier. The current frontend represents the authenticated account with an OpenID-style profile subject while its Draft entries use numeric entry IDs. Supplying an account UUID to the public Draft entry endpoint does not resolve a team. Onboarding must therefore never ask a user to copy this account identifier from storage or authentication data.

The Draft single-page application also keeps the useful entry identifier out of its ordinary visible URL. Asking a user to copy a team-page URL is therefore not a reliable discovery method.

A private-league invite code is a join credential, not an existing entry identifier. The current frontend submits it to a mutating private-join endpoint together with new entry details. The toolkit must not call that endpoint merely to discover an existing team, and invite codes must not be committed or displayed publicly.

For personal Draft discovery, obtain the numeric Draft entry from the normal signed-in account entry list using a read-only, session-bound flow. A future automated onboarding flow should use a sanctioned authenticated account-to-entry association and present the user's Draft entries for selection, without exposing tokens, UUIDs or requiring developer tools.

Standard FPL has a different entry URL and data model. Its public entry pages expose a numeric entry identifier, but public completed-Gameweek picks do not by themselves solve private, pre-deadline onboarding. The separate [Standard FPL Mode Analysis](STANDARD_FPL_MODE_ANALYSIS.md) records the current data finding and proposed user-authorized connection.

The completed [Standard FPL authentication discovery](STANDARD_FPL_AUTH_DISCOVERY.md) confirms that FPL's own OAuth client cannot be reused by the toolkit: the GitHub Pages redirect URI is rejected, and the protected current-team endpoint does not grant that origin cross-origin access. A commercial **Connect FPL** flow therefore depends on Premier League approval, a toolkit-specific registered client and permitted data use. Capturing passwords, copied sessions or bearer tokens is not an acceptable shortcut. A later live probe proved a separate personal-use path: the normal signed-in Pick Team and Transfers views expose the strict snapshot allowlist through rendered DOM state. That can support a local helper, but its manual installation and markup fragility do not satisfy paid onboarding.

The internal [Standard FPL private snapshot contract](STANDARD_FPL_PRIVATE_SNAPSHOT.md) is implemented. It gives the analysis pipeline a strict, versioned and identifier-free representation of current squad, price, transfer and chip state. This reduces connector coupling but does not remove the external authentication or commercial-permission gates.

The [2026/27 Standard FPL squad, single-transfer legality and advisory ranking layer](STANDARD_FPL_TRANSFER_LEGALITY.md) is also implemented. It separates hard game rules and point-hit cost from model heuristics, fails closed when the live season is newer than the verified ruleset and refuses to rank transfers from stale public state.

The original Draft/H2H product remains protected by a permanent mode-isolation regression: Standard-only modules cannot enter the Draft collector or H2H decision engines, the default CLI and scheduled public collection remain Draft, and Standard FPL reports cannot use the public publish path. This boundary is documented in [Standard FPL Mode Analysis](STANDARD_FPL_MODE_ANALYSIS.md#h2h-protection-boundary).

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

Official FPL Draft guidance and the authenticated 2026/27 setup screens confirm that private leagues allow **2–16 managers**. Public leagues are offered in **4-, 6- and 8-manager** formats, and the official guide describes leagues of up to eight as the practical optimum. Every manager still drafts 15 players: two goalkeepers, five defenders, five midfielders and three forwards. See the [official FPL Draft guide](https://www.premierleague.com/en/news/1245444/fpl-draft-what-you-need-to-know) and the [authenticated setup audit](FPL_DRAFT_LIVE_SETUP_AUDIT.md).

### League-manager choices

| Setting | Confirmed choices | Product impact |
|---|---|---|
| League type and size | Private: 2–16 managers; public: 4, 6 or 8 | Access/onboarding and major model input |
| Scoring mode | Classic or Head-to-Head | Changes or removes opponent-specific features |
| Initial draft schedule | Administrator selects date and time for a private league | Draft Assistant scheduling |
| Draft order | Random; renewed/redraft leagues can use reversed prior standings | Draft-history interpretation |
| Pick clock | 30, 60, 90 or 120 seconds; default 90 | Draft Assistant responsiveness and live countdown handling |
| Trade policy | No trades, all trades, administrator approval or manager approval | Controls whether trade analysis is applicable |
| Redrafts | Up to three additional drafts during the season | Requires a new roster-history epoch |
| Redraft schedule | Target Gameweek, date and time; locks when the preceding Gameweek starts | Collection and model lifecycle |

The four trade modes and their processing rules are documented in the [official trade guide](https://www.premierleague.com/en/news/1245445). Additional drafts and their scheduling are confirmed in the [2026/27 FPL Draft announcement](https://www.premierleague.com/en/news/4683615/fpl-draft-is-live-for-202627-register-now).

The live setup audit also confirmed that an initial private draft must be scheduled in the future and more than three hours before its target Gameweek deadline; initial order is random; a redraft order can instead be random or descending current league rank; and trade settings become immutable once the draft begins. Manager-veto mode requires at least 50% of managers to object, and approval-based trade deadlines occur 24 hours before the waiver deadline.

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

Classic leagues are currently an explicitly unsupported configuration. The paid application must detect Classic scoring during onboarding and stop before collection or payment activation with a clear explanation.

#### Short FPL Draft Classic-mode discovery

**Conclusion:** Classic support is a moderate product extension, not a collector or modelling rewrite. No architectural blocker was found, and the potential value is high because it adds an entire official league mode.

The current league-details response includes an explicit scoring field, so mode detection should be low complexity. The present collector does not preserve or branch on that setting and unconditionally builds the current matchup, scoring-round matchup and four-Gameweek H2H outlook. Without an explicit mode gate, a Classic league would therefore receive missing-match errors rather than a purposeful experience.

Most of the product remains reusable in Classic mode:

- official player and ownership collection;
- fixture and intelligence models;
- free-agent and waiver comparisons;
- injuries, stashes and roster value;
- Recommended XI and the multi-Gameweek planner;
- league activity and aggregate manager-decision evidence; and
- the customer's own forecast-versus-actual lineup diagnostics.

The mode-specific replacement should be a **League Race** view rather than an H2H view. A useful first version would provide:

- current rank, total points and gaps to nearby managers and the leader;
- projected legal XI totals for every manager over the planning window;
- expected rank pressure or movement without presenting it as a probability;
- league-wide strongest and weakest position groups;
- the managers and rosters most relevant to catching or defending a position; and
- Classic-specific Decision Updates for rank, gap or projected-race changes.

| Work area | Relative difficulty | Discovery finding |
|---|---|---|
| Detect and reject Classic safely | Low | Add normalized league mode to report context and onboarding validation |
| Preserve the shared toolkit views | Low | Core collection, player models and Recommended XI are mode-neutral |
| Basic Classic League Race | Medium | Normalize Classic standings and project every manager's legal XI |
| Classic outcome diagnostics | Medium | Reuse the existing own-lineup evaluation and omit H2H result fields |
| Full value comparable to H2H Scout | Medium–high | Requires a new league-wide model, explanations, change signals and responsive UI |
| API validation | Medium uncertainty | Capture sanitized real Classic payloads and test standings, scoring and odd league sizes |

The clean implementation boundary is a normalized `league_context.scoring_mode`, followed by separate `h2h` and `classic` report builders. Shared projection helpers should move out of the H2H-specific module rather than being duplicated. The dashboard should select either **H2H** or **League Race** navigation from the report mode.

### Redrafts

A redraft changes league ownership without resetting the season standings. The collector should treat each draft or redraft as a new **roster epoch**:

- preserve season standings and completed results;
- close the previous ownership and opponent-decision history;
- reset ownership-derived baselines;
- associate the new draft history with the new epoch; and
- prevent mass ownership changes from appearing as ordinary waiver activity.

## Decided first commercial scope

The paid H2H product must support every private-league size from **2 through 16 managers inclusive**. Six-manager behaviour is only the existing baseline; all other sizes require league-relative scarcity, replacement-level and opponent-sample validation before the product can claim that coverage. The live rules audit confirmed that odd-sized H2H leagues use a synthetic **average team**, scoring the league's average Gameweek score, rather than a bye. That opponent has no manager roster to scout: use official average points for live/final scoring, project the future league mean, label it clearly and suppress roster-specific threat/profile analysis. The exact API representation still requires a sanitized odd-league payload.

FPL Draft Classic scoring remains unsupported until the separate League Race experience is implemented and validated. It is not the current personal development priority. The current priority is the distinct standard FPL game described in [Standard FPL Mode Analysis](STANDARD_FPL_MODE_ANALYSIS.md).

Every unsupported combination must be detected before payment or trial activation where possible. The toolkit must never silently run six-manager or H2H assumptions against a different configuration.

## Remaining commercial hurdles

| Hurdle | Why it matters | Proposed response |
|---|---|---|
| Official data rights and terms | Current terms restrict commercial reuse without prior written approval | Hard gate: obtain written permission or licences and appropriate legal advice before accepting payment |
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

1. **Completed:** validate the implemented private Standard FPL snapshot contract against the allowlisted fields visible in a live signed-in session; no contract revision was required.
2. **Personal exporter implemented:** the bounded DOM-only Standard FPL snapshot works without extracting or replaying credentials. Maintain the isolated two-stage helper and its live validation while keeping a hosted connection blocked pending Premier League approval and client registration.
3. **Completed:** the bounded Standard FPL proof of concept now adds a four-Gameweek squad outlook, explained hold-versus-transfer decisions and frozen, same-Gameweek player-point outcome evaluation while preserving the existing Draft report.
   A standalone browser-local viewer can render the generated private report from a file for personal testing without uploading it; this is not hosted private delivery or paid-user onboarding.
4. Obtain sanitized FPL Draft Classic league-details, standings and event payloads before revisiting the separate Draft League Race idea.
5. **Mostly completed:** the authenticated Create League, Join Public League, Transactions and current Help/Rules screens confirmed setup fields, exact 30/60/90/120-second timer choices, trade/redraft rules and the odd-manager average-team behaviour. Direct League Admin form structure and the odd-fixture API shape remain to be captured.
6. Record which Draft league settings and draft-history fields are available from current official responses without browser developer tools.
7. Define recalibration and acceptance tests for every Draft H2H league size from 2 through 16, including odd-size schedule fixtures.
8. Complete the data-source inventory and seek written commercial-use clarification from the Premier League and Football DataCo if commercialization resumes.
9. Select protected hosting, identity, database and payment architecture only when multi-user commercialization becomes an active goal.
10. If commercialization resumes, define subscription boundaries, data deletion, league switching and redraft recovery.

## Paid-beta release gates

Do not accept general paid sign-ups until all of the following are true:

- onboarding succeeds without developer tools or repository access;
- authentication and entitlement are enforced server-side;
- object-level tenant-isolation tests pass;
- the application detects league size, scoring mode and redrafts;
- unsupported configurations are blocked with clear explanations;
- every H2H league size from 2 through 16 has regression and calibration evidence, including odd-numbered schedule behaviour;
- no raw manager identities or internal entry identifiers enter public output;
- data freshness and collection failures are visible to the customer;
- payment cancellation and failed-payment access transitions are tested; and
- written data-use permission or suitable licences are recorded, and original visual assets have received appropriate review.

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
