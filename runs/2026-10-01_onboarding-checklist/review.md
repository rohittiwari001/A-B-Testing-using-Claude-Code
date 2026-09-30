# Review: 2026-10-01_onboarding-checklist (round 1)
Verdict: PASS

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| 1 | note | Handling is correct: SRM blocked the analysis and no activation estimate was produced or reported. | results.json has no primary_test step; summary verdict "blocked" | none |
| 2 | note | The loss is specific to Android from 2026-09-05; iOS + Web are balanced. An iOS + Web-only readout would change the population, and the caveat says so. | srm_localise: Android p < 0.001, iOS + Web p = 0.323 | none |
| 3 | note | The covariate-balance warning (platform mix differs by variant) is a symptom of the same loss, not a separate issue. | data_profile.md covariate balance WARN | none |

## Checklist
1. SRM - ok (detected, blocked, user decision recorded in intake.md).
2-6. Tests / units / corrections / significance wording - not applicable (no effect estimated).
7. Peeking - not applicable.
8. Novelty - not applicable.
9. Simpson's paradox - n/a; platform mix imbalance explained by the SRM.
10. Guardrails - none planned.
11. Conclusion follows - ok ("Blocked: data issue" with fix-and-rerun next steps).
12. Traceability - ok (counts recomputed from data/ match results.json; all scripts present).
13. Failed assumptions - the design assumption of a 50/50 split fails; that is the finding.
