"""Primary test: conversion, ads vs PSA, two-proportion z-test (one pre-registered primary, no correction). Step: primary_test.

Run from the project root:  python runs/2026-10-01_marketing-ads/code/20_analysis_primary_test.py
Reads only the run copy of the CSV (never modified). `converted` (TRUE/FALSE) is cast to 0/1 in memory.
"""

from __future__ import annotations

import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN.parents[1]))

from abkit import frequentist, io, multiple_testing, results, state  # noqa: E402

st = state.load_state(RUN)
s, design = st["settings"], st["design"]
VAR, UNIT = design["variant_col"], design["unit_col"]
CONTROL, TREATMENT = design["control"], design["treatment"]
m = next(x for x in st["metrics"] if x["role"] == "primary")
METRIC, DIRECTION = m["name"], m["direction"]

df = io.load_run_csv(RUN, date_cols=[])
df[METRIC] = df[METRIC].astype(int)  # bool -> 0/1 (in memory only)

# Unit of analysis = randomisation unit: one row per user (checked in validation; re-asserted here).
assert df[UNIT].is_unique, "Expected one row per user"

alternative = frequentist.alternative_for(s["sidedness"], DIRECTION)
r = frequentist.compare(df, METRIC, "binary", VAR, CONTROL, TREATMENT, alpha=s["alpha"], alternative=alternative, role="primary")
multiple_testing.apply_correction([r], s["correction_primary"], s["alpha"])  # "none": single pre-registered primary
r.assumptions[0]["passed"] = True
r.assumptions[0]["detail"] = f"{len(df):,} rows, {df[UNIT].nunique():,} unique users; unit = randomisation unit"
srm = results.get_result(RUN, "srm")
r.assumptions.append({"check": "no sample ratio mismatch vs intended split (96/4, corrected by the user)",
                      "passed": not bool(srm.get("significant")),
                      "detail": f"SRM {results.fmt_p_stat(srm.get('p_value'))} (step srm, threshold {s['srm_threshold']})"})
threshold = m.get("practical_threshold_rel")
r.extra["practical_threshold_rel"] = threshold
r.extra["ci_low_vs_threshold"] = ("above" if r.rel_ci_low is not None and r.rel_ci_low >= threshold else
                                  "below" if r.rel_ci_high is not None and r.rel_ci_high < threshold else "straddles")
r.notes.append("Covariate balance WARN in validation (PSA share varies by most-ads day / hour / exposure bucket); these are "
               "measured during the test, so they do not change this user-level comparison but are noted as a caveat.")

vs = r.extra["variant_stats"]
conv_counts = df.groupby(VAR)[METRIC].agg(["sum", "count"]).rename(columns={"sum": "conversions", "count": "users"})
results.add_result(
    RUN, "primary_test", r, __file__, method="frequentist.two_proportion_ztest",
    data={
        "metric_by_variant": [{"variant": k, "mean": v["mean"], "ci_low": v["ci_low"], "ci_high": v["ci_high"], "n": v["n"]}
                              for k, v in vs.items()],
        "counts": {str(k): {"conversions": int(row.conversions), "users": int(row.users)} for k, row in conv_counts.iterrows()},
        "lift_ci": [{"metric": m.get("label", METRIC), "role": "primary", "rel_lift": r.rel_lift,
                     "rel_ci_low": r.rel_ci_low, "rel_ci_high": r.rel_ci_high, "significant": r.significant}],
        "practical_threshold_rel": threshold,
    },
)
state.set_step_status(RUN, "primary_test", "done")
print(results.describe(r.to_dict()))
print(f"abs diff {r.estimate:.5f} [{r.ci_low:.5f}, {r.ci_high:.5f}]; rates psa {r.control_value:.5f} ad {r.treatment_value:.5f}; "
      f"CI vs threshold: {r.extra['ci_low_vs_threshold']}")
