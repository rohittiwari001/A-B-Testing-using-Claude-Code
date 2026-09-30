# Multiple testing: Bonferroni, Holm, Benjamini-Hochberg

## When to use
More than one hypothesis contributes to the decision: several secondary metrics, several arms,
segments, several looks (see sequential_testing.md for looks).

## Assumptions
- The family of tests is defined *before* results are seen (the plan lists it).
- Bonferroni and Holm are valid under any dependence; BH assumes independence or positive dependence
  (reasonable for metrics and segments of one experiment).

## Step-by-step procedure
1. Define families from the plan: primary (one metric, no correction), secondary metrics (Holm by default),
   segments (Benjamini-Hochberg by default), arms vs control (Holm or Dunnett, multi_arm.md).
2. Run the tests, then `multiple_testing.apply_correction(results, method, alpha)` per family.
   This sets `p_value_adjusted`, `correction` and `significant` on each result.
3. Report both raw and adjusted p-values; claims use adjusted ones.

## abkit function(s)
`multiple_testing.adjust_pvalues`, `multiple_testing.apply_correction`; also used inside
`segments.segment_effects` and `frequentist.compare_to_control`.

## How to interpret
- Bonferroni: p x m. Simple, conservative. Use for a small, critical family or for sample sizing.
- Holm: step-down Bonferroni; controls the family-wise error rate (FWER), always at least as powerful. Default for secondary metrics.
- Benjamini-Hochberg: controls the false discovery rate (expected share of false findings among the
  "significant" ones). Default for many segments / exploratory cuts.
- CIs: adjusted p-values do not adjust the CI; for FWER-level intervals use alpha / m (Bonferroni CIs) when needed.

## Common pitfalls
- Correcting the primary metric together with dozens of exploratory metrics (kills power where it matters).
- Not correcting segments, then headlining the one segment that "won".
- Choosing the correction after seeing which one keeps a result significant.

## How to present it
Tables: raw p, adjusted p, correction name in the note. Forest plots: filled markers only when significant after correction.
Wording: "Of 6 secondary metrics, 2 remain significant after Holm correction."
