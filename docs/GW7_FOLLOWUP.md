# GW7 follow-up — 20 October 2026

The 04:33 UTC 17 October pre-deadline snapshot at commit `c45c194`
retains the actual selection inputs. These are historical recorded values,
not predictions reconstructed from GW7 results.

| Player | Start Score | Expected minutes | Fixture score | Sample confidence | Evidence factor | Projected points |
|---|---:|---:|---:|---:|---:|---:|
| Brobbey | 79.4 | 74.1 | 60 | 77.8 | 0.978 | 3.8 |
| Kostoulas | 79.2 | 73.2 | 80 | 21.2 | 0.921 | 7.2 |
| Hall | 84.5 | 89.8 | 60 | 72.1 | 0.972 | 4.0 |
| Vuskovic | 78.8 | 77.8 | 80 | 11.7 | 0.912 | 6.4 |

All four had availability 100 in the recorded model. Brobbey also had an
official next-round chance of 100 and empty news. Start Score optimizes its
own weighted inputs rather than projected points. The evidence discount
reverses the forward ordering: before that discount Brobbey scores about
81.2 and Kostoulas 86.0. Hall's expected minutes and stronger floor combine
with higher confidence to outweigh Vuskovic's easier fixture. The forward
margin is only 0.2, already within the existing close-call threshold.

Do not change the weights based on this round. Only two valid paired rounds
exist, and only GW7 has differing XIs. Continue the prospective challenger
experiment, preserving all alternatives' score components with each new
deadline pair. Compare future differing selections and minutes errors;
keep raw XI points separate from official autosub-adjusted totals.

The 13:35 snapshot ended recent evidence at GW6; the 20:01 snapshot at
`b674e89` includes GW7. McGinn now has one observed round (zero player-point
gain), and Vuskovic has two (+16 combined player points). Both sections
consume the same Standard FPL feed, gated on finished AND data_checked.
The earlier report did not retain those upstream flags, so the precise
timing of their change cannot be proved retrospectively. No persistent
collector failure was reproduced. Add explicit freshness diagnostics to
distinguish awaiting final checks from collection failures on future runs,
without weakening the finalization gate or altering frozen forecasts.
