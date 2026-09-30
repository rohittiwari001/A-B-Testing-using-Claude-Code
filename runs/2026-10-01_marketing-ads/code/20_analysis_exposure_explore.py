"""EXPLORATORY, non-causal: ads-vs-PSA conversion lift by total-ads bucket and by most-ads day (BH), plus an
interaction test for the bucket. Step: exposure_explore.

Run from the project root:  python runs/2026-10-01_marketing-ads/code/20_analysis_exposure_explore.py
`total ads`, `most ads day` and `most ads hour` are measured during the test (post-treatment), so these breakdowns
describe where the lift shows up; they do not show what causes it. The bucket column is added in memory only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN.parents[1]))

from abkit import io, multiple_testing, results, segments, state  # noqa: E402

st = state.load_state(RUN)
s, design = st["settings"], st["design"]
VAR = design["variant_col"]
CONTROL, TREATMENT = design["control"], design["treatment"]
m = next(x for x in st["metrics"] if x["role"] == "primary")
METRIC = m["name"]
ALPHA, CORR = s["alpha"], s["correction_segments"]

df = io.load_run_csv(RUN, date_cols=[])
df[METRIC] = df[METRIC].astype(int)  # bool -> 0/1 (in memory only)

BUCKET_COL = "total ads bucket"
EDGES = [0, 5, 10, 20, 50, 100, 200, np.inf]
LABELS = ["1-5", "6-10", "11-20", "21-50", "51-100", "101-200", "201+"]
assert df["total ads"].min() >= 1, "bucket edges assume at least one ad seen"
df[BUCKET_COL] = pd.cut(df["total ads"], EDGES, labels=LABELS, right=True).astype(str)
DAY_COL = "most ads day"
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# PSA share per level (the covariate-balance WARN from validation) to put in each row's notes.
psa_share = {col: df.groupby(col)[VAR].apply(lambda v: float((v == CONTROL).mean())).to_dict() for col in (BUCKET_COL, DAY_COL)}
overall_psa_share = float((df[VAR] == CONTROL).mean())
srm = results.load_results(RUN)["steps"]["srm"]["data"]["heterogeneity"]
balance_p = {DAY_COL: srm[DAY_COL]["p_value"]}
_tab = pd.crosstab(df[BUCKET_COL], df[VAR])
from scipy import stats  # noqa: E402

balance_p[BUCKET_COL] = float(stats.chi2_contingency(_tab, correction=False)[1])

EXPLORATORY = "exploratory: measured during the test"


dup_check = next(c for c in results.load_results(RUN)["validation"]["checks"] if c["check"] == "duplicates")


def annotate(rows: list, col: str) -> list:
    for r in rows:
        r.role = "segment"
        r.notes.insert(0, EXPLORATORY)
        for a in r.assumptions:  # unit check is done once in validation (one row per user)
            if a["check"].startswith("independent units") and a["passed"] is None:
                a["passed"] = dup_check["verdict"] == "pass"
                a["detail"] = f"validation duplicates check: {dup_check['detail']}"
        if r.segment != "All" and not r.significant:
            r.notes.append(f"Not significant after correction: inconclusive (relative lift CI "
                           f"{results.fmt_ci(r.rel_ci_low, r.rel_ci_high)}), not evidence of no effect.")
        r.extra["segment_col"] = col if r.segment != "All" else None
        if r.segment != "All":
            share = psa_share[col][r.segment]
            r.extra["psa_share"] = share
            r.notes.append(
                f"Covariate balance WARN: the PSA share in this level is {results.fmt_prob(share)} vs "
                f"{results.fmt_prob(overall_psa_share)} overall (equal-share test across levels "
                f"{results.fmt_p_stat(balance_p[col])}); groups within a level may not be comparable.")
            r.notes.append(f"{CORR} correction within the `{col}` family; not causal (post-treatment variable).")
    return rows


by_bucket = annotate(segments.segment_effects(df, METRIC, "binary", BUCKET_COL, VAR, CONTROL, TREATMENT,
                                              alpha=ALPHA, correction=CORR), BUCKET_COL)
by_day = annotate(segments.segment_effects(df, METRIC, "binary", DAY_COL, VAR, CONTROL, TREATMENT,
                                           alpha=ALPHA, correction=CORR, include_overall=False), DAY_COL)

inter = segments.interaction_test(df, METRIC, BUCKET_COL, VAR, CONTROL, TREATMENT, alpha=ALPHA)
inter.role = "segment"
inter.metric = METRIC
inter.notes.append("estimate holds the Wald chi-square statistic, not a lift: do not plot it as an effect.")
inter.notes.insert(0, EXPLORATORY)
inter.notes.append("Linear probability model with HC1 SEs; a significant result means the absolute lift differs across "
                   "exposure buckets, which can reflect who ends up seeing many ads, not a dose-response effect.")

# Simpson's check (heterogeneous_effects.md procedure step 3): diagnostic only. Standardising on a post-treatment
# variable is not a valid causal adjustment; it shows whether the uneven PSA share across buckets drives the pooled lift.
simpson = segments.simpsons_check(df, METRIC, BUCKET_COL, VAR, CONTROL, TREATMENT)
simpson.role = "segment"
simpson.notes.insert(0, EXPLORATORY)
simpson.notes.append("Diagnostic only: the bucket is post-treatment, so the standardised difference is not a causal estimate.")

# Sensitivity: BH across both exploratory families together (stored, not used for the flags).
seg_rows = [r for r in by_bucket + by_day if r.segment != "All"]
joint = multiple_testing.adjust_pvalues([r.p_value for r in seg_rows], CORR)
for r, pj in zip(seg_rows, joint):
    r.extra["p_value_adjusted_across_both_families"] = float(pj)

# Levels skipped by min_n (none expected, recorded for transparency).
kept = {r.segment for r in seg_rows}
skipped = [lvl for lvl in LABELS + DAY_ORDER if lvl not in kept]


def forest(rows: list, order: list[str]) -> list[dict]:
    out = [r.to_dict() for r in rows]
    rank = {k: i for i, k in enumerate(["All", *order])}
    return sorted(out, key=lambda d: rank.get(d["segment"], 99))


results.add_result(
    RUN, "exposure_explore", [*by_bucket, *by_day, inter, simpson], __file__, method="segments.segment_effects",
    data={
        "exploratory": True,
        "label": "Exploratory, non-causal: exposure variables are measured during the test",
        "bucket_definition": {"column": "total ads", "edges": [e if np.isfinite(e) else None for e in EDGES], "labels": LABELS},
        "segment_order": {BUCKET_COL: ["All", *LABELS], DAY_COL: DAY_ORDER},
        "segment_forest": {BUCKET_COL: forest(by_bucket, LABELS), DAY_COL: forest(by_day, DAY_ORDER)},
        "interaction_test": {BUCKET_COL: inter.to_dict()},
        "simpsons_check": {BUCKET_COL: simpson.to_dict()},
        "psa_share_by_level": psa_share, "psa_share_overall": overall_psa_share,
        "covariate_balance_p": balance_p,
        "skipped_levels_min_n": skipped,
        "correction": {"method": CORR, "family": "within each breakdown (bucket; day)"},
    },
)
state.set_step_status(RUN, "exposure_explore", "done")

for r in by_bucket + by_day:
    tag = r.extra.get("segment_col") or "overall"
    print(f"[{tag}] {r.segment}: " + results.describe(r.to_dict()) + f" | n_psa={r.n[CONTROL]:,}")
print(f"interaction (bucket): Wald = {inter.estimate:.1f}, {results.fmt_p_stat(inter.p_value)}, df = {inter.extra['df']}")
print(f"simpson (bucket): pooled {simpson.extra['pooled_diff']:.5f}, standardised {simpson.extra['standardised_diff']:.5f}, "
      f"flagged {simpson.extra['flagged']}, max mix gap {simpson.extra['max_mix_gap']:.4f}")
print("skipped:", skipped)
