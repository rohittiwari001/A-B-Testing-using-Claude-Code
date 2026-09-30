# Ratio metrics, the delta method and clustered errors

## When to use
The analysis unit is finer than the randomisation unit: users randomised but the metric is per session,
pageview, order or click (CTR, revenue per order, pages per session); or clusters (stores, classrooms) randomised.

## Assumptions
- Randomisation units are independent; rows within a unit are not.
- Enough units per arm (hundreds+) for the normal approximation of a ratio of means.
- The metric is a ratio of sums: sum(numerator) / sum(denominator) across units.

## Step-by-step procedure
1. Identify numerator and denominator (CTR = clicks / pageviews) and the randomisation unit (user_id).
2. `ratio_metrics.delta_method_ratio(df, numerator, denominator, unit_col, variant_col, control, treatment)`:
   aggregates to unit-level sums X, Y, then Var(R) = [var X / mu_Y^2 - 2 mu_X cov(X,Y) / mu_Y^3 + mu_X^2 var Y / mu_Y^4] / n.
3. Cross-check with `ratio_metrics.cluster_robust_test(df, row_ratio, unit_col, ..., weights=denominator)`
   (WLS with cluster-robust SEs gives the same estimate and a nearly identical SE).
4. Report `extra.design_effect` (variance inflation that a naive row-level test ignores) and the naive p-value,
   so readers see why the naive answer was wrong.

## abkit function(s)
`ratio_metrics.delta_method_ratio`, `ratio_metrics.cluster_robust_test`, `io.to_unit_level`.

## How to interpret
- Design effect 2 means the naive SE is too small by a factor sqrt(2); naive p-values are far too small.
- The ratio of sums weights heavy users more than the mean of per-user ratios; say which one you report.
  Per-user mean ratio (average user CTR) is a different metric: compute per user, then Welch.

## Common pitfalls
- Treating sessions as independent (the most common source of false wins).
- Averaging per-session ratios (weights sessions, not pageviews) without saying so.
- Denominators that the treatment changes (e.g. treatment increases sessions): the ratio can move for the
  wrong reason. Always report numerator and denominator per unit alongside the ratio.

## How to present it
Charts: `lift_ci` with the delta-method CI; optionally a two-row lift_ci showing naive vs correct CI width.
Wording: "CTR rose +3.0% (95% CI +0.6% to +5.4%, delta method at user level). A session-level test would
have overstated certainty by a factor of 2.1 in variance."
