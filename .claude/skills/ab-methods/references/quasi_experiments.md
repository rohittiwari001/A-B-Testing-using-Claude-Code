# Quasi-experiments: DiD, synthetic control, interrupted time series

## When to use
Randomisation was not possible: regional launches, policy changes, marketing campaigns, pricing changes applied
to everyone. Say plainly that the evidence is weaker than a randomised test.

## Assumptions
- **Difference-in-differences**: without treatment, treated and control groups would have followed parallel
  trends; no spillover to controls; no anticipation; group composition stable.
- **Synthetic control**: a convex combination of untreated units reproduces the treated unit's pre-period path;
  enough pre-periods and donors.
- **Interrupted time series**: the pre-trend would have continued; nothing else changed at the same time.

## Step-by-step procedure
1. Plot `quasi.group_trends(df, outcome, treated_col, time_col, index_to_pre=True, post_col=...)` and look at the pre-period.
2. `quasi.parallel_trends_test(...)`: differential pre-trend (p < alpha means DiD is suspect).
3. `quasi.diff_in_diff(df, outcome, treated_col, post_col, unit_col, time_col, log=True)`: two-way fixed effects,
   SEs clustered by unit; `log=True` makes the effect relative.
4. Robustness: placebo launch date in the pre-period (should find nothing); drop one treated unit at a time;
   `quasi.synthetic_control(...)` with its placebo-in-space p-value.
5. Single treated series without controls: `quasi.interrupted_time_series(...)` (HAC SEs); weakest design.

## abkit function(s)
`quasi.diff_in_diff`, `quasi.parallel_trends_test`, `quasi.group_trends`, `quasi.synthetic_control`,
`quasi.interrupted_time_series`, `charts.did_trends`.

## How to interpret
- The DiD estimate is the effect on the treated units, relative to what their trend would have been.
- Few clusters (< 30): cluster-robust SEs are too optimistic; lean on placebo / permutation checks.
- A non-significant pre-trend test is absence of evidence, not proof of parallel trends.

## Common pitfalls
- Staggered adoption analysed with plain TWFE (biased with heterogeneous effects over time; use per-cohort 2x2 comparisons).
- Control units affected by the launch (spillover, cannibalisation).
- Choosing the control group after seeing which gives the best answer.

## How to present it
Chart: `did_trends` (indexed to pre-period = 100, launch line). Wording: "Launch regions grew +4.8% faster
than other regions after launch (DiD, 95% CI +2.9% to +6.7%); pre-launch trends were parallel (p = 0.4).
Because the launch was not randomised, treat this as strong but not conclusive evidence."
