# CUPED and regression adjustment

## When to use
A pre-experiment measurement of the metric (or a strongly correlated covariate) exists for each unit, and
you want tighter CIs from the same data: borderline results, small effects, expensive traffic.

## Assumptions
- The covariate is measured **before** assignment, so the treatment cannot affect it.
- Covariate is balanced across variants (it will be, under proper randomisation; check it).
- Linear relationship is enough for most of the gain; units with no pre-period (new users) get the mean.

## Step-by-step procedure
1. Check balance of the covariate between arms (validation `pre-period data`; `cuped` also records a balance check).
2. `variance_reduction.cuped(df, metric, covariate, variant_col, control, treatment, alpha)`:
   theta = cov(Y, X) / var(X) pooled across arms; Y_adj = Y - theta (X - mean X); Welch test on Y_adj.
3. Several covariates or categorical ones: `variance_reduction.regression_adjustment(df, metric, [covariates], ...)`
   (Lin 2013: treatment x centred covariates, HC2 robust SEs).
4. Always report the unadjusted result next to the adjusted one (`extra.unadjusted`), plus
   `extra.correlation`, `extra.variance_reduction`, and CI widths.
5. The *decision* uses the adjusted result if CUPED was pre-planned; if added after seeing results, say so.

## abkit function(s)
`variance_reduction.cuped`, `variance_reduction.regression_adjustment`, `charts.cuped_variance_reduction`.

## How to interpret
- Variance reduction ~ rho^2: rho = 0.7 removes about half the variance, like doubling the sample.
- The point estimate moves a little (chance imbalance in the covariate is corrected); a large move signals a
  covariate imbalance worth investigating.
- `effective_sample_multiplier` = 1 / (1 - variance reduction).

## Common pitfalls
- Using a covariate measured during the test (post-treatment bias).
- Choosing among many covariates or adjusted / unadjusted *after* seeing p-values (forking paths).
- Forgetting that relative lift should still be reported against the unadjusted control mean.
- Dropping units with missing pre-period data (changes the population; fill with the mean instead).

## How to present it
Chart: `cuped_variance_reduction` (CI width before vs after) and `lift_ci` with both rows.
Wording: "Using pre-period minutes narrows the confidence interval by 31%; the lift is +2.1% (95% CI +0.8%
to +3.3%), significant after adjustment (p = 0.001) where the unadjusted test was borderline (p = 0.08)."
