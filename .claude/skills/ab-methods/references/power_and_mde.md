# Power, sample size and MDE

## When to use
Before a test (how many users, how many days?), after an inconclusive test (could it ever have detected
the effect we care about?), and when choosing between designs (number of arms, split, CUPED).

## Assumptions
- Normal approximation for the difference in means / proportions (fine for n in the hundreds and up).
- Units independent; variance estimated from comparable historical data: same unit, same metric
  definition, same population, same window length.
- The MDE is a *business* decision: the smallest effect worth acting on, not the effect you hope for.

## Step-by-step procedure
1. Baseline: conversion rate p, or mean and SD, from historical data at the randomisation unit
   (`power.variance_from_history`). Per-user metrics grow with window length, so match the test window.
2. Agree alpha, sidedness and power (defaults 0.05, two-sided, 0.8) and candidate relative MDEs (e.g. 1, 2, 3, 5%).
3. Sample size per variant: `power.sample_size_proportions(p, mde)` or `power.sample_size_means(sd, mde_abs)`.
   With k treatment arms pass `n_comparisons=k` (Bonferroni split of alpha).
4. Runtime: `power.runtime_days(n, daily_eligible_units, n_variants)` rounds up to full weeks, minimum 7 days.
5. Table and curves: `power.sample_size_table(...)`, `power.power_curve(...)`.
6. For an inconclusive past test: `power.mde_proportions(p, n_observed)` gives the effect it could have detected.
7. If CUPED will be used, the required n shrinks by the factor (1 - rho^2), rho = pre/post correlation.

## abkit function(s)
`power.sample_size_proportions`, `power.sample_size_means`, `power.mde_proportions`, `power.mde_means`,
`power.power_proportions`, `power.power_means`, `power.power_curve`, `power.sample_size_table`,
`power.runtime_days`, `power.variance_from_history`, `power.simulate_power` (validation by simulation).

## How to interpret
- "n per variant" is the number of *randomisation units* per arm at the end of the test.
- 80% power: if the true effect equals the MDE, the test detects it 4 times in 5. Smaller effects are often missed.
- Halving the MDE roughly quadruples the sample size.

## Common pitfalls
- Session-level variance for a user-randomised test (understates variance, overstates power).
- MDE set to the hoped-for effect ("we expect +10%"), producing underpowered tests.
- Forgetting extra arms or unequal splits (a 90/10 split needs far more total traffic).
- Post-hoc "observed power": it is a function of the p-value and adds nothing. Report the MDE instead.
- Novelty: a one-week test sized on the week-one effect can miss the smaller long-run effect.

## How to present it
Charts: `sample_size_vs_mde` (days labelled) and/or `power_curve` with the available n marked.
Wording: "To detect a +3% lift in conversion with 80% power we need about 34,100 users per variant: 14 days at current traffic."
