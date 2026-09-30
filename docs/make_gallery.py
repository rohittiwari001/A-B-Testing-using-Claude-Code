"""Render every chart in the catalogue from the demo data into docs/chart_gallery/ for visual review.

Run:  python docs/make_gallery.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from abkit import bayesian, frequentist, power, quasi, sequential, segments, time_effects, validation, variance_reduction  # noqa: E402
from abkit.results import fmt_p, fmt_pct  # noqa: E402
from abkit.viz import apply_style, charts, save_chart  # noqa: E402

OUT = ROOT / "docs" / "chart_gallery"
DEMO = ROOT / "demo_data"


def save(fig, chart_id, title, subtitle, source, message):
    save_chart(fig, OUT, chart_id, title, message, subtitle, source, out_dir=OUT)
    print(f"  {chart_id}")


def main() -> None:
    apply_style()
    OUT.mkdir(parents=True, exist_ok=True)
    co = pd.read_csv(DEMO / "checkout_ab.csv")
    src = "Source: checkout_ab.csv (synthetic), 1-14 Sep 2026"

    conv = frequentist.compare(co, "converted", "binary", "variant", "control", "treatment")
    rev = frequentist.compare(co, "revenue", "continuous", "variant", "control", "treatment")
    rows = [dict(conv.to_dict(), metric="Conversion"), dict(rev.to_dict(), metric="Revenue per user")]
    t = f"Treatment lifts conversion by {fmt_pct(conv.rel_lift)} (p = {fmt_p(conv.p_value)}); revenue per user moves with it"
    save(charts.lift_ci(rows, t, "Relative lift vs control, 95% CI", f"{src}; z-test / Welch t-test"), "lift_ci", t,
         "Relative lift vs control", src, t)

    t = f"Conversion is {fmt_pct(conv.rel_lift)} higher in treatment"
    save(charts.metric_by_variant(conv.extra["variant_stats"], t, "Checkout conversion rate, 95% CI", src, "control", "binary"),
         "metric_by_variant", t, "Conversion rate", src, t)

    cum = time_effects.cumulative_effects(co, "converted", "binary", "exposure_date", "variant", "control", "treatment")
    t = "Treatment has led on cumulative conversion since the first days of the test"
    save(charts.cumulative_daily(cum.to_dict("records"), t, "Cumulative conversion rate by exposure date", src,
                                 metric_type="binary"), "cumulative_daily", t, "", src, t)

    nov = pd.read_csv(DEMO / "novelty_feature.csv")
    by = time_effects.effects_by(nov, "clicks", "count", "days_since_exposure", "variant", "control", "treatment")
    tr = time_effects.trend_test(by)
    t = f"The lift shrinks from {fmt_pct(tr.extra['first_third_lift'], 0)} in week one to {fmt_pct(tr.extra['last_third_lift'], 0)}: a novelty effect"
    save(charts.daily_lift(by.to_dict("records"), t, "Relative lift in clicks per user-day by days since exposure, 95% CI",
                           "Source: novelty_feature.csv (synthetic); Welch t-test per day", x_key="days_since_exposure",
                           xlabel="Days since first exposure"), "daily_lift", t, "", "", t)

    seg = segments.segment_effects(co, "converted", "binary", "platform", "variant", "control", "treatment")
    t = "The conversion lift is concentrated on iOS; Web shows no significant change"
    save(charts.segment_forest([r.to_dict() for r in seg], t, "Relative lift in conversion by platform, 95% CI, BH-corrected",
                               src), "segment_forest", t, "", src, t)

    curve = power.power_curve("proportion", 0.34, [0.02, 0.03, 0.05], [2000, 5000, 10_000, 20_000, 40_000, 80_000, 160_000])
    n3 = power.sample_size_proportions(0.34, 0.03).estimate
    t = f"About {n3:,} users per variant give 80% power to detect a +3% lift"
    save(charts.power_curve(curve.to_dict("records"), t, "Power by users per variant, baseline conversion 34%, alpha 0.05",
                            "Source: abkit.power (normal approximation)", highlight_mde=0.03, planned_n=40_000),
         "power_curve", t, "", "", t)

    tab = power.sample_size_table("proportion", 0.34, [0.02, 0.03, 0.05, 0.08], daily_units=5700)
    t = (f"Detecting a {fmt_pct(tab.mde.iloc[0], 0)} lift takes {tab.days.iloc[0] // 7} weeks; "
         f"{fmt_pct(tab.mde.iloc[2], 0)} needs only {tab.days.iloc[2] // 7} week")
    save(charts.sample_size_vs_mde(tab.to_dict("records"), t, "Users per variant needed at 80% power, alpha 0.05",
                                   "Source: abkit.power; 5,700 eligible users per day", highlight_mde=0.03),
         "sample_size_vs_mde", t, "", "", t)

    bb = bayesian.beta_binomial(int(co[co.variant == "control"].converted.sum()), int((co.variant == "control").sum()),
                                int(co[co.variant == "treatment"].converted.sum()), int((co.variant == "treatment").sum()))
    t = f"There is a {bb.probability:.1%} probability that treatment converts better than control"
    save(charts.posterior_distributions(bb.extra["posteriors"], t, "Posterior conversion rate, Beta(1,1) prior", src, "control",
                                        "binary"), "posterior_distributions", t, "", src, t)
    save(charts.prob_to_beat_control({"treatment": bb.probability}, t, "Posterior probability of beating control", src),
         "prob_to_beat_control", t, "", src, t)

    srm = pd.read_csv(DEMO / "srm_broken.csv")
    s = validation.srm_check(srm, "variant", {"control": 0.5, "treatment": 0.5})
    t = "Treatment is missing 7% of its expected users: results cannot be trusted until fixed"
    save(charts.srm_bar(s.extra["observed"], s.extra["expected_share"], t, "Share of users by variant vs intended 50/50 split",
                        "Source: srm_broken.csv (synthetic); chi-square goodness-of-fit", p_value=s.p_value), "srm_bar", t, "", "", t)

    hist = charts.histogram_data(pd.read_csv(DEMO / "pricing_multiarm.csv"), "revenue", "variant", drop_zeros=True)
    t = "Among buyers, price_high shifts spend upward; the tail is long in every arm"
    save(charts.distribution_compare(hist, t, "Revenue per buyer (USD), density", "Source: pricing_multiarm.csv (synthetic)",
                                     "control", xlabel="Revenue per buyer (USD)"), "distribution_compare", t, "", "", t)

    cu = variance_reduction.cuped(pd.read_csv(DEMO / "cuped_engagement.csv"), "minutes", "pre_minutes", "variant", "control", "treatment")
    t = f"CUPED narrows the confidence interval by {1 - cu.extra['ci_width_adjusted'] / cu.extra['ci_width_unadjusted']:.0%} using pre-period minutes"
    save(charts.cuped_variance_reduction([{"label": "Minutes per user", **cu.extra}], t, "Width of the 95% CI for the difference in minutes",
                                         "Source: cuped_engagement.csv (synthetic)"), "cuped_variance_reduction", t, "", "", t)

    bnd = sequential.boundaries([0.25, 0.5, 0.75, 1.0])
    t = "The observed effect crossed the O'Brien-Fleming boundary at the third look"
    save(charts.sequential_boundaries(bnd.to_dict("records"), t, "Group-sequential design, 4 looks, alpha 0.05 two-sided",
                                      "Source: abkit.sequential (illustrative z path)",
                                      observed=[{"info_fraction": 0.25, "z": 1.1}, {"info_fraction": 0.5, "z": 2.2},
                                                {"info_fraction": 0.75, "z": 2.9}]), "sequential_boundaries", t, "", "", t)

    g1 = frequentist.noninferiority_test(co[co.variant == "control"].revenue, co[co.variant == "treatment"].revenue, 0.01, metric="Revenue per user")
    g2 = frequentist.noninferiority_test(counts=(3100, 40_000, 3560, 40_000), margin_rel=0.05, direction="no_increase", metric="Refund rate")
    g3 = frequentist.noninferiority_test(co[co.variant == "control"].revenue[:3000], co[co.variant == "treatment"].revenue[:3000], 0.01,
                                         metric="Revenue per user (week 1 only)")
    t = "One guardrail is breached: refunds rise beyond the 5% tolerance"
    save(charts.guardrail_scorecard([g.to_dict() for g in (g1, g2, g3)], t, "Non-inferiority tests, 90% CI (illustrative)", src),
         "guardrail_scorecard", t, "", src, t)

    geo = pd.read_csv(DEMO / "geo_rollout.csv")
    did = quasi.diff_in_diff(geo, "orders", "rolled_out", "post_launch", "region", "week", log=True)
    trends = quasi.group_trends(geo, "orders", "rolled_out", "week", index_to_pre=True, post_col="post_launch")
    t = f"Launch regions grew {fmt_pct(did.rel_lift)} faster than other regions after same-day delivery launched"
    save(charts.did_trends(trends.to_dict("records"), t, "Weekly orders indexed to pre-launch average = 100",
                           "Source: geo_rollout.csv (synthetic); two-way fixed-effects DiD, SEs clustered by region",
                           intervention=16.5, ylabel="Orders index"), "did_trends", t, "", "", t)


if __name__ == "__main__":
    main()
