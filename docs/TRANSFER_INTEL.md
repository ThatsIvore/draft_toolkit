# Transfer Intel v1

The toolkit supplements official FPL availability with a small curated transfer-evidence overlay. It exists for the short interval between reliable transfer reporting and the FPL bootstrap updating a player's news, club and fixtures.

## Evidence tiers

| Status | Score effect | Decision behavior |
|---|---|---|
| `talks` | None | Display `RUMOUR WATCH` only |
| `deal_agreed`, same league | None until confirmation | Preview the destination run and display `EARLY PICKUP` only when its guardrails clear; current-match availability stays with the official FPL feed |
| `confirmed`, same league | Destination fixtures replace stale current-club fixtures until the feed synchronizes | Evaluate `EARLY PICKUP` guardrails |
| `deal_agreed` or `confirmed`, leaving the league | Selection and acquisition are blocked | Exclude from starts, claims and injury-stash candidates |

Every record includes a source tier, source URL, report time and expiry. Expired records have no effect. The default records are packaged in `src/fpl_toolkit/data/transfer-intel.json`; `FPL_TRANSFER_INTEL_PATH` may point a trusted deployment at another validated file with the same schema.

## Early-pickup guardrail

A same-league move is labelled `EARLY PICKUP` only when all of the following hold:

1. the move is agreed or confirmed;
2. the destination four-Gameweek Fixture Score is at least 65;
3. the destination run improves on the current club by at least 5 heuristic fixture points; and
4. curated role evidence says `projected_starter` or `strong_rotation`.

An attractive destination is therefore insufficient on its own. Talks never alter scoring, a transfer fee never implies a starting role, and `MOVE WATCH` is not a transaction recommendation.

## Integration

- Shared intelligence applies the same selection/acquisition guardrails in Draft and Standard FPL.
- Selection eligibility is a hard shared rule rather than a score discount. A blocked player receives zero Start Score, expected minutes, projected points, uncertainty range and effective H2H roster contribution even if a downstream consumer receives stale pre-transfer intelligence.
- Confirmed destination fixtures feed lineup, waiver and planning calculations without waiting for a stale club assignment. An agreed but unconfirmed move remains a separate advisory preview.
- The public **Availability & Transfers** view shows health decisions, stashes, return dates, transfer risks and early-pickup candidates.
- Transfer evidence becomes a persistent Decision Update for the actionable Gameweek.
- H2H opponent lineups inherit the selection guardrail, so an agreed exit cannot remain a projected threat.

Draft ownership and projection eligibility remain separate facts. If the Draft feed still shows an exiting player on an opponent roster, the toolkit retains that ownership fact in `opponent_squad` but excludes the player from likely-XI priority, projected totals, current threat cards and four-Gameweek key threats. This makes the stale upstream roster visible without allowing it to contaminate advice.

The overlay remains advisory and manually curated. It does not scrape arbitrary news, submit a transaction or rewrite a frozen active-Gameweek forecast.
