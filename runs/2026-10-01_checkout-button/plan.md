# Plan: Single-button checkout test

**Problem types:** post_test_readout, guardrail_check, heterogeneous_effects, novelty_check

**Approach.** A fixed-horizon, user-randomised 50/50 test with one row per user, so the randomisation unit and the
analysis unit match and standard unit-level tests apply. Validate the data and check SRM first. Test the primary
metric (conversion) with a two-proportion z-test against the +2% practical threshold. Test the revenue guardrail for
non-inferiority (1% margin), with a bootstrap sensitivity check because revenue is heavy-tailed. Estimate
platform effects (pre-specified, BH-corrected) with an interaction test and a Simpson's check. Check stability over
the 14 days because the treatment is a visible UI change.

## Steps
| # | id | method | why |
|---|---|---|---|
| 1 | validate | validation.full_profile | schema, duplicates, contamination, dates, outliers before any estimate |
| 2 | srm | validation.srm_check | 50/50 intended split; SRM would invalidate the comparison |
| 3 | primary_test | frequentist.two_proportion_ztest | binary unit-level primary metric; no correction (single primary) |
| 4 | guardrail_revenue | frequentist.noninferiority_test | revenue per user must not fall more than 1% (one-sided, 90% CI) |
| 5 | revenue_sensitivity | frequentist.bootstrap_diff | heavy-tailed revenue: confirm the Welch-based CI with a bootstrap |
| 6 | segments_platform | segments.segment_effects (+ interaction_test, simpsons_check) | platform pre-specified; BH across segments; the interaction test decides whether effects differ |
| 7 | time_trends | time_effects.cumulative_effects (+ effects_by, trend_test) | visible UI change: rule out a novelty spike |
| 8 | summary | decision.build_summary | verdict against the 2% threshold and guardrail status |

## Assumptions to check
- One row per user, no user in both variants (validation).
- SRM p >= 0.001 against 50/50.
- Normal approximation: at least 10 successes and failures per group (z-test assumption check).
- Revenue tail: bootstrap and Welch CIs agree.
- Platform mix balanced across variants (Simpson's paradox risk).

## Charts
srm_bar (validation), lift_ci, metric_by_variant (results), cumulative_daily, daily_lift (time),
guardrail_scorecard (guardrails), segment_forest (segments), distribution_compare (appendix).

## Deck (standard, about 16 slides)
exec_summary, setup, validation, results, guardrails, segments, time, risks, next_steps, appendix

## Report
exec_summary, business_question, design, data_validation, methodology, results, guardrails, segments, risks,
recommendation, appendix

## Open questions for the user
None. Country is excluded as agreed.
