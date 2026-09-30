# Data profile: cuped_engagement.csv

**Overall verdict: PASS**

| Check | Verdict | Detail |
|---|---|---|
| schema | PASS | 5 columns, 20,000 rows |
| dtypes | PASS | All metric columns numeric |
| missing values | PASS | No missing values |
| duplicates | PASS | 20,000 units, one row each |
| contamination | PASS | No unit appears in more than one variant |
| variants | PASS | Counts {'treatment': 10098, 'control': 9902} |
| SRM | PASS | p = 0.166 (threshold 0.001) |
| outliers | PASS | No extreme outliers in continuous metrics |
| impossible values | PASS | Metric values within valid ranges |
| pre-period data | PASS | Available; correlations with metrics pre_minutes~minutes=0.73 |
| covariate balance | PASS | Segment mix similar across variants |

## What this means for the analysis

- pre_minutes is complete and correlates with minutes at 0.73, so CUPED should remove about 53% of the variance.
- No date column, so time trends and novelty cannot be checked (the dates check was skipped).
- Minutes are right-skewed; the sample is large enough for the CLT, and a bootstrap check is planned.
