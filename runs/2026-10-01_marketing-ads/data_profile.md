# Data profile: Marketing campaign, ads vs PSA

**Overall verdict: WARN**

| Check | Verdict | Detail |
|---|---|---|
| schema | PASS | 6 columns, 588,101 rows |
| dtypes | PASS | All metric columns numeric |
| missing values | PASS | No missing values |
| duplicates | PASS | 588,101 units, one row each |
| contamination | PASS | No unit appears in more than one variant |
| variants | PASS | Counts {'ad': 564577, 'psa': 23524} |
| SRM | PASS | p = 1.000 (threshold 0.001) |
| outliers | WARN | Extreme values (reported, not removed): total ads: max is 10x the 99th percentile. Consider winsorised or bootstrap sensitivity analysis. |
| impossible values | PASS | Metric values within valid ranges |
| pre-period data | PASS | None described (CUPED not possible) |
| covariate balance | WARN | Segment mix differs between variants: most ads day (p = 4.8e-48), most ads hour (p = 1.1e-28) (can indicate an assignment or logging problem, or Simpson's paradox risk) |

## Details of flagged checks

### outliers (WARN)

Extreme values (reported, not removed): total ads: max is 10x the 99th percentile. Consider winsorised or bootstrap sensitivity analysis.

### covariate balance (WARN)

Segment mix differs between variants: most ads day (p = 4.8e-48), most ads hour (p = 1.1e-28) (can indicate an assignment or logging problem, or Simpson's paradox risk)

## Informational notes

- The data dictionary in context.md lists an `Index` (row index) column; it is not in the file. It carries no information, so this has no effect on the analysis (not treated as a schema problem).
- There is no date column: time coverage, full weeks, day-level SRM and novelty checks are not possible.
- `converted` is stored as TRUE/FALSE and loaded as boolean (0/1); no other values found.

## What this means for the analysis

- SRM: no mismatch against the intended split 96/4 (p = 1.000).
- Duplicates: 588,101 units, one row each. The analysis unit (user) matches the randomisation unit.
- Contamination: No unit appears in more than one variant.
- `total ads` is heavy-tailed (median 13, p90 57, p99 202, max 2,065). Flagged: Extreme values (reported, not removed): total ads: max is 10x the 99th percentile. Consider winsorised or bootstrap sensitivity analysis. It is not the primary metric; it is an exposure measure used only for descriptive breakdowns. Values are reported, not removed; if it is ever compared between groups, use a bootstrap and a winsorised sensitivity.
- Missing values: No missing values.
- Covariate balance: Segment mix differs between variants: most ads day (p = 4.8e-48), most ads hour (p = 1.1e-28) (can indicate an assignment or logging problem, or Simpson's paradox risk). Note that day/hour of most ads are measured during the test (post-treatment), so imbalance can reflect the treatment itself, not only assignment problems.
- Impossible values: Metric values within valid ranges.
- The primary metric `converted` is binary at user level: the two-proportion z-test planned is appropriate.

<!-- srm-localisation -->

## SRM localisation (code/11_validate_srm.py)

- Intended split 96/4 (ad/psa). Observed 564,577 ad / 23,524 psa (4.00% psa); expected 564,577 / 23,524. Chi-square = 0.00, p = 0.9998 (threshold 0.001): no mismatch.
- The user corrected the intended split from 95/5 to 96/4 after the first check. Against 95/5 the same data give p = 3.2e-271 (recorded for the audit trail only).

- `most ads day`: psa share ranges 3.50% to 4.71% (overall 4.00%, intended 4%); 5 of 7 levels differ from the intended share on their own. Test of equal psa share across levels: p = 4.8e-48.
- `most ads hour`: psa share ranges 3.01% to 4.55% (overall 4.00%, intended 4%); 6 of 24 levels differ from the intended share on their own. Test of equal psa share across levels: p = 1.1e-28.
- `total ads bucket`: psa share ranges 3.26% to 4.81% (overall 4.00%, intended 4%); 3 of 9 levels differ from the intended share on their own. Test of equal psa share across levels: p = 1.5e-62.

Reading: the overall split matches the intended 96/4, so there is no shortfall to localise. The psa share does vary across levels (3.0% to 4.8% around an overall 4.00%). These columns are measured during the test (post-treatment), so the variation can reflect the treatment itself (for example, how many ads a user ends up seeing) rather than assignment; it is reported as a covariate-balance WARN, and breakdowns by these columns are exploratory.

**User-id structure (pre-treatment):** every psa user has an id in 900,000-923,523 (23,524 consecutive ids, fill rate 100%); every ad user has an id in 1,000,000-1,654,483 (fill rate 86.3%). The ranges do not overlap. Randomly assigned users would be interleaved across one id space. This means either (a) ids were re-keyed per group when the file was built (harmless for the analysis, but then ids cannot be used to audit assignment), or (b) group was assigned by id range rather than at random (a design problem). The data cannot tell these apart; the data owner should confirm.

### SRM by `most ads day`

| most ads day | n | n_ad | n_psa | share_psa | expected_psa | missing_psa | p_value | srm |
|---|---|---|---|---|---|---|---|---|
| Friday | 92608 | 88805 | 3803 | 0.0411 | 3704.3200 | -98.6800 | 0.0980 | False |
| Monday | 87073 | 83571 | 3502 | 0.0402 | 3482.9200 | -19.0800 | 0.7414 | False |
| Saturday | 81660 | 78802 | 2858 | 0.0350 | 3266.4000 | 408.4000 | 3.03e-13 | True |
| Sunday | 85391 | 82332 | 3059 | 0.0358 | 3415.6400 | 356.6400 | 4.72e-10 | True |
| Thursday | 82982 | 79077 | 3905 | 0.0471 | 3319.2800 | -585.7200 | 3.19e-25 | True |
| Tuesday | 77479 | 74572 | 2907 | 0.0375 | 3099.1600 | 192.1600 | 4.27e-04 | True |
| Wednesday | 80908 | 77418 | 3490 | 0.0431 | 3236.3200 | -253.6800 | 5.33e-06 | True |

### SRM by `most ads hour`

| most ads hour | n | n_ad | n_psa | share_psa | expected_psa | missing_psa | p_value | srm |
|---|---|---|---|---|---|---|---|---|
| 0 | 5536 | 5309 | 227 | 0.0410 | 221.4400 | -5.5600 | 0.7030 | False |
| 1 | 4802 | 4615 | 187 | 0.0389 | 192.0800 | 5.0800 | 0.7083 | False |
| 2 | 5333 | 5152 | 181 | 0.0339 | 213.3200 | 32.3200 | 0.0239 | False |
| 3 | 2679 | 2590 | 89 | 0.0332 | 107.1600 | 18.1600 | 0.0734 | False |
| 4 | 722 | 694 | 28 | 0.0388 | 28.8800 | 0.8800 | 0.8673 | False |
| 5 | 765 | 742 | 23 | 0.0301 | 30.6000 | 7.6000 | 0.1608 | False |
| 6 | 2068 | 1985 | 83 | 0.0401 | 82.7200 | -0.2800 | 0.9749 | False |
| 7 | 6405 | 6168 | 237 | 0.0370 | 256.2000 | 19.2000 | 0.2209 | False |
| 8 | 17627 | 16968 | 659 | 0.0374 | 705.0800 | 46.0800 | 0.0765 | False |
| 9 | 31004 | 29802 | 1202 | 0.0388 | 1240.1600 | 38.1600 | 0.2687 | False |
| 10 | 38939 | 37454 | 1485 | 0.0381 | 1557.5600 | 72.5600 | 0.0606 | False |
| 11 | 46210 | 44149 | 2061 | 0.0446 | 1848.4000 | -212.6000 | 4.49e-07 | True |
| 12 | 47298 | 45238 | 2060 | 0.0436 | 1891.9200 | -168.0800 | 8.02e-05 | True |
| 13 | 47655 | 45485 | 2170 | 0.0455 | 1906.2000 | -263.8000 | 6.97e-10 | True |
| 14 | 45648 | 43779 | 1869 | 0.0409 | 1825.9200 | -43.0800 | 0.3035 | False |
| 15 | 44683 | 42855 | 1828 | 0.0409 | 1787.3200 | -40.6800 | 0.3261 | False |
| 16 | 37567 | 35963 | 1604 | 0.0427 | 1502.6800 | -101.3200 | 0.0076 | False |
| 17 | 34988 | 33605 | 1383 | 0.0395 | 1399.5200 | 16.5200 | 0.6522 | False |
| 18 | 32323 | 31052 | 1271 | 0.0393 | 1292.9200 | 21.9200 | 0.5338 | False |
| 19 | 30352 | 29169 | 1183 | 0.0390 | 1214.0800 | 31.0800 | 0.3626 | False |
| 20 | 28923 | 27846 | 1077 | 0.0372 | 1156.9200 | 79.9200 | 0.0165 | False |
| 21 | 29976 | 28895 | 1081 | 0.0361 | 1199.0400 | 118.0400 | 5.03e-04 | True |
| 22 | 26432 | 25515 | 917 | 0.0347 | 1057.2800 | 140.2800 | 1.07e-05 | True |
| 23 | 20166 | 19547 | 619 | 0.0307 | 806.6400 | 187.6400 | 1.55e-11 | True |

### SRM by `total ads bucket`

| total ads bucket | n | n_ad | n_psa | share_psa | expected_psa | missing_psa | p_value | srm |
|---|---|---|---|---|---|---|---|---|
| 1 | 56606 | 54298 | 2308 | 0.0408 | 2264.2400 | -43.7600 | 0.3479 | False |
| 2 | 39827 | 37911 | 1916 | 0.0481 | 1593.0800 | -322.9200 | 1.49e-16 | True |
| 3-5 | 81390 | 77753 | 3637 | 0.0447 | 3255.6000 | -381.4000 | 8.96e-12 | True |
| 6-10 | 82952 | 79537 | 3415 | 0.0412 | 3318.0800 | -96.9200 | 0.0859 | False |
| 11-20 | 127484 | 123334 | 4150 | 0.0326 | 5099.3600 | 949.3600 | 6.14e-42 | True |
| 21-50 | 130776 | 125541 | 5235 | 0.0400 | 5231.0400 | -3.9600 | 0.9554 | False |
| 51-100 | 46002 | 44149 | 1853 | 0.0403 | 1840.0800 | -12.9200 | 0.7585 | False |
| 101-200 | 17112 | 16360 | 752 | 0.0439 | 684.4800 | -67.5200 | 0.0084 | False |
| 201+ | 5952 | 5694 | 258 | 0.0433 | 238.0800 | -19.9200 | 0.1876 | False |
