# Bayesian readouts

## When to use
Stakeholders want "probability that B is better" and "expected loss" instead of p-values; decisions with
asymmetric costs; multi-arm "which is best" questions. It is not a fix for peeking or for tiny samples.

## Assumptions
- Same independence and unit rules as frequentist tests.
- Prior chosen *before* seeing results. Default `weakly_informative`: Beta(1, 1) for conversion (or a Beta
  centred on the historical baseline worth 20 pseudo-users); N(0, (10% of control mean)^2) on the difference
  for continuous metrics.
- Normal likelihood for means needs large n (hundreds or more per arm).

## Step-by-step procedure
1. Validate and check SRM first (srm.md).
2. Conversion: `bayesian.beta_binomial(x_c, n_c, x_t, n_t, prior=..., baseline=...)`.
   Continuous: `bayesian.normal_model(control_values, treatment_values, prior=...)`.
3. Read `probability` (P(treatment better in the good direction)), credible intervals (absolute `ci_*`,
   relative `rel_ci_*`) and `extra.expected_loss_treatment` (plus the relative version).
4. Decide with `bayesian.decide(result, threshold=settings.bayes_decision_threshold, max_loss_rel=...)`:
   ship if P(beat) >= threshold and expected loss is negligible; don't ship if P(beat) <= 1 - threshold; else extend.
5. Multi-arm: draw posteriors per arm and use `posterior_prob_best`.
6. Sensitivity: rerun with `prior="flat"`; if the decision flips, the data are too weak to decide.

## abkit function(s)
`bayesian.beta_binomial`, `bayesian.normal_model`, `bayesian.decide`, `bayesian.posterior_prob_best`.

## How to interpret
- P(beat control) = 0.97: given the model and the prior, a 97% probability that the true effect is positive.
- Expected loss: the average amount of metric lost by shipping if the treatment is actually worse. A tiny
  loss can justify shipping below the 0.95 threshold when the change is cheap.
- A 95% credible interval contains the true effect with 95% posterior probability.

## Common pitfalls
- "Bayesian means we can peek freely": repeated looks with a fixed threshold still inflate wrong decisions.
- Informative priors built from optimistic past winners (winner's curse): shrink them or stay weakly informative.
- Reporting P(beat) without the size of the effect.

## How to present it
Charts: `posterior_distributions`, `prob_to_beat_control` (threshold line).
Wording: "There is a 99.9% probability that treatment converts better than control; the most likely lift is
+3.2% (95% credible interval +1.2% to +5.2%)."
