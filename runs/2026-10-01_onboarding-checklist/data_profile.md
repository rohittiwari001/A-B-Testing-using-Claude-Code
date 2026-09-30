# Data profile: srm_broken.csv

**Overall verdict: BLOCK**

| Check | Verdict | Detail |
|---|---|---|
| schema | PASS | 5 columns, 38,911 rows |
| dtypes | PASS | All metric columns numeric |
| missing values | PASS | No missing values |
| duplicates | PASS | 38,911 units, one row each |
| contamination | PASS | No unit appears in more than one variant |
| variants | PASS | Counts {'control': 20838, 'treatment': 18073} |
| SRM | BLOCK | Sample ratio mismatch: p = 1.22e-44 < 0.001; observed shares {'control': 0.5355, 'treatment': 0.4645}. Concentrated in: exposure_date 2026-09-05 to 2026-09-14 (10 of 14 levels); platform=Android |
| dates | PASS | 2026-09-01 to 2026-09-14 (14 days) |
| outliers | PASS | No continuous metrics |
| impossible values | PASS | Metric values within valid ranges |
| pre-period data | PASS | None described (CUPED not possible) |
| covariate balance | WARN | Segment mix differs between variants: platform (p = 5.6e-119) (can indicate an assignment or logging problem, or Simpson's paradox risk) |

## Details of flagged checks

### SRM (BLOCK)

Sample ratio mismatch: p = 1.22e-44 < 0.001; observed shares {'control': 0.5355, 'treatment': 0.4645}. Concentrated in: exposure_date 2026-09-05 to 2026-09-14 (10 of 14 levels); platform=Android

Likely causes to investigate:
- Assignment or bucketing bug (hash salt, uneven ramp, variant-specific eligibility)
- Logging loss that differs by variant (crashes, slow pages, ad blockers, client-side events)
- Bot or fraud filtering that interacts with the treatment
- Data pipeline joins or filters applied after assignment (e.g. 'users who reached step X')
- Ramp changes or restarts during the test without re-randomisation

SRM by `exposure_date`:

| exposure_date | n_control | n_treatment | share_control | share_treatment | p_value | srm |
|---|---|---|---|---|---|---|
| 2026-09-01 | 1589 | 1692 | 0.4843 | 0.5157 | 0.0721 | False |
| 2026-09-02 | 1635 | 1621 | 0.5021 | 0.4979 | 0.8062 | False |
| 2026-09-03 | 1584 | 1649 | 0.4899 | 0.5101 | 0.2530 | False |
| 2026-09-04 | 1606 | 1706 | 0.4849 | 0.5151 | 0.0823 | False |
| 2026-09-05 | 1191 | 921 | 0.5639 | 0.4361 | 4.23e-09 | True |
| 2026-09-06 | 1195 | 915 | 0.5664 | 0.4336 | 1.09e-09 | True |
| 2026-09-07 | 1659 | 1248 | 0.5707 | 0.4293 | 2.48e-14 | True |
| 2026-09-08 | 1628 | 1300 | 0.5560 | 0.4440 | 1.35e-09 | True |
| 2026-09-09 | 1546 | 1295 | 0.5442 | 0.4558 | 2.49e-06 | True |
| 2026-09-10 | 1648 | 1281 | 0.5626 | 0.4374 | 1.19e-11 | True |
| 2026-09-11 | 1612 | 1325 | 0.5489 | 0.4511 | 1.19e-07 | True |
| 2026-09-12 | 1148 | 898 | 0.5611 | 0.4389 | 3.26e-08 | True |
| 2026-09-13 | 1188 | 943 | 0.5575 | 0.4425 | 1.11e-07 | True |
| 2026-09-14 | 1609 | 1279 | 0.5571 | 0.4429 | 8.22e-10 | True |

SRM by `platform`:

| platform | n_control | n_treatment | share_control | share_treatment | p_value | srm |
|---|---|---|---|---|---|---|
| Android | 7295 | 4367 | 0.6255 | 0.3745 | 6.84e-162 | True |
| Web | 5305 | 5249 | 0.5027 | 0.4973 | 0.5857 | False |
| iOS | 8238 | 8457 | 0.4934 | 0.5066 | 0.0901 | False |

### covariate balance (WARN)

Segment mix differs between variants: platform (p = 5.6e-119) (can indicate an assignment or logging problem, or Simpson's paradox risk)

## What this means for the analysis

- BLOCK: treatment has 18,073 users where a 50/50 split implies 19,456 (chi-square p < 0.001).
- Units were lost unevenly between variants, so the groups are no longer comparable and any activation difference could be caused by the loss itself.
- The day and platform tables above show where the loss is concentrated; this matches the Android release flagged at intake.
- No effect estimate should be reported until the cause is understood.
