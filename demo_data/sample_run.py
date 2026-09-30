"""Build a complete sample run (checkout demo) programmatically.

Used by the deck/report smoke tests and by ``docs/make_samples.py`` to render a sample deck and
report for review. A real run is produced by the agents writing numbered scripts in ``code/``;
this helper condenses those steps into one function.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from abkit import decision, frequentist, results, segments, state, time_effects, validation  # noqa: E402
from abkit.results import fmt_ci, fmt_p_stat, fmt_pct, fmt_pp, fmt_value  # noqa: E402
from abkit.viz import charts, save_chart  # noqa: E402

DEMO = Path(__file__).resolve().parent


def build_checkout_sample(root: str | Path | None = None, run_date: date = date(2026, 10, 1)) -> Path:
    run = state.new_run("checkout-sample", (DEMO / "checkout_ab_context.md").read_text(encoding="utf-8"),
                        DEMO / "checkout_ab.csv", run_date=run_date, root=root)
    script = str(run / "code" / "20_analysis_sample.py")
    st = state.load_state(run)
    st.update({
        "title": "Single-button checkout test",
        "phase": "deliverables",
        "problem_type": ["post_test_readout", "heterogeneous_effects", "guardrail_check"],
        "metrics": [{"name": "converted", "role": "primary", "type": "binary", "direction": "increase"},
                    {"name": "revenue", "role": "guardrail", "type": "continuous", "direction": "no_decrease"}],
        "plan": {
            "steps": [{"id": s, "method": m, "status": "done"} for s, m in [
                ("validate", "validation.full_profile"), ("primary_test", "frequentist.two_proportion_ztest"),
                ("guardrails", "frequentist.noninferiority_test"), ("segments", "segments.segment_effects"),
                ("time_trends", "time_effects.cumulative_effects"), ("summary", "decision.build_summary")]],
            "charts": ["lift_ci", "metric_by_variant", "cumulative_daily", "segment_forest", "guardrail_scorecard"],
            "deck_sections": ["exec_summary", "setup", "results", "guardrails", "segments", "risks", "next_steps", "appendix"],
            "report_sections": ["exec_summary", "business_question", "design", "data_validation", "methodology", "results",
                                "guardrails", "segments", "risks", "recommendation", "appendix"],
            "deliverables": ["charts/", "deck.pptx", "summary.docx"],
        },
        "gates": {"plan_approved": True, "validation_passed": True, "review_passed": True},
    })
    state.save_state(run, st)
    (run / "intake.md").write_text(
        "# Intake\n\n## Business question\nShould we ship the single-button checkout?\n\n"
        "## Hypothesis\nA single 'Pay now' button raises checkout conversion without lowering revenue per user.\n",
        encoding="utf-8")
    (run / "review.md").write_text("# Review\n\n- note: sample run built by demo_data/sample_run.py\n", encoding="utf-8")

    df = pd.read_csv(run / "data" / "checkout_ab.csv")
    spec = {"unit_col": "user_id", "variant_col": "variant", "control": "control", "date_col": "exposure_date",
            "expected_split": {"control": 0.5, "treatment": 0.5}, "metrics": {"converted": "binary", "revenue": "continuous"},
            "segments": ["platform", "country"], "non_negative": ["revenue"], "expected_columns": list(df.columns)}
    results.set_validation(run, validation.full_profile(df, spec), str(run / "code" / "10_validate_sample.py"))

    prim = frequentist.compare(df, "converted", "binary", "variant", "control", "treatment", role="primary")
    results.add_result(run, "primary_test", prim, script)
    c, t = df[df.variant == "control"].revenue, df[df.variant == "treatment"].revenue
    guard = frequentist.noninferiority_test(c, t, margin_rel=0.01, metric="revenue")
    results.add_result(run, "guardrails", guard, script)
    seg = segments.segment_effects(df, "converted", "binary", "platform", "variant", "control", "treatment")
    inter = segments.interaction_test(df, "converted", "platform", "variant", "control", "treatment")
    results.add_result(run, "segments", [*seg[1:], inter], script, data={"overall": seg[0].to_dict()})
    cum = time_effects.cumulative_effects(df, "converted", "binary", "exposure_date", "variant", "control", "treatment")
    results.add_result(run, "time_trends", None, script, method="time_effects.cumulative_effects", data={"cumulative": cum})
    decision.build_summary(run, "primary_test", script, guardrail_step="guardrails", mde_rel=0.02, metric_label="checkout conversion",
                           next_steps=["Roll out the single-button checkout to 100% of users",
                                       "Keep monitoring revenue per user for four weeks after rollout",
                                       "Investigate why the Web lift is smaller before the next checkout test"])

    res = results.load_results(run)
    p = results.get_result(res, "primary_test")
    g = results.get_result(res, "guardrails")
    src = f"Source: checkout_ab.csv, 2026-09-01 to 2026-09-14; n = {sum(p['n'].values()):,} users"
    t1 = f"Treatment lifts checkout conversion by {fmt_pct(p['rel_lift'])}, statistically significant"
    save_chart(charts.lift_ci([{**p, "metric": "Conversion"}, {**g, "metric": "Revenue per user"}], t1,
                              "Relative lift vs control, 95% CI (revenue: 90% CI, non-inferiority)", src + "; two-proportion z-test"),
               run, "lift_ci", t1, f"Conversion {fmt_pct(p['rel_lift'])} ({fmt_p_stat(p['p_value'])})", section="results",
               takeaways=[f"Conversion: {fmt_pct(p['rel_lift'])} relative, CI {fmt_ci(p['rel_ci_low'], p['rel_ci_high'])}",
                          f"Evidence: {fmt_p_stat(p['p_value'])}, above the 2% practical threshold",
                          f"Revenue per user: {fmt_pct(g['rel_lift'])}, non-inferiority {g['extra']['status']}"])
    vs = p["extra"]["variant_stats"]
    t2 = f"Conversion rises from {fmt_value(vs['control']['mean'], 'binary')} to {fmt_value(vs['treatment']['mean'], 'binary')}"
    save_chart(charts.metric_by_variant(vs, t2, "Checkout conversion rate, 95% CI", src, "control", "binary"), run,
               "metric_by_variant", t2, t2, section="results",
               takeaways=[f"Control: {fmt_value(vs['control']['mean'], 'binary')}", f"Treatment: {fmt_value(vs['treatment']['mean'], 'binary')}",
                          f"Absolute change: {fmt_pp(p['estimate'], 2)}"])
    cum_r = results.get_step(res, "time_trends")["data"]["cumulative"]
    t3 = "Treatment led on cumulative conversion throughout the test"
    save_chart(charts.cumulative_daily(cum_r, t3, "Cumulative conversion rate by exposure date", src, metric_type="binary"), run,
               "cumulative_daily", t3, t3, section="results",
               takeaways=["No reversal over the 14 days", "Gap stable after the first week", "No sign of a novelty spike"])
    seg_r = [results.get_step(res, "segments")["data"]["overall"]] + [r for r in results.get_step(res, "segments")["results"] if r.get("segment") and r["method"] != "segments.interaction_test"]
    it = [r for r in results.get_step(res, "segments")["results"] if r["method"] == "segments.interaction_test"][0]
    best = max(seg_r[1:], key=lambda r: r["rel_lift"])["segment"]
    t4 = (f"The lift is largest on {best}; " + ("the platforms differ significantly" if it["significant"]
          else "differences between platforms are not significant"))
    save_chart(charts.segment_forest(seg_r, t4, "Relative lift in conversion by platform, 95% CI, BH-corrected", src), run,
               "segment_forest", t4, t4, section="segments",
               takeaways=[f"Interaction test: {fmt_p_stat(it['p_value'])}", "Treat platform differences as exploratory",
                          "Direction is positive on every platform"])
    t5 = f"Revenue per user is non-inferior ({fmt_pct(g['rel_lift'])})"
    save_chart(charts.guardrail_scorecard([{**g, "metric": "Revenue per user"}], t5, "Non-inferiority test, margin 1%, 90% CI", src),
               run, "guardrail_scorecard", t5, t5, section="guardrails",
               takeaways=[f"Change {fmt_pct(g['rel_lift'])}", f"Margin {g['extra']['margin_rel']:.0%}", f"Status: {g['extra']['status']}"])
    return run
