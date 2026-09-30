# Frequentist tests

## When to use
The default readout for a randomised test with a fixed horizon (analysed once, at the planned end).

## Assumptions
- Independent units at the randomisation level; one row per unit (aggregate first otherwise).
- Sample size fixed in advance, no early stopping on peeks (otherwise see sequential_testing.md).
- Large-sample normality of the *mean* (CLT) for z / Welch; very skewed metrics need large n or a bootstrap check.

## Step-by-step procedure
1. Aggregate to one row per randomisation unit (`io.to_unit_level`).
2. Choose the test by metric type:
   - binary -> `two_proportion_ztest` (Fisher exact if any cell has fewer than 10);
   - continuous / count -> `welch_ttest` (never Student's t with pooled variance);
   - heavy tails (max > 10x p99 or |skew| > 5) -> add `bootstrap_diff` and a winsorised sensitivity run; report both;
   - "did the distribution shift" only -> `mann_whitney` (never for totals or means);
   - categorical outcome with more than 2 levels -> `chi_square_test`.
3. `frequentist.compare(df, metric, type, variant_col, control, treatment, alpha, alternative, role)` applies the default.
4. The StatResult records estimate, absolute and relative lift with CI, p-value, n and assumptions checked.
5. Apply the planned correction to secondary metrics (multiple_testing.md).

## abkit function(s)
`frequentist.compare`, `two_proportion_ztest`, `welch_ttest`, `bootstrap_diff`, `mann_whitney`,
`chi_square_test`, `noninferiority_test`, `compare_to_control`, `alternative_for`.

## How to interpret
- p-value: probability of a difference at least this large if there were truly no effect. It is not the
  probability that the treatment works.
- The CI is the range of effects compatible with the data; judge it against the practical threshold.
- Relative-lift CI uses the delta method: Var(T/C - 1) ~ se_T^2 / C^2 + T^2 se_C^2 / C^4.

## Common pitfalls
- Row-level tests on session or event data (inflated significance): see ratio_metrics_delta_method.md.
- Mann-Whitney used to claim "revenue went up".
- Removing outliers in one direction only, or after looking at the results.
- "No effect" declared from p > 0.05 (see interpretation_and_decisions.md).
- A one-sided test chosen after seeing the direction of the effect.

## How to present it
Charts: `lift_ci` (all metrics), `metric_by_variant` (primary levels).
Wording: "Treatment lifts conversion by +3.2% (95% CI +1.2% to +5.2%, p = 0.001)."
