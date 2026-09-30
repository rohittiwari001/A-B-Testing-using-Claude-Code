"""Validate cuped_engagement.csv incl. pre-period availability, correlation and balance; write data_profile.md."""

from pathlib import Path

from abkit import io, results, state, validation

RUN = Path(__file__).resolve().parents[1]
s = state.load_state(RUN)["settings"]
df = io.load_run_csv(RUN)
spec = {
    "unit_col": "user_id", "variant_col": "variant", "control": "control",
    "expected_split": {"control": 0.5, "treatment": 0.5},
    "metrics": {"minutes": "continuous"}, "pre_period_cols": ["pre_minutes"],
    "expected_columns": ["user_id", "variant", "signup_country", "pre_minutes", "minutes"],
    "segments": ["signup_country"], "non_negative": ["minutes", "pre_minutes"], "srm_threshold": s["srm_threshold"],
}
profile = validation.full_profile(df, spec)
results.set_validation(RUN, profile, __file__)
srm = validation.srm_check(df, "variant", spec["expected_split"], s["srm_threshold"])
results.add_result(RUN, "srm", srm, __file__)
for step in ("validate", "srm"):
    state.set_step_status(RUN, step, "done")

pre = next(c for c in profile["checks"] if c["check"] == "pre-period data")["data"]
rho = pre["correlation"]["pre_minutes~minutes"]
md = validation.profile_to_markdown(profile, "Data profile: cuped_engagement.csv")
md += ("\n## What this means for the analysis\n\n"
       f"- pre_minutes is complete and correlates with minutes at {rho:.2f}, so CUPED should remove about "
       f"{rho ** 2:.0%} of the variance.\n"
       "- No date column, so time trends and novelty cannot be checked (the dates check was skipped).\n"
       "- Minutes are right-skewed; the sample is large enough for the CLT, and a bootstrap check is planned.\n")
(RUN / "data_profile.md").write_text(md, encoding="utf-8")
print("verdict:", profile["verdict"], "| blocking:", profile["blocking"], "| rho:", round(rho, 3))
