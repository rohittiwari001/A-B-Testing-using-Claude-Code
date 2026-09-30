# Heterogeneous treatment effects (segments)

## When to use
Pre-specified segments (platform, country, new vs returning) where the effect could plausibly differ, or
where rollout decisions are made per segment.

## Assumptions
- Segments are defined by pre-treatment attributes (never by something the treatment can change).
- Enough units per segment (the segment test has far less power than the overall test).
- Segments listed in the plan are confirmatory; everything else is exploratory.

## Step-by-step procedure
1. `segments.segment_effects(df, metric, type, segment_col, variant_col, control, treatment, correction="benjamini-hochberg")`
   returns an "All" row plus one row per segment, corrected across segments.
2. `segments.interaction_test(...)`: joint Wald test that the effect is equal across segments. Only this test
   supports the claim "the effect differs by segment".
3. `segments.simpsons_check(...)`: compares pooled and segment-standardised effects and the segment mix by arm.
4. Check validation `covariate balance`: a segment mix that differs by arm points to an assignment or logging issue.

## abkit function(s)
`segments.segment_effects`, `segments.interaction_test`, `segments.simpsons_check`, `charts.segment_forest`.

## How to interpret
- A significant effect in segment A and a non-significant one in B is **not** evidence that A and B differ.
- Interaction test p < alpha: effects differ; describe the pattern and consider segment-specific rollout.
- Interaction test not significant: report segment results as consistent with a common effect.
- Simpson's paradox: pooled and within-segment directions disagree because the segment mix differs by arm.

## Common pitfalls
- Post-hoc fishing: slicing by many segments and reporting the one that "won". With 20 cuts, one is
  significant at 5% by chance. Label exploratory findings and require confirmation in a new test.
- Segments defined by post-treatment behaviour ("users who used the new feature").
- Tiny segments with huge CIs presented as findings.

## How to present it
Chart: `segment_forest` ("All" row on top, filled markers only if significant after correction).
Wording: "The lift is largest on iOS (+5.2%), but the interaction test finds no evidence that platforms
differ (p = 0.17); we recommend a single rollout decision."
