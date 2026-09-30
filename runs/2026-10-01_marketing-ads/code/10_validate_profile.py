"""Validate and profile the marketing ads-vs-PSA CSV (schema, duplicates, SRM vs the intended split in state.json, outliers, balance) and write data_profile.md.

Run from the project root:  python runs/2026-10-01_marketing-ads/code/10_validate_profile.py
Reads only the run copy of the CSV; never modifies data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN.parents[1]))

from abkit import io, results, state, validation  # noqa: E402

st = json.loads((RUN / "state.json").read_text(encoding="utf-8"))
design = st["design"]
settings = st["settings"]

UNIT, VAR = design["unit_col"], design["variant_col"]
CONTROL, TREATMENT = design["control"], design["treatment"]
EXPECTED = design["expected_split"]  # intended split: read only from state.json design.expected_split
SPLIT = f"{EXPECTED[TREATMENT] * 100:g}/{EXPECTED[CONTROL] * 100:g}"  # label, e.g. "96/4"

spec = {
    "unit_col": UNIT,
    "variant_col": VAR,
    "control": CONTROL,
    "expected_split": EXPECTED,
    # no date column in this dataset -> date_col omitted
    "metrics": {"converted": "binary", "total ads": "count"},
    # columns described in context.md that are real data columns; "Index" (a row index) is described but absent
    "expected_columns": ["user id", "test group", "converted", "total ads", "most ads day", "most ads hour"],
    "segments": ["most ads day", "most ads hour"],
    "pre_period_cols": [],
    "non_negative": ["total ads"],
    "srm_threshold": settings["srm_threshold"],
    "min_days": settings["min_days"],
    "prefer_full_weeks": settings["prefer_full_weeks"],
    "allow_multiple_rows": False,  # user-level data, one row per user
}

df = io.load_run_csv(RUN, date_cols=[])  # no date column; stop "most ads day" being guessed as a date
profile = validation.full_profile(df, spec)
checks = {c["check"]: c for c in profile["checks"]}

# ---------------------------------------------------------------- informational facts for the narrative
n_total = len(df)
counts = df[VAR].astype(str).value_counts().to_dict()
exp_psa = EXPECTED[CONTROL] * n_total
missing_psa = exp_psa - counts.get(CONTROL, 0)
# if the ad arm is complete and only PSA users were lost, the PSA arm "should" be ad_n * share_c / share_t
implied_psa_from_ad = counts.get(TREATMENT, 0) * EXPECTED[CONTROL] / EXPECTED[TREATMENT]
missing_psa_if_ad_complete = implied_psa_from_ad - counts.get(CONTROL, 0)
conv_missing = int(df["converted"].isna().sum())
ta = df["total ads"]
ta_q = ta.quantile([0.5, 0.9, 0.99]).to_dict()

# ---------------------------------------------------------------- "what this means" section
lines = ["", "## Informational notes", "",
         "- The data dictionary in context.md lists an `Index` (row index) column; it is not in the file. "
         "It carries no information, so this has no effect on the analysis (not treated as a schema problem).",
         "- There is no date column: time coverage, full weeks, day-level SRM and novelty checks are not possible.",
         "- `converted` is stored as TRUE/FALSE and loaded as boolean (0/1); no other values found.",
         "", "## What this means for the analysis", ""]

srm = checks["SRM"]
srm_d = srm["data"]
if srm["verdict"] == "block":
    lines += [
        f"- **Sample ratio mismatch (BLOCK).** Intended split {EXPECTED[TREATMENT]:.0%} {TREATMENT} / "
        f"{EXPECTED[CONTROL]:.0%} {CONTROL}. Observed {counts.get(TREATMENT, 0):,} {TREATMENT} "
        f"({counts.get(TREATMENT, 0) / n_total:.2%}) and {counts.get(CONTROL, 0):,} {CONTROL} "
        f"({counts.get(CONTROL, 0) / n_total:.2%}). A {SPLIT} split of {n_total:,} users implies "
        f"{exp_psa:,.0f} {CONTROL} users, so about {missing_psa:,.0f} ({missing_psa / exp_psa:.1%}) are missing. "
        f"If the ad arm is complete and only PSA users were lost, the PSA arm should have "
        f"{implied_psa_from_ad:,.0f} users, i.e. about {missing_psa_if_ad_complete:,.0f} missing "
        f"({missing_psa_if_ad_complete / implied_psa_from_ad:.1%}). Chi-square p = {srm_d['p_value']:.2e} "
        f"(threshold {spec['srm_threshold']}).",
        "- The groups are no longer comparable by design: whatever removed PSA users (or added ad users) may be "
        "related to conversion, so the ad-vs-PSA lift can be biased in either direction. **No effect estimate "
        "should be reported as a finding until the user decides how to proceed.** Localisation tables by day, "
        "hour and total-ads bucket are in `11_validate_srm.py` / results.json step `srm`.",
        "- Unless the intended split was different from the one recorded (confirm with the user), the options are: "
        "(a) find the cause and re-extract; (b) proceed with the analysis clearly labelled as a sensitivity "
        "analysis under SRM; (c) rerun the test.",
    ]
else:
    lines += [f"- SRM: no mismatch against the intended split {SPLIT} (p = {srm_d['p_value']:.3f})."]

dup = checks["duplicates"]
lines.append(f"- Duplicates: {dup['detail']}. The analysis unit (user) matches the randomisation unit.")
cont = checks["contamination"]
lines.append(f"- Contamination: {cont['detail']}." + (" Exclude those users in analysis and report n." if cont["verdict"] == "warn" else ""))

out = checks["outliers"]
lines.append(
    f"- `total ads` is heavy-tailed (median {ta_q[0.5]:.0f}, p90 {ta_q[0.9]:.0f}, p99 {ta_q[0.99]:.0f}, max {ta.max():,}). "
    + ("Flagged: " + out["detail"] + " " if out["verdict"] != "pass" else "")
    + "It is not the primary metric; it is an exposure measure used only for descriptive breakdowns. Values are "
    "reported, not removed; if it is ever compared between groups, use a bootstrap and a winsorised sensitivity."
)
miss = checks["missing values"]
lines.append(f"- Missing values: {miss['detail']}"
             + ("" if conv_missing == 0 else f"; `converted` has {conv_missing} missing (not plausible zeros).") + ".")
bal = checks["covariate balance"]
lines.append(f"- Covariate balance: {bal['detail']}. Note that day/hour of most ads are measured during the test "
             "(post-treatment), so imbalance can reflect the treatment itself, not only assignment problems.")
imp = checks["impossible values"]
lines.append(f"- Impossible values: {imp['detail']}.")
lines.append("- The primary metric `converted` is binary at user level: the two-proportion z-test planned is appropriate"
             + (" once the SRM question is resolved." if srm["verdict"] == "block" else "."))

md = validation.profile_to_markdown(profile, "Data profile: Marketing campaign, ads vs PSA") + "\n".join(lines) + "\n"
(RUN / "data_profile.md").write_text(md, encoding="utf-8")

results.set_validation(RUN, profile, __file__)
state.set_step_status(RUN, "validate", "done")

print(f"VERDICT: {profile['verdict'].upper()}")
for c in profile["checks"]:
    if c["verdict"] != "pass":
        print(f"  [{c['verdict'].upper()}] {c['check']}: {c['detail']}")
print(f"Blocking checks: {profile['blocking']}")
