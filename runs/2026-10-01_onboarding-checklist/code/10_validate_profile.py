"""Validate srm_broken.csv: full profile with SRM localised by date and platform; write data_profile.md."""

from pathlib import Path

from abkit import io, results, state, validation

RUN = Path(__file__).resolve().parents[1]
s = state.load_state(RUN)["settings"]
df = io.load_run_csv(RUN)
spec = {
    "unit_col": "user_id", "variant_col": "variant", "control": "control",
    "expected_split": {"control": 0.5, "treatment": 0.5}, "date_col": "exposure_date",
    "metrics": {"converted": "binary"},
    "expected_columns": ["user_id", "variant", "exposure_date", "platform", "converted"],
    "segments": ["platform"], "srm_threshold": s["srm_threshold"],
    "min_days": s["min_days"], "prefer_full_weeks": s["prefer_full_weeks"],
}
profile = validation.full_profile(df, spec)
results.set_validation(RUN, profile, __file__)
srm = validation.srm_check(df, "variant", spec["expected_split"], s["srm_threshold"])
results.add_result(RUN, "srm", srm, __file__)
state.set_step_status(RUN, "validate", "done")
state.set_step_status(RUN, "srm", "failed" if srm.significant else "done", "SRM detected" if srm.significant else None)

md = validation.profile_to_markdown(profile, "Data profile: srm_broken.csv")
if profile["verdict"] == "block":
    short = min(srm.extra["observed_share"], key=lambda k: srm.extra["observed_share"][k] - srm.extra["expected_share"][k])
    md += ("\n## What this means for the analysis\n\n"
           f"- BLOCK: {short} has {srm.extra['observed'][short]:,} users where a 50/50 split implies "
           f"{srm.extra['expected_count'][short]:,.0f} (chi-square {results.fmt_p_stat(srm.p_value)}).\n"
           "- Units were lost unevenly between variants, so the groups are no longer comparable and any activation "
           "difference could be caused by the loss itself.\n"
           "- The day and platform tables above show where the loss is concentrated; this matches the Android "
           "release flagged at intake.\n- No effect estimate should be reported until the cause is understood.\n")
(RUN / "data_profile.md").write_text(md, encoding="utf-8")
print("verdict:", profile["verdict"], "| blocking:", profile["blocking"])
print(next(c["detail"] for c in profile["checks"] if c["check"] == "SRM"))
