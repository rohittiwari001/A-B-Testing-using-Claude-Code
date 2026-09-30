"""Charts: naive vs CUPED lift, CI width reduction, minutes by variant, distribution (numbers from results.json)."""

from pathlib import Path

from abkit import results as R
from abkit.viz import apply_style, charts, save_chart

apply_style()
RUN = Path(__file__).resolve().parents[1]
res = R.load_results(RUN)
cu = R.get_result(res, "cuped_test")
naive = R.get_result(res, "naive_test", 0)
n = sum(cu["n"].values())
src = f"Source: cuped_engagement.csv, 14-day test; n = {n:,} users; Welch t-test, CUPED with pre_minutes"
width_cut = cu["extra"]["ci_width_reduction"]

sig = "statistically significant" if cu["significant"] else "not statistically significant"
t = f"With CUPED, the feed lifts minutes per user by {R.fmt_pct(cu['rel_lift'])}, {sig} ({R.fmt_p_stat(cu['p_value'])})"
rows = [{**naive, "metric": "Unadjusted (Welch)"}, {**cu, "metric": "CUPED-adjusted"}]
save_chart(charts.lift_ci(rows, t, "Relative lift in minutes per user vs control, 95% CI", src), RUN, "lift_ci", t,
           f"CUPED {R.fmt_pct(cu['rel_lift'])}, {R.fmt_p_stat(cu['p_value'])}", "Relative lift, 95% CI", src, section="results",
           takeaways=[f"Unadjusted: {R.fmt_pct(naive['rel_lift'])}, {R.fmt_p_stat(naive['p_value'])}",
                      f"CUPED: {R.fmt_pct(cu['rel_lift'])}, CI {R.fmt_ci(cu['rel_ci_low'], cu['rel_ci_high'])}",
                      "CUPED chosen after the first result: stated as a caveat"],
           notes="Same data, sharper lens: pre-period minutes explain much of the user-to-user noise.")

t = (f"Using pre-period minutes narrows the confidence interval by {R.fmt_prob(width_cut)}, like having "
     f"{cu['extra']['effective_sample_multiplier']:.1f}x the users")
save_chart(charts.cuped_variance_reduction([{"label": "Minutes per user", **cu["extra"]}], t,
                                           "Width of the 95% CI for the difference in minutes per user", src),
           RUN, "cuped_variance_reduction", t, f"CI {R.fmt_prob(width_cut)} narrower", "CI width before vs after CUPED", src,
           section="results",
           takeaways=[f"Pre/post correlation {cu['extra']['correlation']:.2f}",
                      f"Variance removed: {R.fmt_prob(cu['extra']['variance_reduction'])}",
                      f"Equivalent to {cu['extra']['effective_sample_multiplier']:.1f}x the sample"],
           notes="Plain-English explanation of CUPED for the product team.")

vs = naive["extra"]["variant_stats"]
t = f"Minutes per user: {R.fmt_num(vs['control']['mean'], 1)} in control vs {R.fmt_num(vs['treatment']['mean'], 1)} in treatment (unadjusted)"
save_chart(charts.metric_by_variant(vs, t, "Minutes per user during the test, 95% CI (unadjusted)", src, "control", "continuous",
                                    ylabel="Minutes per user"),
           RUN, "metric_by_variant", t, t, "Minutes per user", src, section="results",
           takeaways=[f"Control {R.fmt_num(vs['control']['mean'], 1)} min", f"Treatment {R.fmt_num(vs['treatment']['mean'], 1)} min",
                      f"CUPED-adjusted difference {R.fmt_num(cu['estimate'], 2)} min"],
           notes="Raw levels for context; the decision uses the CUPED-adjusted difference.")

hist = R.get_step(res, "naive_test")["data"]["histogram"]
t = "Minutes per user are right-skewed with similar shapes in both variants"
save_chart(charts.distribution_compare(hist, t, "Minutes per user during the test, density", src, "control",
                                       xlabel="Minutes per user"),
           RUN, "distribution_compare", t, t, "Distribution of minutes", src, section="appendix",
           takeaways=["Long right tail", "No change in shape", "Bootstrap agrees with Welch"],
           notes="Supports the use of mean-based tests at this sample size.")
print("charts saved")
