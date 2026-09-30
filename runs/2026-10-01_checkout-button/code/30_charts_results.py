"""Charts: SRM, primary lift, conversion by variant, guardrail scorecard (all numbers from results.json)."""

from pathlib import Path

from abkit import results as R
from abkit import state
from abkit.viz import apply_style, charts, save_chart

apply_style()
RUN = Path(__file__).resolve().parents[1]
res = R.load_results(RUN)
st = state.load_state(RUN)
labels = {m["name"]: m.get("label", m["name"]) for m in st["metrics"]}
dates = next(c for c in res["validation"]["checks"] if c["check"] == "dates")["data"]
p = R.get_result(res, "primary_test")
g = R.get_result(res, "guardrail_revenue")
srm = R.get_result(res, "srm")
n_total = sum(p["n"].values())
src = f"Source: checkout_ab.csv, {dates['start']} to {dates['end']}; n = {n_total:,} users"
thr = next(m["practical_threshold_rel"] for m in st["metrics"] if m["role"] == "primary")
alpha = st["settings"]["alpha"]
ci, ni_ci = f"{1 - alpha:.0%} CI", f"{1 - 2 * alpha:.0%} CI"      # interval levels follow the run's alpha

# SRM
share_t = srm["extra"]["observed_share"]["treatment"]
t = f"Traffic split matches the intended 50/50 (treatment {R.fmt_prob(share_t)}; no sample ratio mismatch)"
save_chart(charts.srm_bar(srm["extra"]["observed"], srm["extra"]["expected_share"], t, "Share of users by variant vs intended split",
                          src + "; chi-square goodness-of-fit", srm["p_value"], srm["extra"]["threshold"]),
           RUN, "srm_bar", t, f"SRM {R.fmt_p_stat(srm['p_value'])}", "Share of users by variant vs intended split", src,
           section="validation", takeaways=[f"Control {R.fmt_prob(srm['extra']['observed_share']['control'])}, treatment {R.fmt_prob(share_t)}",
                                            f"Chi-square {R.fmt_p_stat(srm['p_value'])} vs threshold {srm['extra']['threshold']}",
                                            "Groups are comparable by design"],
           notes="The split is as intended, so the comparison between groups is trustworthy.")

# Primary lift with guardrail
t = f"Treatment lifts checkout conversion by {R.fmt_pct(p['rel_lift'])}, statistically significant, with revenue per user holding up"
rows = [{**p, "metric": "Checkout conversion"}, {**g, "metric": f"Revenue per user (NI, {ni_ci})"}]
save_chart(charts.lift_ci(rows, t, f"Relative lift vs control; conversion {ci}, revenue {ni_ci} (non-inferiority)", src + "; z-test, NI test"),
           RUN, "lift_ci", t, f"Conversion {R.fmt_pct(p['rel_lift'])} ({R.fmt_p_stat(p['p_value'])})",
           "Relative lift vs control", src, section="results",
           takeaways=[f"Conversion: {R.fmt_pct(p['rel_lift'])}, CI {R.fmt_ci(p['rel_ci_low'], p['rel_ci_high'])}",
                      f"Evidence: {R.fmt_p_stat(p['p_value'])}; point estimate above the {R.fmt_pct(thr, 0, signed=False)} threshold",
                      f"Revenue per user: {R.fmt_pct(g['rel_lift'])}, guardrail {g['extra']['status']}"],
           notes="Headline chart: the conversion lift is real; the lower end of its CI is below the practical threshold.")

# Levels
vs = p["extra"]["variant_stats"]
t = f"Checkout conversion rises from {R.fmt_value(vs['control']['mean'], 'binary')} to {R.fmt_value(vs['treatment']['mean'], 'binary')}"
save_chart(charts.metric_by_variant(vs, t, f"Checkout conversion rate by variant, {ci}", src, "control", "binary"),
           RUN, "metric_by_variant", t, t, f"Checkout conversion rate by variant, {ci}", src, section="results",
           takeaways=[f"Control: {R.fmt_value(vs['control']['mean'], 'binary')}", f"Treatment: {R.fmt_value(vs['treatment']['mean'], 'binary')}",
                      f"Absolute change: {R.fmt_pp(p['estimate'], 2)}"],
           notes="Absolute levels: about one extra purchase per hundred checkout users.")

# Guardrail scorecard
t = f"Revenue per user is non-inferior ({R.fmt_pct(g['rel_lift'])}); the {R.fmt_pct(g['extra']['margin_rel'], 0, signed=False)} margin is ruled out"
save_chart(charts.guardrail_scorecard([{**g, "metric": labels["revenue"].capitalize()}], t,
                                      f"Non-inferiority test, one-sided alpha {alpha}, {ni_ci}", src),
           RUN, "guardrail_scorecard", t, f"Revenue guardrail {g['extra']['status']}", "Non-inferiority test", src, section="guardrails",
           takeaways=[f"Change {R.fmt_pct(g['rel_lift'])}, {ni_ci} {R.fmt_ci(g['rel_ci_low'], g['rel_ci_high'])}",
                      f"Margin {R.fmt_pct(-g['extra']['margin_rel'])}: harm beyond it is ruled out",
                      f"Status: {g['extra']['status'].upper()}"],
           notes="The guardrail is a positive statement: a revenue drop larger than the margin is ruled out.")
print("charts saved")
