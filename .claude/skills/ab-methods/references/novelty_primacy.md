# Novelty and primacy effects

## When to use
Visible UI changes, new features, anything users react to because it is new (novelty: early lift that fades)
or need to learn (primacy / learning: early dip or small lift that grows). Also whenever the dashboard lift
"keeps shrinking".

## Assumptions
- Data carry a calendar date and ideally the user's first exposure date (days since exposure).
- Enough units per day for per-day estimates (wide CIs otherwise; aggregate to weeks).

## Step-by-step procedure
1. Lift by days since exposure (cohort view, preferred - separates novelty from calendar effects):
   `time_effects.effects_by(df, metric, type, "days_since_exposure", variant_col, control, treatment)`.
2. Lift by calendar day: `time_effects.daily_effects(...)`; cumulative: `time_effects.cumulative_effects(...)`.
3. `time_effects.trend_test(daily)`: inverse-variance weighted slope of lift on time; `extra.pattern` is
   "novelty (effect decays)", "primacy / learning (effect grows)" or "stable".
4. `time_effects.early_vs_late(df, ..., split_at=7)`: effect in week one vs after.
5. If novelty is present, base the decision on the late-period effect (and say it has a wider CI), or extend the test.

## abkit function(s)
`time_effects.effects_by`, `time_effects.daily_effects`, `time_effects.cumulative_effects`,
`time_effects.trend_test`, `time_effects.early_vs_late`, `charts.daily_lift`, `charts.cumulative_daily`.

## How to interpret
- A decaying lift means the long-run effect is closer to the late estimate than the overall average.
- Calendar-day wobbles without an exposure-day trend usually reflect traffic mix (weekends), not novelty.
- Cumulative curves converge by construction; use them for "did the lead hold", not for trends.

## Common pitfalls
- Reading novelty from the cumulative chart (it always flattens).
- Mixing new and returning users: returning users see the change as new, new users do not.
- Too-short tests (< 2 weeks) for features where learning matters.

## How to present it
Chart: `daily_lift` by days since exposure with CI band and an overall line.
Wording: "The lift fell from +9% in the first week to +4% afterwards; we expect the long-run effect to be
about +4% and recommend deciding on that figure."
