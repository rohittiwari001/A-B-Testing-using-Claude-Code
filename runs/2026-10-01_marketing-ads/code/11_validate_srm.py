"""SRM check against the intended split (read from state.json design.expected_split) and its localisation:
SRM by day, hour and total-ads bucket, plus the user-id structure.

Run from the project root:  python runs/2026-10-01_marketing-ads/code/11_validate_srm.py
Reads only the run copy of the CSV. The total-ads bucket column is added to an in-memory copy; the CSV is never modified.
Stores the results as step "srm" in results.json, always writes the step note (pass or fail), and appends an
"SRM localisation" section to data_profile.md.
If state.json history records a user correction of the intended split, the originally stated split is re-checked
for the record only (it does not drive the verdict).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN.parents[1]))

from abkit import io, results, state, validation  # noqa: E402

st = json.loads((RUN / "state.json").read_text(encoding="utf-8"))
design, settings = st["design"], st["settings"]
UNIT, VAR = design["unit_col"], design["variant_col"]
CONTROL, TREATMENT = design["control"], design["treatment"]
EXPECTED = design["expected_split"]
THR = settings["srm_threshold"]


def split_label(split: dict) -> str:
    return f"{split[TREATMENT] * 100:g}/{split[CONTROL] * 100:g}"


SPLIT = split_label(EXPECTED)

# Originally stated split, if the user corrected it (recorded in state.json history as "... corrected by user: a/b -> c/d").
ORIGINAL = None
for ev in st.get("history", []):
    mt = re.search(r"intended split corrected by user:\s*(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\s*->", ev.get("event", ""))
    if mt:
        ORIGINAL = {TREATMENT: float(mt.group(1)) / 100, CONTROL: float(mt.group(2)) / 100}
ORIGINAL_LBL = split_label(ORIGINAL) if ORIGINAL else None

df = io.load_run_csv(RUN, date_cols=[]).copy()  # in-memory copy only
BUCKET_EDGES = [0, 1, 2, 5, 10, 20, 50, 100, 200, np.inf]
BUCKET_LABELS = ["1", "2", "3-5", "6-10", "11-20", "21-50", "51-100", "101-200", "201+"]
df["total ads bucket"] = pd.cut(df["total ads"], BUCKET_EDGES, labels=BUCKET_LABELS, right=True)

# ---------------------------------------------------------------- overall SRM
overall = validation.srm_check(df, VAR, EXPECTED, THR)
overall.metric = "variant counts"
exp_c = overall.extra["expected_count"][CONTROL]
obs_c = overall.n[CONTROL]
implied_c_from_t = overall.n[TREATMENT] * EXPECTED[CONTROL] / EXPECTED[TREATMENT]
shortfall = {
    "intended_split": SPLIT,
    "expected_control": exp_c,
    "observed_control": obs_c,
    "missing_control_vs_expected": exp_c - obs_c,
    "missing_share_vs_expected": (exp_c - obs_c) / exp_c,
    "implied_control_if_treatment_arm_complete": implied_c_from_t,
    "missing_control_if_treatment_arm_complete": implied_c_from_t - obs_c,
}
overall.extra["shortfall"] = shortfall
overall.extra["intended_split"] = SPLIT
overall.notes.append(f"Checked against the intended split {SPLIT} from state.json: {results.fmt_p_stat(overall.p_value)} "
                     f"(threshold {THR}).")
original_check = None
if ORIGINAL:
    original_check = validation.srm_check(df, VAR, ORIGINAL, THR)
    overall.extra["originally_stated_split"] = {"split": ORIGINAL_LBL, "p_value": original_check.p_value,
                                                "expected_control": original_check.extra["expected_count"][CONTROL]}
    overall.notes.append(f"Intended split corrected by the user from {ORIGINAL_LBL} to {SPLIT} (intake.md). For the record, "
                         f"the check against {ORIGINAL_LBL} gives p = {original_check.p_value:.1e}.")

# ---------------------------------------------------------------- localisation
BY = ["most ads day", "most ads hour", "total ads bucket"]
share_col = f"share_{CONTROL}"
tables, hetero = {}, {}
for col in BY:
    t = validation.srm_by(df, VAR, col, EXPECTED, THR)
    t["n"] = t[f"n_{TREATMENT}"] + t[f"n_{CONTROL}"]
    t[f"expected_{CONTROL}"] = t["n"] * EXPECTED[CONTROL]
    t[f"missing_{CONTROL}"] = t[f"expected_{CONTROL}"] - t[f"n_{CONTROL}"]
    if overall.significant:  # share of the overall shortfall is only meaningful when there is one
        t["share_of_total_missing"] = t[f"missing_{CONTROL}"] / shortfall["missing_control_vs_expected"]
    t[col] = t[col].astype(str)
    tables[col] = t
    # Is the control share the same across levels? (chi-square of independence, variant x level)
    tab = pd.crosstab(df[col], df[VAR])
    chi2, p, dof, _ = stats.chi2_contingency(tab, correction=False)
    hetero[col] = {"chi2": float(chi2), "dof": int(dof), "p_value": float(p),
                   "control_share_min": float(t[share_col].min()), "control_share_max": float(t[share_col].max()),
                   "levels_with_srm": int(t["srm"].sum()), "levels": int(len(t)),
                   "levels_with_control_share_ge_intended": int((t[share_col] >= EXPECTED[CONTROL]).sum())}

# ---------------------------------------------------------------- user-id structure (pre-treatment, can reveal assignment)
id_struct = {}
for g, s in df.groupby(VAR)[UNIT]:
    id_struct[str(g)] = {"min": int(s.min()), "max": int(s.max()), "n": int(s.size),
                         "range_size": int(s.max() - s.min() + 1),
                         "fill_rate": float(s.size / (s.max() - s.min() + 1))}
overlap = not (id_struct[CONTROL]["max"] < id_struct[TREATMENT]["min"] or id_struct[TREATMENT]["max"] < id_struct[CONTROL]["min"])
id_struct["ranges_overlap"] = overlap

results.add_result(
    RUN, "srm", overall, __file__, method="validation.srm_check",
    data={"shortfall": shortfall, "by": {k: v.to_dict(orient="records") for k, v in tables.items()},
          "heterogeneity": hetero, "user_id_structure": id_struct,
          "originally_stated_split": overall.extra.get("originally_stated_split"),
          "total_ads_buckets": {"edges": [e if np.isfinite(e) else None for e in BUCKET_EDGES], "labels": BUCKET_LABELS},
          "srm_bar": {"observed": overall.n, "expected_share": overall.extra["expected_share"]}},
)
note = (f"SRM vs {SPLIT}" + (" (user-corrected)" if ORIGINAL else "") + f": p = {overall.p_value:.4f}"
        + (f"; {shortfall['missing_control_vs_expected']:,.0f} {CONTROL} users short" if overall.significant else "; passes")
        + (f". Originally stated {ORIGINAL_LBL}: p = {original_check.p_value:.1e}" if ORIGINAL else ""))
state.set_step_status(RUN, "srm", "failed" if overall.significant else "done", note=note)

# ---------------------------------------------------------------- append to data_profile.md (idempotent)
MARK = "<!-- srm-localisation -->"
path = RUN / "data_profile.md"
base = path.read_text(encoding="utf-8").split(MARK)[0].rstrip() + "\n"
cols_show = lambda col: [c for c in [col, "n", f"n_{TREATMENT}", f"n_{CONTROL}", share_col, f"expected_{CONTROL}",
                                     f"missing_{CONTROL}", "share_of_total_missing", "p_value", "srm"] if c in tables[col].columns]
obs_share_c = overall.extra["observed_share"][CONTROL]
sec = [MARK, "", "## SRM localisation (code/11_validate_srm.py)", "",
       f"- Intended split {SPLIT} ({TREATMENT}/{CONTROL}). Observed {overall.n[TREATMENT]:,} {TREATMENT} / {obs_c:,} {CONTROL} "
       f"({obs_share_c:.2%} {CONTROL}); expected {overall.extra['expected_count'][TREATMENT]:,.0f} / {exp_c:,.0f}. "
       f"Chi-square = {overall.extra['chi2']:,.2f}, p = {overall.p_value:.4f} (threshold {THR}): "
       + ("**SRM**." if overall.significant else "no mismatch."),
       ]
if ORIGINAL:
    sec.append(f"- The user corrected the intended split from {ORIGINAL_LBL} to {SPLIT} after the first check. Against "
               f"{ORIGINAL_LBL} the same data give p = {original_check.p_value:.1e} (recorded for the audit trail only).")
if overall.significant:
    sec.append(f"- {CONTROL} shortfall: {shortfall['missing_control_vs_expected']:,.0f} users "
               f"({shortfall['missing_share_vs_expected']:.1%}) versus {SPLIT}; "
               f"{shortfall['missing_control_if_treatment_arm_complete']:,.0f} if the {TREATMENT} arm is complete.")
sec.append("")
for col in BY:
    h = hetero[col]
    sec += [f"- `{col}`: {CONTROL} share ranges {h['control_share_min']:.2%} to {h['control_share_max']:.2%} "
            f"(overall {obs_share_c:.2%}, intended {EXPECTED[CONTROL]:.0%}); {h['levels_with_srm']} of {h['levels']} levels "
            f"differ from the intended share on their own. Test of equal {CONTROL} share across levels: p = {h['p_value']:.1e}."]
sec.append("")
if overall.significant:
    sec.append(f"Reading: the overall split does not match {SPLIT}. Use the tables below to see whether the shortfall is local "
               "(one level that could be excluded) or broad. These columns are measured during the test (post-treatment), "
               "so they cannot separate an assignment problem from a logging one.")
else:
    lo = min(h["control_share_min"] for h in hetero.values())
    hi = max(h["control_share_max"] for h in hetero.values())
    sec.append(f"Reading: the overall split matches the intended {SPLIT}, so there is no shortfall to localise. The {CONTROL} "
               f"share does vary across levels ({lo:.1%} to {hi:.1%} around an overall {obs_share_c:.2%}). These columns "
               "are measured during the test (post-treatment), so the variation can reflect the treatment itself (for "
               "example, how many ads a user ends up seeing) rather than assignment; it is reported as a covariate-balance "
               "WARN, and breakdowns by these columns are exploratory.")
sec += ["",
        f"**User-id structure (pre-treatment):** every {CONTROL} user has an id in {id_struct[CONTROL]['min']:,}-{id_struct[CONTROL]['max']:,} "
        f"({id_struct[CONTROL]['range_size']:,} consecutive ids, fill rate {id_struct[CONTROL]['fill_rate']:.0%}); every {TREATMENT} user has an id in "
        f"{id_struct[TREATMENT]['min']:,}-{id_struct[TREATMENT]['max']:,} (fill rate {id_struct[TREATMENT]['fill_rate']:.1%}). The ranges "
        f"{'overlap' if overlap else 'do not overlap'}. Randomly assigned users would be interleaved across one id space. This means either "
        "(a) ids were re-keyed per group when the file was built (harmless for the analysis, but then ids cannot be used to audit assignment), "
        "or (b) group was assigned by id range rather than at random (a design problem). The data cannot tell these apart; "
        "the data owner should confirm.",
        ""]
for col in BY:
    t = tables[col][cols_show(col)]
    sec += [f"### SRM by `{col}`", "", validation._records_table(t.to_dict(orient="records")), ""]
path.write_text(base + "\n" + "\n".join(sec), encoding="utf-8")

print(f"SRM vs {SPLIT}: p = {overall.p_value:.4g}; observed {overall.n}; expected {({k: round(v) for k, v in overall.extra['expected_count'].items()})}")
if ORIGINAL:
    print(f"originally stated {ORIGINAL_LBL}: p = {original_check.p_value:.3e}")
for col, h in hetero.items():
    print(f"{col}: {CONTROL} share {h['control_share_min']:.4f}-{h['control_share_max']:.4f}, SRM levels {h['levels_with_srm']}/{h['levels']}, "
          f">= intended: {h['levels_with_control_share_ge_intended']}, heterogeneity p={h['p_value']:.1e}")
print("user id structure:", id_struct)
print("step note:", note)
