# Recent Match Evidence v1

## Decision

Draft H2H and Standard FPL share one football-performance layer. Model v0.6.0 supplements the durable prior and cumulative season statistics with grades derived from the newest four **completed and officially data-checked Gameweeks**.

This is not a third-party press rating. It uses the official public FPL `event/<gameweek>/live/` response after scoring is final. The collector keeps only compact derived evidence in its report; it does not persist the raw event payload.

## Inputs and grading

Each completed Gameweek grade compares a player only with players in the same position. The grade combines:

- total FPL points: 55%
- Bonus Points System score (BPS): 25%
- expected goal involvement: 15%
- minutes: 5%

Tied values receive the same percentile. Players without an appearance receive no grade for that Gameweek. The recent score weights the newest Gameweeks `1.0`, `0.75`, `0.55`, and `0.4`, then reserves 15% for recent playing-time evidence.

A double Gameweek is one aggregate Gameweek grade in v1. Fixture-level grades would require a more expensive player-by-player feed and are a later option.

## Guardrails

- An event counts only when official bootstrap data says both `finished: true` and `data_checked: true`.
- No partial or live match statistics enter the grade.
- Confidence needs both appearances and minutes; three 90-minute appearances reach full confidence.
- The adjustment is neutral at a score of 50 and capped to ±5 points.
- Baseline and upside receive the capped adjustment; floor receives 60% of it.
- A missing, invalid, or temporarily unavailable feed produces a zero adjustment and does not block report generation.
- Existing H2H phase/freeze behavior remains separate. Recent evidence cannot rewrite a live Gameweek outcome because that Gameweek is ineligible until finalised.

## Shared-mode boundary

The official Draft and Standard FPL bootstrap feeds can assign different element IDs to the same player. Draft collection therefore resolves the Standard event-feed ID to the Draft element ID through the stable player `code` shared by both official bootstrap feeds. Unmapped event rows are ignored. Standard FPL keeps its native element IDs. Both collectors then pass the same evidence contract into `attach_intelligence`; mode-specific ownership, budgets, transfers, captaincy and H2H logic remain downstream and separate.

Every player intelligence object contains `recent_match_evidence` with the window score and grade, confidence, capped adjustment, minutes, starts, appearances, and compact per-Gameweek grades. Report-level metadata states whether the feed was available and which Gameweeks were used.

## Future discovery

Possible v2 work is fixture-level grades for double Gameweeks and calibration against completed-season outcomes. Third-party match ratings remain deferred because their definitions, licensing, availability and overlap with official BPS need separate evaluation.
