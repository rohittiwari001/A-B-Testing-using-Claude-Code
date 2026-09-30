"""Charts: cumulative and daily conversion, platform forest plot, revenue distribution (all numbers from results.json)."""

from pathlib import Path

from abkit import results as R
from abkit.viz import apply_style, charts, save_chart

apply_style()
RUN = Path(__file__).resolve().parents[1]
res = R.load_results(RUN)
alpha = __import__("abkit.state", fromlist=["load_state"]).load_state(RUN)["settings"]["alpha"]
ci = f"{1 - alpha:.0%} CI"
dates = next(c for c in res["validation"]["checks"] if c["check"] == "dates")["data"]
src = f"Source: checkout_ab.csv, {dates['start']} to {dates['end']}"
p = R.get_result(res, "primary_test")
tt = R.get_step(res, "time_trends")
trend = tt["results"][0]
cum, daily = tt["data"]["cumulative"], tt["data"]["daily"]

t = f"Treatment led on cumulative conversion on all {len(cum)} days of the test" if all(
    r["treatment_mean"] > r["control_mean"] for r in cum) else "Cumulative conversion by day: the lead changed hands during the test"
save_chart(charts.cumulative_daily(cum, t, "Cumulative checkout conversion by exposure date", src, metric_type="binary"),
           RUN, "cumulative_daily", t, t, "Cumulative conversion by exposure date", src, section="time",
           takeaways=[f"Final: {R.fmt_value(cum[-1]['control_mean'], 'binary')} vs {R.fmt_value(cum[-1]['treatment_mean'], 'binary')}",
                      f"Cumulative lift at the end: {R.fmt_pct(cum[-1]['rel_lift'])}",
                      "No reversal at any point" if "led on" in t else "Lead changed during the test"],
           notes="Stability check: the gap opened early and held.")

t = (f"Daily lift is noisy but shows no trend over the test ({R.fmt_p_stat(trend['p_value'])} for the slope)"
     if not trend["significant"] else f"Daily lift trends over the test: {trend['extra']['pattern']}")
save_chart(charts.daily_lift(daily, t, f"Relative lift in conversion by exposure date, {ci}", src + "; z-test per day",
                             x_key="exposure_date", overall=p["rel_lift"]),
           RUN, "daily_lift", t, t, "Daily relative lift", src, section="time",
           takeaways=[f"Trend slope {R.fmt_pct(trend['estimate'], 2)} per day, {R.fmt_p_stat(trend['p_value'])}",
                      f"First third {R.fmt_pct(trend['extra']['first_third_lift'])} vs last third {R.fmt_pct(trend['extra']['last_third_lift'])}",
                      "No novelty decay to adjust for"],
           notes="Novelty check for a visible UI change: nothing suggests the effect is fading.")

seg = R.get_step(res, "segments_platform")
rows = [seg["data"]["overall"]] + [r for r in seg["results"] if r["method"] == "frequentist.two_proportion_ztest"]
inter = next(r for r in seg["results"] if r["method"] == "segments.interaction_test")
best = max(rows[1:], key=lambda r: r["rel_lift"])
t = (f"The lift is largest on {best['segment']} ({R.fmt_pct(best['rel_lift'])}), but platforms do not differ significantly"
     if not inter["significant"] else f"The effect differs by platform: largest on {best['segment']} ({R.fmt_pct(best['rel_lift'])})")
save_chart(charts.segment_forest(rows, t, f"Relative lift in conversion by platform, {ci}, BH-corrected", src),
           RUN, "segment_forest", t, t, "Lift by platform", src, section="segments",
           takeaways=[f"Interaction test {R.fmt_p_stat(inter['p_value'])}: one rollout decision",
                      f"{best['segment']}: {R.fmt_pct(best['rel_lift'])} (significant after BH)" if best["significant"] else f"{best['segment']}: {R.fmt_pct(best['rel_lift'])}",
                      "All platforms point in the same direction" if all(r["rel_lift"] > 0 for r in rows) else "Directions differ across platforms"],
           notes="Differences between platforms are exploratory; the interaction test is what counts.")

hist = R.get_step(res, "revenue_sensitivity")["data"]["histogram_buyers"]
t = "Revenue per buyer has a long right tail in both variants; the shapes are similar"
save_chart(charts.distribution_compare(hist, t, "Revenue per buyer (USD), density, buyers only", src, "control",
                                       xlabel="Revenue per buyer (USD)"),
           RUN, "distribution_compare", t, t, "Revenue per buyer distribution", src, section="appendix",
           takeaways=["Long right tail in both arms", "Bootstrap used as a sensitivity check", "No capping applied"],
           notes="Why the bootstrap check was run for revenue.")
print("charts saved")
