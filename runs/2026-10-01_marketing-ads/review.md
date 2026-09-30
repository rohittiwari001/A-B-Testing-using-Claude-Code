# Review: 2026-10-01_marketing-ads (round 1)
Verdict: FIXES NEEDED

The statistics hold up and the "Ship" verdict follows from the numbers. Every number I recomputed matched. The problems are
documentation left over from the correction of the intended split by the user (95/5 -> 96/4). The primary test and summary
use 96/4. Several other files still describe the old 95/5 split, which would contradict the deliverables if copied into them.

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| 1 | fix | plan.md still describes the design as 95/5 and does not mention the correction | plan.md l.5-6 "unbalanced intended split (95/5) ... test SRM against 95/5 first"; l.15 step srm "intended split 95/5"; l.23 "SRM against 95/5 (likely to fail)"; l.39-40 "Likely SRM: ... 95/5 implies about 29,405" | Add a dated "Amendment" note to plan.md: the user confirmed 96/4 after validation, SRM is re-checked against 96/4, and the 95/5 risk is resolved. Keep the original text for the audit trail but mark it as superseded |
| 2 | fix | An old failure note is still attached to the SRM step in state.json. The step is marked done and now passes, but the note still says it failed | state.json plan.steps[srm].note = "SRM vs 95/5: p=3.16e-271; 5,881 PSA users short". 11_validate_srm.py l.93-95 only writes a note when SRM is significant (note=None otherwise), so the old note is never replaced | Re-set the step note through the state CLI/API, e.g. "SRM vs 96/4 (user-corrected): p = 1.000", and make the script always write the note |
| 3 | fix | data_profile.md, "SRM localisation" section: 96/4 numbers are labelled 95/5, and the text contradicts the tables | "expected at 95/5: 564,577 / 23,524" (these are the 96/4 counts); "PSA shortfall: 0 users ... versus 95/5"; "If the user confirms 95/5, this is SRM"; "4 of 7 levels reach 5%" while shares range 3.50-4.71% (the counter actually checks >= 4%); the "Reading" paragraph says "No day, hour or exposure level reaches the intended 5% PSA share ... the shortfall is broad" (out of date: there is no shortfall now). The share_of_total_missing column divides by a total shortfall of 0.04 users, giving meaningless values (Saturday 10,210; Thursday -14,643; 11-20 bucket 23,734) | In 11_validate_srm.py, build every split label from EXPECTED instead of hard-coding 95/5. Remove the "Reading"/shortfall text, or make it depend on SRM failing. Rename levels_with_psa_share_ge_5pct -> levels_with_psa_share_ge_intended. Drop share_of_total_missing when the total shortfall is about 0. Reword the per-level result: the PSA share varies across post-treatment levels (3.0-4.8%) around an overall 4.00%. Then re-run 11_validate_srm.py |
| 4 | fix | results.json step srm has the same stale 95/5 wording in its keys and notes | extra.shortfall / data.shortfall key expected_psa_at_95_5 = 23,524.04 (the 96/4 expectation); notes[0] "Against 96/4 instead of 95/5: p = 1.000 (only relevant if 95/5 was approximate)"; data.by share_of_total_missing as in #3; data.heterogeneity levels_with_psa_share_ge_5pct. Also 10_validate_profile.py l.1 docstring "SRM vs 95/5" and the BLOCK branch (l.75 "A 95/5 split", l.62 comment "5/95") hard-code the old split instead of using EXPECTED | Same script fix as #3: rename the keys to be split-neutral (expected_control), replace the note with "Intended split corrected by user to 96/4 (intake.md); p = 1.000; vs 95/5 p = 3.2e-271 for the record". Parameterise the text in 10_validate_profile.py. Re-run both validation scripts, then the summary script (the downstream numbers do not change) |
| 5 | fix | The summary caveats do not say that the intended split was confirmed only after the data had been checked | results.json summary.caveats (4 items) cover the id block, exposure, dates and money, but not that 95/5 failed SRM (p = 3.2e-271) and the user then confirmed 96/4. Stakeholders should know that the split check passing came after this correction | Add one caveat of 15 words or fewer, e.g. "Intended split confirmed as 96/4 after the 95/5 check failed; observed split matches exactly." |
| 6 | note | Treat the SRM pass as weak evidence of random assignment. The observed split matches 96/4 to within 0.04 users (chi-square p = 0.9998). Under independent 4% assignment, P(PSA count = 23,524 exactly) is about 0.27% (SD about 150 users). Combined with PSA ids forming one fully filled block (900,000-923,523, fill 100%) apart from the ad ids, this suggests fixed-quota or id-range assignment, or re-keyed ids | Recomputed: n = 588,101, expected PSA 23,524.04, observed 23,524; data.user_id_structure in step srm | No analyst action beyond #5. The verdict should be shown as conditional on the data owner confirming random assignment. The summary already has this as caveat 1 and next step 2; keep it prominent on the exec slide |
| 7 | note | The PSA share differs by exposure level (most ads day p = 4.8e-48, hour p = 1.1e-28, total-ads bucket p = 4.7e-57). These variables are measured after treatment, so the pattern may reflect the treatment itself. It is not Simpson paradox | Bucket-standardised diff 0.00797 vs pooled 0.00769 (results.json simpsons_check). I recomputed a day-standardised diff of 0.00778 (same sign and size). Mean total ads is 24.82 (ad) vs 24.76 (psa) | Optionally store the day-level Simpson check too. The caveat is already in the notes |
| 8 | note | No dates, so peeking and novelty cannot be checked from the data; "no early stopping" rests on the statement of the user | intake.md Q4; data has no date column | Caveat already present ("No dates in the data ...") |
| 9 | note | No guardrail metrics were defined (none are available in the data), so the verdict rests on the primary metric alone | state.json metrics has only converted | Mention it in the methodology/risks section of the report |
| 10 | note | Minor bookkeeping issues. None of them changes a result | exposure_explore rows: assumption "independent units" passed = null ("verify in validation"; validation confirms one row per user). The interaction-test result stores the Wald statistic 157.96 in estimate/abs_lift. The Bayesian SRM assumption hard-codes passed = True instead of reading step srm. Bayesian alpha = 0.050000000000000044 | Chart and deck code must not plot the interaction estimate as a lift. Optionally clean up in the same pass as #3-4 |
| 11 | note | Exposure breakdown: non-significant buckets should be called inconclusive, not "no effect" | e.g. bucket 1-5: -10.2%, CI [-48.6%, +28.2%]; 11-20: +2.5%, CI [-32.4%, +37.4%] | Use "inconclusive" wording on the segment slide |

## Checklist
1. SRM - ok. Checked against the corrected intended split 96/4 (p = 0.9998, threshold 0.001). I reproduced it, and also p = 3.16e-271 against 95/5. No effects were reported while SRM against 95/5 was unresolved (the user decision is recorded in intake.md). Labelling is inconsistent with 96/4 in several files: findings #1-#4. The strength of the pass as evidence of randomisation: #6.
2. Test matches metric type - ok. Binary user-level converted uses a two-proportion z-test (pooled p, unpooled CI). Beta-binomial is added as the Bayesian view.
3. Unit of analysis - ok. One row per user (588,101 unique), and the randomisation unit is the user. Asserted in 20_analysis_primary_test.py.
4. Multiple testing - ok. The primary uses none (single pre-registered). Segments use BH within each family (bucket; day); I reproduced the day-family adjusted p-values exactly. A joint-family BH sensitivity check is stored. Impact quantities come from the primary comparison and need no correction.
5. Practical vs statistical - ok. Relative lift +43.1% with CI [+29.3%, +56.8%]; the whole CI is above the 5% threshold (ci_low_vs_threshold = above). P(rel lift >= 5%) = 1.0.
6. Inconclusive wording - ok for the primary (significant). Segment wording: note #11.
7. Peeking - ok / note #8. The user states no early stopping; there are no dates to verify it.
8. Novelty/primacy - not checkable (no dates); caveat present (note #8).
9. Simpson paradox / mix imbalance - note #7. The PSA share is imbalanced across post-treatment levels. Pooled and standardised effects agree for both the bucket and the day breakdown.
10. Guardrails - none defined (note #9). No breach or inconclusive guardrail affects the verdict.
11. Conclusion follows - ok. abkit.decision.recommend(primary, [], mde_rel=0.05) returns ship, "The primary metric improved significantly and by more than the practical threshold.", identical to summary.verdict/reason. Headline 43.1%, 1.79% vs 2.55% and 7.7 per 1,000 match the stored results. The caveat on the post-hoc split correction is missing: #5.
12. Traceability - ok. Every step script exists in code/ (validation -> 10_validate_profile.py; srm -> 11_validate_srm.py; primary_test, bayesian, impact, exposure_explore, summary -> 20_analysis_*.py). Numbers spot-checked from the raw CSV: abs diff 0.0076925 with CI [0.0059509, 0.0094340] and p = 1.705e-13; SRM p vs 96/4 = 0.99979; attributable share 0.3011; total incremental 4,343.0; Tuesday relative lift +110.7%; BH-adjusted day p-values. All match.
13. Failed assumptions - ok. No assumption has passed = false. The passed = null entries on segment rows are covered by validation (#10). The simulated CI coverage of the custom impact function is 0.9545 / 0.9545 / 0.9553 (nominal 0.95).

---

# Review: 2026-10-01_marketing-ads (round 2)
Verdict: PASS

All five round-1 fixes are resolved. Every artefact now uses the intended split of 96/4, and the old 95/5 split appears
only as a clearly labelled audit-trail record. None of the numbers or the verdict changed.

| # | Round-1 item | Status | Evidence |
|---|---|---|---|
| 1 | plan.md still said 95/5 | resolved | plan.md l.5-6 dated "Plan note (2026-10-01)"; approach, step 2 and assumptions now say 96/4; the risk section is marked "SRM (resolved)" and keeps the 95/5 history |
| 2 | Stale failure note on the SRM step in state.json | resolved | plan.steps[srm].note = "SRM vs 96/4 (user-corrected): p = 0.9998; passes. Originally stated 95/5: p = 3.2e-271". 11_validate_srm.py now always writes the note (l.114-118) |
| 3 | data_profile.md SRM localisation section | resolved | Labels are built from design.expected_split ("Intended split 96/4 ... p = 0.9998"). The 95/5 check is given only as an audit-trail line. Per-level lines say "differ from the intended share"; the Reading paragraph now says there is no shortfall and the variation is post-treatment. share_of_total_missing is only computed if SRM fails and is gone from the tables |
| 4 | results.json step srm and the validation scripts | resolved | shortfall keys are now split-neutral (intended_split "96/4", expected_control 23,524.04); notes: "Checked against the intended split 96/4 ..." and "corrected by the user from 95/5 to 96/4 ... p = 3.2e-271"; heterogeneity key levels_with_control_share_ge_intended. 10_validate_profile.py and 11_validate_srm.py read the split only from state.json (10: l.24-25; 11: l.32-50; the original split is parsed from the state history, for the record only). Validation verdict WARN, blocking [] |
| 5 | Caveat on the split being confirmed after the 95/5 check failed | resolved | summary.caveats[1] "Split confirmed as 96/4 only after a 95/5 check failed." The assignment caveat is first. A no-guardrails caveat was added (covers note #9) |
| 10 | Bookkeeping (note) | resolved | Segment rows' independent-units assumptions are now passed = true. The Bayesian SRM assumption reads step srm ("SRM p = 1.000"); Bayesian alpha = 0.05. The interaction-test estimate still holds the Wald statistic (157.96) but carries the note "do not plot it as an effect" (acceptable) |
| 11 | Inconclusive wording (note) | resolved | Every non-significant segment row notes "inconclusive (relative lift CI [...]), not evidence of no effect". The caveat says "4 of 7 buckets inconclusive" (1-5, 6-10, 11-20, 201+: correct count) |

Re-checks this round:
- Verdict re-derived: abkit.decision.recommend(primary, [], mde_rel=0.05) returns ship with the same reason as summary.reason. The build_summary change affects display labels only: the headline reads "The ad campaign raises conversion by 43.1% vs the PSA", and plain_english gives 7.7 per 1,000, which matches impact.estimate 7.692.
- The primary test, impact and exposure numbers are unchanged from round 1 (abs diff 0.0076925, CI low 0.0059509, rel lift 0.43085, p 1.705e-13; impact 7.69 / 4,343 / 0.3011). The SRM p-values are unchanged: 0.99979 against 96/4 and 3.16e-271 against 95/5.
- Traceability: validation -> code/10_validate_profile.py; srm, primary_test, bayesian, impact, exposure_explore and summary each point to an existing script in code/.

Remaining notes (no action; carry into caveats as already done): #6 the SRM pass is weak evidence of random assignment
(the split is matched almost exactly and PSA ids form a separate block), so the verdict depends on the data owner confirming
assignment. #7 the PSA share varies across post-treatment levels, but there is no sign of Simpson paradox. #8 with no dates,
peeking and novelty cannot be checked.

## Checklist (round 2)
1. SRM - ok (96/4 used consistently in all artefacts; 95/5 kept as a labelled audit record only)
2. Test vs metric type - ok
3. Unit of analysis - ok
4. Multiple testing - ok
5. Practical vs statistical - ok (CI low +29.3% > 5%)
6. Inconclusive wording - ok
7. Peeking - ok / note #8
8. Novelty - not checkable; caveat present
9. Simpson / mix - note #7
10. Guardrails - none defined; caveat now present
11. Conclusion follows - ok (ship)
12. Traceability - ok
13. Failed assumptions - ok (none false or null)
