"""Decision and summary: verdict against the practical threshold and the revenue guardrail. Step: summary."""

from pathlib import Path

from abkit import decision, results, state
from abkit.results import fmt_p_stat, fmt_pct

RUN = Path(__file__).resolve().parents[1]
st = state.load_state(RUN)
primary_meta = next(m for m in st["metrics"] if m["role"] == "primary")
res = results.load_results(RUN)

seg = results.get_step(res, "segments_platform")["results"]
inter = next(r for r in seg if r["method"] == "segments.interaction_test")
plat = [r for r in seg if r["method"] == "frequentist.two_proportion_ztest"]
best = max(plat, key=lambda r: r["rel_lift"])
worst = min(plat, key=lambda r: r["rel_lift"])
trend = results.get_result(res, "time_trends")
boot = results.get_result(res, "revenue_sensitivity", 1)

guard = results.get_result(res, "guardrail_revenue")
boot_agrees = (boot["rel_ci_low"] > -guard["extra"]["margin_rel"]) == (guard["extra"]["status"] == "pass")
caveats = [
    f"Platforms: {best['segment']} {fmt_pct(best['rel_lift'])}, {worst['segment']} {fmt_pct(worst['rel_lift'])}; interaction "
    + (f"{fmt_p_stat(inter['p_value'])}, so they differ." if inter["significant"] else f"{fmt_p_stat(inter['p_value'])}, no evidence they differ."),
    f"Revenue is heavy-tailed; bootstrap CI {results.fmt_ci(boot['rel_ci_low'], boot['rel_ci_high'])} "
    + ("agrees with the guardrail pass." if boot_agrees else "disagrees with the guardrail result."),
    f"Daily lift: {trend['extra']['pattern']} ({fmt_p_stat(trend['p_value'])}).",
]
prim = results.get_result(res, "primary_test")
thr = primary_meta["practical_threshold_rel"]
if prim["rel_ci_low"] < thr <= prim["rel_lift"]:
    caveats.insert(0, f"CI lower bound {fmt_pct(prim['rel_ci_low'])} is below the {fmt_pct(thr, 0, signed=False)} threshold: "
                      "the true lift may be smaller than needed (review finding 1).")
next_steps = [
    "Roll out the single-button checkout to all users on every platform",
    "Track conversion and revenue per user for four weeks after rollout against this test's estimates",
    f"Use a follow-up test if a platform-specific design is wanted ({worst['segment']} shows the smallest lift)",
]
decision.build_summary(RUN, "primary_test", __file__, guardrail_step="guardrail_revenue",
                       mde_rel=primary_meta["practical_threshold_rel"], direction="increase",
                       metric_label=primary_meta["label"], caveats=caveats, next_steps=next_steps)
state.set_step_status(RUN, "summary", "done")
print(results.load_results(RUN)["summary"]["headline"])
