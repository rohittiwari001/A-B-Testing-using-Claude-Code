# Review: 2026-10-01_checkout-button (round 1)
Verdict: FIXES NEEDED

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| 1 | fix | The summary does not say that the CI's lower bound is below the 2% practical threshold. The point estimate clears the threshold; the whole interval does not. | primary_test rel_lift +3.2%, CI [+1.2%, +5.2%]; practical threshold 2% (intake) | Add a caveat that the true lift could be as low as the CI lower bound, below the threshold; keep the verdict (the recommendation rule uses the point estimate). |
| 2 | note | iOS is significant after BH and Android / Web are not, but the interaction test is not significant. The summary words this correctly. | segments_platform: interaction p = 0.168 | None. Keep the single-rollout recommendation. |
| 3 | note | The revenue guardrail passes with the NI test (90% CI); the two-sided Welch and bootstrap 95% CIs include 0 but stay above the -1% margin. | guardrail_revenue p = 0.005; revenue_sensitivity CI [-0.3%, +4.7%] | None. Already in caveats. |

## Checklist
1. SRM - ok (p = 0.196 vs 0.001, intended 50/50).
2. Test matches metric type - ok (z-test for binary conversion; NI and Welch/bootstrap for revenue).
3. Unit of analysis - ok (one row per user = randomisation unit; no contamination).
4. Multiple-testing correction - ok (primary: none; segments: BH as planned).
5. Practical vs statistical significance - finding 1.
6. Inconclusive wording - ok (no null result is described as "no effect").
7. Peeking - ok (ran to the planned 14 days, per intake).
8. Novelty - ok (trend test stable, p = 0.794).
9. Simpson's paradox - ok (not flagged; segment mix balanced).
10. Guardrails - ok (revenue pass).
11. Conclusion follows - ok (`decision.recommend` re-derived: ship).
12. Traceability - ok (all step scripts exist; conversion rates and revenue lift recomputed from data/ and match results.json).
13. Failed assumptions - none recorded.

# Review: 2026-10-01_checkout-button (round 2)
Verdict: PASS

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| 1 | resolved | Caveat added: the CI lower bound is below the 2% practical threshold. | results.json summary.caveats[0], code/20_analysis_summary.py | none |

All 13 checklist items ok. The verdict stays "Ship" with the threshold caveat.

Addendum (round 2): caveat wording shortened for the deck word limit (deck-builder request); numbers and verdict unchanged. Re-checked: ok.

# Review: 2026-10-01_checkout-button (round 3, follow-up "rerun with alpha 0.01")
Verdict: PASS

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| 1 | note | At alpha 0.01 the primary result stays significant (p = 0.001) and its 99% CI [+0.6%, +5.8%] is wider; the lower bound is further below the 2% threshold, and the caveat reflects it. | primary_test | none |
| 2 | note | The revenue guardrail still passes non-inferiority at one-sided alpha 0.01 (98% CI). iOS stays significant after BH (adjusted p = 0.002). | guardrail_revenue, segments_platform | none |
| 3 | resolved | Chart subtitles had hard-coded "95% CI" / "90% CI"; they now derive the level from alpha (30_charts_*.py). | code diff | none |

Override recorded in state.json (alpha 0.05 -> 0.01). Verdict unchanged: Ship.
