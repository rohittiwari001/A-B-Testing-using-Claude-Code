"""Decision and summary on the CUPED estimate, with the unadjusted result and post-hoc caveat. Step: summary."""

from pathlib import Path

from abkit import decision, results, state
from abkit.results import fmt_ci, fmt_p_stat, fmt_pct

RUN = Path(__file__).resolve().parents[1]
st = state.load_state(RUN)
meta = next(m for m in st["metrics"] if m["role"] == "primary")
res = results.load_results(RUN)
cu = results.get_result(res, "cuped_test")
naive = results.get_result(res, "naive_test", 0)
reg = results.get_result(res, "regression_check")
width_cut = cu["extra"]["ci_width_reduction"]

caveats = [
    f"CUPED chosen after the unadjusted result ({fmt_p_stat(naive['p_value'])}) was seen; both reported.",
    f"CUPED lift {fmt_pct(cu['rel_lift'])} vs unadjusted {fmt_pct(naive['rel_lift'])}: treatment had a small "
    "pre-period head start by chance (review finding 2).",
    f"Regression adjustment agrees: {fmt_pct(reg['rel_lift'])} ({fmt_p_stat(reg['p_value'])}).",
    "No dates in the data: novelty not checked.",
]
if cu["rel_ci_low"] < meta["practical_threshold_rel"]:
    caveats.insert(1, f"CI {fmt_ci(cu['rel_ci_low'], cu['rel_ci_high'])} includes lifts below the "
                      f"{fmt_pct(meta['practical_threshold_rel'], 0, signed=False)} threshold.")
next_steps = [
    "Ship the redesigned home feed",
    "Pre-register CUPED with pre-period minutes as the default analysis for future engagement tests",
    "Check minutes per user again four weeks after launch, as novelty could not be ruled out",
]
decision.build_summary(RUN, "cuped_test", __file__, mde_rel=meta["practical_threshold_rel"], direction="increase",
                       metric_label=meta["label"], caveats=caveats, next_steps=next_steps,
                       extra_key_numbers=[{"label": "Unadjusted test (for comparison)",
                                           "value": f"{fmt_pct(naive['rel_lift'])}, {fmt_p_stat(naive['p_value'])}"},
                                          {"label": "CI narrower with CUPED", "value": fmt_pct(width_cut, 0, signed=False)}])
state.set_step_status(RUN, "summary", "done")
print(results.load_results(RUN)["summary"]["headline"])
