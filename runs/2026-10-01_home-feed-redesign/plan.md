# Plan: Home feed redesign (CUPED re-analysis)

**Problem types:** cuped_reanalysis, post_test_readout

**Approach.** Validate the data, including covariate balance and the pre/post correlation. Report the naive Welch
test (the result already seen) next to a CUPED-adjusted Welch test that uses pre_minutes. Add a Lin
regression-adjustment check. Heavy-tailed minutes get a bootstrap check on the naive estimate. The decision uses
CUPED, with the post-hoc choice stated as a caveat.

## Steps
| # | id | method | why |
|---|---|---|---|
| 1 | validate | validation.full_profile | includes pre-period availability, correlation and balance |
| 2 | srm | validation.srm_check | intended 50/50 |
| 3 | naive_test | frequentist.welch_ttest | the unadjusted result (borderline, seen before CUPED was chosen) |
| 4 | cuped_test | variance_reduction.cuped | pre_minutes, same metric pre-period; variance reduction ~ corr^2 |
| 5 | regression_check | variance_reduction.regression_adjustment | sensitivity: Lin (2013) adjustment, HC2 SEs |
| 6 | summary | decision.build_summary | verdict on the CUPED estimate vs the 1% threshold |

## Assumptions to check
- pre_minutes balanced across variants (it is pre-treatment).
- CUPED and regression adjustment agree.
- Minutes are right-skewed: CLT is fine at n ~ 10,000 per arm; the bootstrap confirms.

## Charts
lift_ci (naive vs CUPED rows), cuped_variance_reduction, metric_by_variant (results), distribution_compare (appendix)

## Deck (standard, about 12 slides)
exec_summary, setup, validation, results, risks, next_steps, appendix

## Report
exec_summary, business_question, design, data_validation, methodology, results, risks, recommendation, appendix
