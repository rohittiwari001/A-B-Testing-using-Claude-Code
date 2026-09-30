"""Charts for the blocked readout: overall SRM and Android-only SRM (numbers from results.json)."""

from pathlib import Path

from abkit import results as R
from abkit.viz import apply_style, charts, save_chart

apply_style()
RUN = Path(__file__).resolve().parents[1]
res = R.load_results(RUN)
dates = next(c for c in res["validation"]["checks"] if c["check"] == "dates")["data"]
src = f"Source: srm_broken.csv, {dates['start']} to {dates['end']}; chi-square goodness-of-fit vs intended 50/50"
srm = R.get_result(res, "srm")
android = R.get_result(res, "srm_localise", segment="Android")
rest = R.get_result(res, "srm_localise", segment="iOS + Web")


def shortfall(r):
    obs, exp = r["extra"]["observed"], r["extra"]["expected_count"]
    return 1 - obs["treatment"] / exp["treatment"]


t = f"Treatment is missing {R.fmt_prob(shortfall(srm))} of its expected users: results cannot be trusted until this is fixed"
save_chart(charts.srm_bar(srm["extra"]["observed"], srm["extra"]["expected_share"], t, "Share of users by variant vs intended 50/50 split",
                          src, srm["p_value"], srm["extra"]["threshold"]),
           RUN, "srm_bar", t, f"Sample ratio mismatch, {R.fmt_p_stat(srm['p_value'])}", "Share of users by variant", src,
           section="validation",
           takeaways=[f"Treatment share {R.fmt_prob(srm['extra']['observed_share']['treatment'])} vs 50.0% intended",
                      f"Chi-square {R.fmt_p_stat(srm['p_value'])} (threshold {srm['extra']['threshold']})",
                      "Effect estimates are withheld"],
           notes="This is the whole story: units went missing unevenly, so the comparison is broken.")

t = (f"The loss is on Android: treatment has {R.fmt_prob(android['extra']['observed_share']['treatment'])} of Android users; "
     f"iOS and Web are balanced")
save_chart(charts.srm_bar(android["extra"]["observed"], android["extra"]["expected_share"], t, "Share of Android users by variant",
                          src, android["p_value"], android["extra"]["threshold"]),
           RUN, "srm_bar_android", t, "Android-specific loss", "Android users by variant", src, section="validation",
           takeaways=[f"Android: {R.fmt_p_stat(android['p_value'])}", f"iOS + Web: {R.fmt_p_stat(rest['p_value'])}",
                      f"About {R.get_step(res, 'srm_localise')['data']['android_late_gap_units']:,} Android treatment users missing since 5 Sep"],
           notes="Points engineering at the Android exposure event after the 5 September release.")
print("charts saved")
