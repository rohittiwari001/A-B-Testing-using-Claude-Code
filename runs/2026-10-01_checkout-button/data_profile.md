# Data profile: checkout_ab.csv

**Overall verdict: PASS**

| Check | Verdict | Detail |
|---|---|---|
| schema | PASS | 7 columns, 80,000 rows |
| dtypes | PASS | All metric columns numeric |
| missing values | PASS | No missing values |
| duplicates | PASS | 80,000 units, one row each |
| contamination | PASS | No unit appears in more than one variant |
| variants | PASS | Counts {'control': 40183, 'treatment': 39817} |
| SRM | PASS | p = 0.196 (threshold 0.001) |
| dates | PASS | 2026-09-01 to 2026-09-14 (14 days) |
| outliers | PASS | No extreme outliers in continuous metrics |
| impossible values | PASS | Metric values within valid ranges |
| pre-period data | PASS | None described (CUPED not possible) |
| covariate balance | PASS | Segment mix similar across variants |

## What this means for the analysis

- One row per user and no user in both variants, so unit-level tests are valid.
- SRM: p = 0.196 (threshold 0.001). Traffic split matches the intended 50/50.
- Revenue is right-skewed (skew 2.5, max 888 vs p99 171); the plan's bootstrap sensitivity check covers this.
