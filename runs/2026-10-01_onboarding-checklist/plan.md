# Plan: Onboarding checklist test (v2, after validation BLOCK)

**Problem types:** srm_investigation

**Why the plan changed.** Validation found a sample ratio mismatch: p < 0.001, concentrated in Android from
2026-09-05. The user chose a blocked readout. No effect estimates will be produced (primary_test is skipped).

## Steps
| # | id | method | why |
|---|---|---|---|
| 1 | validate | validation.full_profile | done (verdict BLOCK) |
| 2 | srm | validation.srm_check | done (SRM detected) |
| 3 | srm_localise | validation.srm_by | quantify the loss by platform and by day, before vs after 2026-09-05 |
| 4 | summary | decision.build_blocked_summary | "Blocked: data issue" verdict with the SRM evidence and next steps |

## Charts
srm_bar (overall), srm_bar_android (Android only) - both in section validation

## Deck (short, about 5 slides)
exec_summary, validation, next_steps

## Report
exec_summary, business_question, design, data_validation, recommendation, appendix
