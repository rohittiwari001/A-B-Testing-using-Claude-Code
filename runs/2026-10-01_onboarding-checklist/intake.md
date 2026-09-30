# Intake: Onboarding checklist test

## Q&A transcript (dry run: questions asked in one batch, answers given by the user)

Already answered: variants (control / treatment), intended 50/50 split by user, one row per user, primary metric
activation (`converted`, activated within 7 days), dates 2026-09-01 to 2026-09-14, platform column.

Noticed in the data header (not yet a finding): about 20.8k control vs 18.1k treatment users. Validation will
test this formally, so the question below asks how exposure is logged.

Asked:
1. **Practical threshold.** Smallest activation lift worth shipping? [3% relative] -> "3%."
2. **Exposure logging.** How is a user recorded as exposed: server-side at assignment, or a client event when the
   checklist renders? [client event] -> "Client event from the app when onboarding starts."
3. **Changes during the test.** Any app releases, SDK changes or incidents between 1 and 14 Sep? [none] ->
   "There was an Android release around 4-5 Sep, not related to the test as far as I know."
4. **Guardrails.** Any guardrail metric? [none] -> "No."
5. **Segments.** Platform pre-specified for any decision? [no, diagnostics only] -> "Only if something looks off."
6. **Statistical defaults** (table shown) -> "Keep them."
7. **Depth.** [standard readout] -> "Standard."

## Business question
Does the new onboarding checklist increase 7-day activation?

## Decision to be made
Ship / don't ship the checklist.

## Hypothesis
Showing a checklist during onboarding raises the share of new users who activate within 7 days.

## Design
- Variants and intended split: control / treatment, 50/50
- Randomisation unit / analysis unit: user / user
- Dates: 2026-09-01 to 2026-09-14 (14 days)
- Pre-period data: none

## Metrics
| name | role | type | direction | notes |
|---|---|---|---|---|
| converted | primary | binary | increase | activation within 7 days; practical threshold +3% relative |

## Segments (pre-specified)
None for decisions; platform and date for diagnostics.

## Known incidents
Android app release around 2026-09-04/05.

## Statistical settings
Defaults kept.

## Deliverable depth
Standard.

## Risks flagged at intake
- Exposure is logged by a client event, and an Android release happened mid-test. There is a risk of
  variant-specific logging loss, so validation must check SRM by day and by platform.

## Decision after validation BLOCK (2026-10-01)
Claude stopped at validation and explained: treatment has 18,073 users where 19,456 were expected
(chi-square p < 0.001). The loss is concentrated in Android treatment users from 2026-09-05, matching the
Android release. Options offered: (1) fix the Android exposure logging and re-extract the data; (2) a restricted
sensitivity analysis on iOS + Web only, clearly labelled; (3) rerun the test after the fix; (4) a short
"analysis blocked" readout for the team.
**User chose (4) now and (1)/(3) next**: produce a blocked readout with the SRM evidence and no activation
estimates, then re-extract after engineering fixes the logging.
