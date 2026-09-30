# Guardrails and non-inferiority

## When to use
Metrics that must not get worse (revenue per user, latency, errors, refunds, unsubscribes) while the primary
metric is optimised.

## Assumptions
- A non-inferiority margin agreed in advance (default 1% relative, `settings.noninferiority_margin_relative`).
- Direction defined per guardrail: `no_decrease` (bigger is better) or `no_increase` (smaller is better).

## Step-by-step procedure
1. For each guardrail: `frequentist.noninferiority_test(control_values, treatment_values, margin_rel, direction)`
   (or `counts=(x_c, n_c, x_t, n_t)` for binary guardrails).
   H0: treatment is worse than control by more than the margin. One-sided at alpha; CI at 1 - 2 alpha (90%).
2. Status in `extra.status`:
   - **pass**: non-inferiority shown (worse-than-margin ruled out);
   - **breach**: the whole CI lies beyond the margin in the harmful direction;
   - **inconclusive**: cannot rule out harm beyond the margin (usually underpowered).
3. Guardrails are a family: report all; a breach feeds the decision (interpretation_and_decisions.md).

## abkit function(s)
`frequentist.noninferiority_test`, `decision.recommend` (uses statuses), `charts.guardrail_scorecard`.

## How to interpret
- "Pass" is a positive statement: harm larger than the margin is ruled out.
- "Inconclusive" is not a pass: say what harm cannot be excluded (the CI bound).
- A significant but tiny decrease inside the margin is still a pass by design; mention it.

## Common pitfalls
- Using a standard two-sided test and calling "not significant" a pass.
- Margins set after seeing results.
- Too many guardrails with no margin discipline (someone will always "fail").

## How to present it
Chart: `guardrail_scorecard` (PASS / BREACH / INCONCLUSIVE with change, CI and margin).
Wording: "Revenue per user is non-inferior: the change is +2.2% (90% CI +0.1% to +4.3%), well inside the -1% margin."
