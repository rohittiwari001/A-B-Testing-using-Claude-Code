# Question bank

Ask only what is unknown. Each question shows why it matters, so you can judge whether the
description already answers it. Offer a default in brackets.

## 1. Business question and decision
- What decision will this analysis inform (ship / not ship, choose an arm, size a test, explain a drop)?
  *Why:* the decision defines the primary metric and the verdict format.
- Who is the audience for the deck (exec / product team / data science)? [product team]

## 2. Hypothesis
- What change did the treatment make, and which direction do you expect the primary metric to move?
  *Why:* sets sidedness and the "good direction" for each metric.
- Is there a practical threshold - the smallest lift worth shipping (MDE)? [the MDE the test was powered for, if known]
  *Why:* separates statistical from practical significance (verdict "iterate" vs "ship").

## 3. Variants and traffic split
- Variant labels and which one is control? (read from data first)
- Intended split (50/50, 33/33/33, 90/10 ramp)? *Why:* SRM is tested against the *intended* split.
- Was the split changed during the test (ramp-up)? *Why:* ramps break naive SRM and pooled estimates.

## 4. Randomisation unit
- User, device, session, account, region? *Why:* the unit of independence; everything is analysed at or above it.

## 5. Analysis unit
- Is the metric defined per randomisation unit, or per session / pageview / order?
  *Why:* if finer than the randomisation unit -> ratio metric, delta method or clustered SEs.

## 6. Dates
- Start and end dates; was the test stopped early or checked repeatedly? *Why:* peeking needs sequential methods.
- Were full weeks covered? *Why:* weekday mix.

## 7. Metrics (for each)
- Role: primary (exactly one, pre-registered) / secondary / guardrail.
- Type: binary / continuous / count / ratio (infer from data, confirm).
- Desired direction: increase / decrease / no_decrease / no_increase (guardrails use no_*).
- Guardrail margin if not the 1% default.
- Any capping / winsorising rule already agreed for revenue-like metrics?

## 8. Pre-period data
- Is there a pre-experiment value of the metric (or a correlated covariate) per unit? *Why:* CUPED.

## 9. Segments of interest
- Which segments were pre-specified (platform, country, new vs returning)? *Why:* confirmatory vs exploratory.

## 10. Known incidents
- Outages, bugs, marketing campaigns, holidays, logging changes during the test? *Why:* exclusions, SRM causes.

## 11. Statistical settings
- Show the defaults table; ask keep or change. Common changes: alpha 0.01 for high-risk launches,
  one-sided for pure non-inferiority questions, Bayesian readout requested by stakeholders.

## 12. Deliverable depth
- Short (exec summary + 3-5 slides), standard (full readout), or deep dive (plus appendix and segment detail)? [standard]

## Problem-type specific extras
- **Power analysis:** baseline rate or mean and SD (or historical data file), daily eligible traffic, number of arms, MDE candidates.
- **SRM investigation:** how assignment and logging work, any filters applied after assignment.
- **Sequential monitoring:** planned number of looks and max duration.
- **Quasi-experiment:** why randomisation was impossible, treated units, launch date, candidate control units.
