# Intake: Marketing ads vs PSA test

## Q&A transcript (questions asked in one batch; the user's answers)

Already answered by the description and the data: user-level randomisation (user id unique, one row per user),
treatment = `ad`, control = `psa`, primary metric = `converted` (binary), 588,101 users, no date column.

1. Intended split? -> 95/5 at first; **corrected to 96/4** after validation (see below).
2. Value per conversion / rollout audience? -> **No.** Report incremental conversions per 1,000 users plus a formula.
3. Practical threshold? -> **5% relative lift in conversion.**
4. Test period / early stopping or peeking? -> **No** early stopping or repeated checking. Dates not provided.
5. Exploratory breakdown by exposure (total ads, day, hour)? -> **Yes**, labelled descriptive / non-causal.
6. Bayesian view as well? -> **Both** frequentist and Bayesian.
7. Statistical defaults -> **Keep.**
8. Audience / depth -> **Stakeholders**: standard readout, plain language first, appendix for detail.

## Business question
Would the ad campaign be successful, and how much of its success can be attributed to the ads?

## Decision to be made
Whether the ads drive enough extra conversions to justify the campaign (continue / scale vs stop).

## Hypothesis
Users who see the ad convert at a higher rate than users who see a public service announcement (PSA) in the same slot.

## Design
- Variants and intended split: ad (treatment) / psa (control), **96/4** (corrected from 95/5)
- Randomisation unit / analysis unit: user / user
- Dates: not in the data; the test ran to plan (no early stopping)
- Pre-period data: none

## Metrics
| name | role | type | direction | notes |
|---|---|---|---|---|
| converted | primary | binary | increase | practical threshold +5% relative |

## Segments
None pre-specified. Exploratory only: `total ads` (bucketed), `most ads day`, `most ads hour`. These are measured during
the test, so any breakdown by them is descriptive, not causal.

## Known incidents
None reported.

## Statistical settings
Defaults kept. Bayesian readout added (beta-binomial, weakly informative prior, decision threshold 0.95).

## Deliverable depth
Stakeholder readout: plain-language executive summary, standard deck with appendix.

## Risks flagged at intake
- **Observed split vs intended split:** the file has 96.0% ad / 4.0% psa (23,524 psa users). A 95/5 split implies
  about 29,405. With this many users that gap is very unlikely to be chance, so validation will almost certainly
  flag a sample ratio mismatch (SRM). If it does, the analysis stops for a user decision.
- The value of a conversion is unknown, so money impact is expressed as a formula, not a number.
- No dates: novelty and weekly effects cannot be checked.

## Decision after validation BLOCK (2026-10-01)
Validation found SRM against 95/5 (23,524 psa users vs 29,405 expected, p < 0.001), and the observed split matched
96/4 almost exactly. The user confirmed: **the intended split was 96/4**. Validation is re-run against 96/4.
Open caveat for the report: psa user ids are one contiguous block (900,000-923,523) separate from ad ids
(1,000,000+). Either ids were renumbered per group (harmless) or assignment was by id range (not random).
The data owner should confirm.
