# Sample ratio mismatch (SRM)

## When to use
Always, before reading any effect. Also the whole analysis when the problem is "our split looks off".

## Assumptions
- The intended split is known (from the user, not from the data).
- Counts are of randomisation units (users), not events. For event-level data count distinct units.

## Step-by-step procedure
1. `validation.srm_check(df, variant_col, expected={...}, threshold=settings.srm_threshold, unit_col=...)`:
   chi-square goodness-of-fit of observed unit counts against the intended split.
2. If p < threshold (default 0.001): **block**. Do not report effects as findings.
3. Localise: `validation.srm_by(df, variant_col, by_col)` for the date column and each segment. A mismatch
   concentrated on some days or one platform points to the cause (full_profile does this automatically).
4. Check the usual causes:
   - assignment or bucketing bugs (hash salt, uneven ramp, variant-specific eligibility);
   - logging loss that differs by variant (crashes, slower pages, client-side events, ad blockers);
   - bot or fraud filtering that interacts with the treatment;
   - joins or filters applied after assignment ("users who reached checkout");
   - ramp changes or restarts without re-randomisation.
5. Present options to the user: (a) fix the pipeline and re-extract; (b) restrict to an unaffected
   window or segment, clearly labelled as a sensitivity analysis; (c) rerun the test. Never "reweight it away".

## abkit function(s)
`validation.srm_check`, `validation.srm_by`, `validation.full_profile` (SRM check with localisation),
`charts.srm_bar`.

## How to interpret
- SRM means the groups are no longer comparable by design: whatever removed units may be correlated with
  the outcome, so the effect estimate can be biased in either direction.
- The strict threshold (0.001) reflects that SRM is checked in every test; smaller mismatches are
  borderline and should be noted, not ignored.
- A tiny share difference (e.g. 50.4 / 49.6) can still be highly significant with large n. It is still SRM.

## Common pitfalls
- Testing event counts instead of unit counts.
- Testing against the observed split rather than the intended split.
- Continuing the analysis "with a caveat". The effect estimate is not trustworthy.
- Ignoring a mismatch that appears in one segment only (it still biases that segment and the total).

## How to present it
Chart: `srm_bar` (observed vs expected share, the short variant highlighted in negative).
Wording: "Treatment has 7% fewer users than a 50/50 split implies (chi-square p < 0.001); the shortfall is
concentrated in Android users from 5 September. Results are withheld until the logging issue is fixed."
