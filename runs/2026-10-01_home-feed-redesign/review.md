# Review: 2026-10-01_home-feed-redesign (round 1)
Verdict: BLOCKED (1 blocker, 1 fix)

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| 1 | blocker | The recommendation depends on an adjustment chosen after the result was seen. Unadjusted: p = 0.081, not significant. CUPED: p = 0.042, just below alpha. Choosing the analysis after seeing results inflates the false-positive rate, so this could change the conclusion. | intake.md "Risks flagged at intake"; naive_test vs cuped_test | User decision needed: accept CUPED as the primary analysis (standard method, covariate fixed by design, regression adjustment agrees) and say so prominently; or treat the result as inconclusive and confirm with a pre-registered rerun. |
| 2 | fix | The lift moves from +2.1% (unadjusted) to +1.7% (CUPED), but the summary does not explain why. Treatment users had slightly higher pre-period minutes by chance (64.0 vs 63.6), and CUPED removes that head start. | means of pre_minutes by variant; theta = 0.737 | Add a caveat explaining the shift. |
| 3 | note | The CUPED CI lower bound is at +0.0%, so the lift could be close to zero and is only marginally above the 1% threshold. The summary's threshold caveat covers this. | cuped_test CI [+0.0%, +3.3%] | none |

## Checklist
1. SRM - ok (p = 0.166).
2. Test matches metric type - ok (Welch + bootstrap for continuous; CUPED / regression adjustment).
3. Unit of analysis - ok (one row per user).
4. Corrections - ok (single primary; sensitivity analyses are not a family).
5. Practical vs statistical - note 3.
6. Inconclusive wording - ok.
7. Peeking / forking paths - finding 1.
8. Novelty - cannot be checked (no dates), stated as a caveat.
9. Simpson's paradox - n/a (no segments).
10. Guardrails - none planned.
11. Conclusion follows - it follows the CUPED result, which is conditional on finding 1.
12. Traceability - ok (all scripts present; CUPED re-derived: 1.34 - 0.737 x 0.365 = 1.07 minutes, about +1.7%).
13. Failed assumptions - none; covariate balance passed (p > 0.001).

# Review: 2026-10-01_home-feed-redesign (round 2)
Verdict: PASS

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| 1 | resolved by user decision | CUPED accepted as primary; the post-hoc choice is the first caveat and pre-registration is a next step. | intake.md "Decision on review blocker 1"; summary.caveats[0] | none |
| 2 | resolved | The caveat explaining the +2.1% to +1.7% shift has been added. | summary.caveats | none |

Addendum (round 2): caveat wording shortened for the deck word limit; numbers and verdict unchanged. Re-checked: ok.
