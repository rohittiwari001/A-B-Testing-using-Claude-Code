# Plan: Marketing ads vs PSA test

**Problem types:** post_test_readout, bayesian_readout, heterogeneous_effects (exploratory only)

**Plan note (2026-10-01).** After validation, the user corrected the intended split from 95/5 to **96/4**. The 95/5
check had failed (SRM). SRM is now checked against 96/4 and passes. The rest of the plan is unchanged.

**Approach.** A user-randomised test with an unbalanced intended split (96/4) and one row per user, so the analysis unit
matches the randomisation unit. Validate the data and test SRM against 96/4 first (see Risks). Once validation passes: test conversion with a two-proportion z-test
against the +5% threshold, add a beta-binomial Bayesian readout, and translate the lift into incremental conversions.
Exposure breakdowns come last and are labelled descriptive.

## Steps
| # | id | method | why |
|---|---|---|---|
| 1 | validate | validation.full_profile | schema, duplicates, impossible values, outliers in total ads |
| 2 | srm | validation.srm_check | intended split 96/4; the unbalanced design makes the split check essential |
| 3 | primary_test | frequentist.two_proportion_ztest | binary unit-level primary metric; one primary, no correction |
| 4 | bayesian | bayesian.beta_binomial | P(ads beat PSA) and expected loss, as requested; weakly informative prior |
| 5 | impact | custom.incremental_impact | incremental conversions per 1,000 users, total incremental conversions in the ad group, and the share of ad-group conversions attributable to the ads (with CIs). Not in abkit yet, so it is written in code/ and flagged for promotion |
| 6 | exposure_explore | segments.segment_effects | ad vs PSA lift by total-ads bucket and by most-ads day (BH-corrected), plus an interaction test; exploratory and non-causal (measured during the test) |
| 7 | summary | decision.build_summary | verdict vs the 5% threshold, plain-English impact statement |

## Assumptions to check
- SRM against 96/4 (the intended split, corrected by the user).
- At least 10 conversions and non-conversions per group (z-test normal approximation).
- `total ads` is heavy-tailed: report it, do not remove it.
- The PSA group is small (about 4%), so its conversion rate drives most of the uncertainty.

## Charts
srm_bar (validation); lift_ci, metric_by_variant, posterior_distributions, prob_to_beat_control (results);
segment_forest for ads-seen buckets (segments, labelled exploratory)

## Deck (stakeholder readout, about 14 slides)
exec_summary, setup, validation, results, segments, risks, next_steps, appendix

## Report
exec_summary, business_question, design, data_validation, methodology, results, segments, risks, recommendation, appendix

## Risks
- **SRM (resolved):** the originally stated 95/5 split did not match the data (23,524 PSA users vs about 29,405 expected).
  The user confirmed the intended split was 96/4, and the observed split matches it. The report will say that the
  split was confirmed after the first check failed. PSA user ids form one separate block, so the data owner should confirm assignment.
- Money impact: formula only (no value per conversion given).
- No dates: no novelty check.
