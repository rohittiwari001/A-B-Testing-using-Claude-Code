# Intake: Home feed redesign (CUPED re-analysis)

## Q&A transcript (dry run: questions asked in one batch, answers given by the user)

Already answered: variants (control / treatment), 50/50 by user, one row per user, primary metric minutes per
user during the 14-day test, pre-period covariate `pre_minutes` (14 days before the test), segment column
signup_country. The user says the naive t-test was borderline.

Asked:
1. **Pre-period definition.** Is `pre_minutes` measured strictly before each user's assignment, with the same
   definition as `minutes`? [yes] -> "Yes, same event, the 14 days before the test started."
2. **Users without history.** Do new users have pre_minutes = 0, or are they missing? [missing -> mean-imputed] ->
   "Every user in the file existed before the test; no missing values."
3. **Pre-registration.** Was CUPED planned before you saw the borderline result? [no] -> "No, we only thought of it
   after the t-test came out at p = 0.08." *(Recorded as a risk: the adjustment was chosen after seeing results.)*
4. **Practical threshold.** Smallest lift in minutes per user worth shipping? [1% relative] -> "1% is enough; the
   feed is cheap to maintain."
5. **Guardrails.** Anything that must not drop? [none] -> "No guardrails for this one."
6. **Segments.** signup_country for decisions? [no] -> "No."
7. **Statistical defaults** (table shown) -> "Keep them."
8. **Depth.** [standard] -> "Standard, but explain CUPED simply for the product team."

## Business question
Does the redesigned home feed increase time spent in the app?

## Decision to be made
Ship / don't ship the redesigned feed.

## Hypothesis
The redesigned feed increases minutes per user.

## Design
- Variants and intended split: control / treatment, 50/50
- Randomisation unit / analysis unit: user / user
- Dates: 14-day test (no date column in the file)
- Pre-period data: pre_minutes, 14 days before the test, same definition

## Metrics
| name | role | type | direction | notes |
|---|---|---|---|---|
| minutes | primary | continuous | increase | practical threshold +1% relative; CUPED with pre_minutes |

## Segments (pre-specified)
None.

## Known incidents
None.

## Statistical settings
Defaults kept.

## Deliverable depth
Standard; explain CUPED in plain words.

## Risks flagged at intake
- CUPED was chosen after the naive test was seen (p = 0.08). Both results will be reported side by side, and the
  report will say the adjustment was not pre-registered. CUPED is a standard, pre-specifiable method whose
  covariate is fixed by design (the same metric pre-period), which limits forking paths; a regression-adjustment
  sensitivity check is also planned.
- No date column: novelty cannot be assessed.

## Decision on review blocker 1 (2026-10-01)
Claude explained that the ship decision depends on CUPED (p = 0.042) while the unadjusted test was not
significant (p = 0.081), and that CUPED was chosen after seeing that result. Options: (a) accept CUPED as primary
and state the post-hoc choice prominently; (b) call the result inconclusive and rerun with CUPED pre-registered.
**User chose (a)**: "CUPED on same-metric pre-period is our standard from now on. Use it, but put the caveat
first, and recommend pre-registering it."
