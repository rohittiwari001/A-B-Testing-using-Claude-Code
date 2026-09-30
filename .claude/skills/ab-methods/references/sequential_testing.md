# Sequential testing (peeking, alpha spending, mSPRT)

## When to use
Results were (or will be) looked at repeatedly with the option to stop early; monitoring dashboards;
tests with a planned early-stopping rule.

## Assumptions
- Group-sequential: number and timing of looks planned in advance (the spending approach tolerates some
  deviation in timing); information fraction = n so far / planned n.
- mSPRT: data arrive over time; a mixing scale tau reflecting plausible effect sizes is set in advance.

## Step-by-step procedure
1. Quantify the problem if peeking already happened: `sequential.peeking_simulation(n_looks)` (A/A false-positive
   rate with naive repeated testing, typically 15-30% instead of 5%).
2. Planned looks: `sequential.boundaries(info_fractions, alpha, kind="obrien-fleming" | "pocock")` gives z boundaries
   (Lan-DeMets spending, exact recursive integration; matches gsDesign / rpact).
   - O'Brien-Fleming: very strict early, close to the fixed-horizon value at the end (default).
   - Pocock: equal-ish boundaries, easier early stops, higher final bar.
3. At each look compute z (e.g. from `frequentist.compare(...).extra["z"]`) and call
   `sequential.group_sequential_test(z_values, info_fractions, planned_fractions=...)`.
4. Continuous monitoring: `sequential.msprt_path(df, metric, date_col, variant_col, control, treatment, alpha, tau_rel)`
   gives always-valid p-values and CIs per day (running minimum of 1/LR; running intersection of CIs).
5. Report the stopping look, the adjusted evidence, and that point estimates at an early stop are biased upward.

## abkit function(s)
`sequential.spending`, `sequential.boundaries`, `sequential.group_sequential_test`, `sequential.msprt`,
`sequential.msprt_path`, `sequential.peeking_simulation`, `charts.sequential_boundaries`.

## How to interpret
- Crossing a boundary at look k controls the overall false-positive rate at alpha across all looks.
- Always-valid p < alpha at any time is a valid stop, however often you checked.
- Not crossing: continue to the next planned look (or stop for futility if planned - not implemented by default).

## Common pitfalls
- Using fixed-horizon p-values after peeking (inflated false positives).
- Adding unplanned looks with O'Brien-Fleming bounds computed for the original schedule (recompute with the
  actual information fractions - allowed by the spending approach).
- Reporting the early-stopped effect as the long-run effect (it is biased upward, "winner's curse").
- tau in mSPRT tuned after seeing data.

## How to present it
Chart: `sequential_boundaries` with the observed z path.
Wording: "The effect crossed the O'Brien-Fleming boundary at the third of four planned looks (z = 2.90 vs
boundary 2.36), so stopping early keeps the false-positive rate at 5%."
