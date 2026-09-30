# Intake: Single-button checkout test

## Q&A transcript (dry run: questions asked in one batch, answers given by the user)

Already answered by the description or the data (not asked): variants (control / treatment), 50/50 split,
user-level randomisation, one row per user, primary metric conversion, guardrail revenue per user, dates
2026-09-01 to 2026-09-14 (14 days = 2 full weeks), platform and country columns.

Asked:
1. **Practical threshold.** What is the smallest conversion lift worth shipping? [2% relative] -> "2% is fine."
2. **Guardrail margin.** How much can revenue per user drop before it matters? [1% relative, the default] -> "1%."
3. **Segments.** Platform is pre-specified. Is country also a decision segment, or exploratory? [exploratory] -> "Platform only; skip country."
4. **Peeking.** Was the test checked and possibly stopped early, or run to its planned 14 days? [planned 14 days] -> "Ran the full two weeks, nobody stopped it."
5. **Incidents.** Any outages, campaigns or logging changes during 1-14 Sep? [none] -> "None that we know of."
6. **Revenue outliers.** Any agreed capping of revenue? [no capping; bootstrap sensitivity] -> "No capping."
7. **Statistical defaults** (table shown: alpha 0.05 two-sided, power 0.80, corrections none/holm/BH, SRM p < 0.001,
   bootstrap 10,000, NI margin 1%) -> "Keep them."
8. **Depth.** Deck for the product team, standard readout? [standard] -> "Standard, with an appendix."

## Business question
Should we ship the single-button ("Pay now") checkout to all users?

## Decision to be made
Ship / don't ship the single-button checkout; whether a platform-specific rollout is needed.

## Hypothesis
Replacing the multi-step checkout with a single "Pay now" button increases checkout conversion without lowering revenue per user.

## Design
- Variants and intended split: control / treatment, 50/50
- Randomisation unit / analysis unit: user / user (one row per user)
- Dates: 2026-09-01 to 2026-09-14 (14 days, full weeks); run to plan, no early stopping
- Pre-period data: none

## Metrics
| name | role | type | direction | notes |
|---|---|---|---|---|
| converted | primary | binary | increase | practical threshold +2% relative |
| revenue | guardrail | continuous | no_decrease | revenue per user, NI margin 1% relative, heavy-tailed |

## Segments (pre-specified)
platform (iOS / Android / Web). Country: not analysed.

## Known incidents
None reported.

## Statistical settings
Defaults kept (config/stat_defaults.yaml).

## Deliverable depth
Standard readout with appendix, audience: product team.

## Risks flagged at intake
None.

## Open assumptions (confirmed by user: yes)
- exposure_date is the date of first exposure; conversion window is the test period.
