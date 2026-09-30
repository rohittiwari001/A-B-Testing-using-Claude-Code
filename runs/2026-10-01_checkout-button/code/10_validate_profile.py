"""Validate checkout_ab.csv against context.md and intake.md; write data_profile.md and results.json validation."""

from pathlib import Path

from abkit import io, results, state, validation

RUN = Path(__file__).resolve().parents[1]
st = state.load_state(RUN)
s = st["settings"]
df = io.load_run_csv(RUN)

spec = {
    "unit_col": "user_id", "variant_col": "variant", "control": "control",
    "expected_split": {"control": 0.5, "treatment": 0.5},
    "date_col": "exposure_date",
    "metrics": {"converted": "binary", "revenue": "continuous"},
    "expected_columns": ["user_id", "variant", "exposure_date", "platform", "country", "converted", "revenue"],
    "segments": ["platform", "country"],
    "non_negative": ["revenue"],
    "srm_threshold": s["srm_threshold"], "min_days": s["min_days"], "prefer_full_weeks": s["prefer_full_weeks"],
}
profile = validation.full_profile(df, spec)
results.set_validation(RUN, profile, __file__)
srm = validation.srm_check(df, "variant", spec["expected_split"], s["srm_threshold"])
results.add_result(RUN, "srm", srm, __file__)
for step in ("validate", "srm"):
    state.set_step_status(RUN, step, "done")

meaning = ["", "## What this means for the analysis", ""]
v = {c["check"]: c for c in profile["checks"]}
meaning.append("- One row per user and no user in both variants, so unit-level tests are valid." if
               v["duplicates"]["verdict"] == "pass" and v["contamination"]["verdict"] == "pass" else
               "- Duplicates or contamination found: see above; exclusions must be handled in analysis.")
meaning.append(f"- SRM: {v['SRM']['detail']}. " + ("Traffic split matches the intended 50/50." if v["SRM"]["verdict"] == "pass"
               else "Effects cannot be trusted until the mismatch is explained."))
out = v["outliers"]["data"].get("revenue", {})
if out:
    meaning.append(f"- Revenue is right-skewed (skew {out['skew']:.1f}, max {out['max']:,.0f} vs p99 {out['p99']:,.0f}); "
                   "the plan's bootstrap sensitivity check covers this.")
(RUN / "data_profile.md").write_text(validation.profile_to_markdown(profile, "Data profile: checkout_ab.csv")
                                     + "\n".join(meaning) + "\n", encoding="utf-8")
print("verdict:", profile["verdict"], "| blocking:", profile["blocking"])
