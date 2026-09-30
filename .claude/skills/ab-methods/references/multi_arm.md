# Multi-arm tests (A/B/n)

## When to use
More than one treatment arm shares a control: price levels, several designs, dose-response.

## Assumptions
- Each arm randomised from the same population and period with a known intended split.
- The question is usually "which arms beat control?" (many-to-one), sometimes "which arm is best?".

## Step-by-step procedure
1. SRM against the intended k-way split (`validation.srm_check` with all arms in `expected`).
2. Each arm vs control: `frequentist.compare_to_control(df, metric, type, variant_col, control, correction="holm")`.
   For continuous metrics, `dunnett=True` gives Dunnett many-to-one p-values (accounts for the shared control,
   less conservative than Holm).
3. Heavy-tailed metrics (revenue): add `bootstrap_diff` per arm and report both.
4. Choosing a winner among arms: compare the top two directly (a pairwise test) or use Bayesian
   `posterior_prob_best`; do not pick the arm with the largest point estimate when CIs overlap heavily.
5. Size future tests with `n_comparisons = k` in the power functions.

## abkit function(s)
`frequentist.compare_to_control` (holm / bonferroni / benjamini-hochberg / dunnett), `bayesian.posterior_prob_best`,
`charts.lift_ci` (one row per arm), `charts.metric_by_variant` (up to 4 variants).

## How to interpret
- An arm is a winner only if its *adjusted* p-value is below alpha and the lift is practically meaningful.
- "Arm B beat control, arm C did not" does not mean B beat C.
- For pricing, revenue per user combines conversion and order value: report both components.

## Common pitfalls
- No correction across arms (with 4 arms, about a 19% chance of at least one false winner).
- Declaring the arm with the highest point estimate the winner.
- Unequal splits without adjusting the SRM expectation.

## How to present it
Chart: `lift_ci` with one row per arm (label "price_high vs control"), colour by significance after correction.
Wording: "price_high raises revenue per user by +5.1% (Holm-adjusted p = 0.01); price_low is not
distinguishable from control."
