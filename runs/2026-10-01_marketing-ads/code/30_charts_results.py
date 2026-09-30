"""Charts for 2026-10-01_marketing-ads: srm_bar, lift_ci, metric_by_variant (all numbers from results.json).

Run from the project root:  python runs/2026-10-01_marketing-ads/code/30_charts_results.py
Display names for stakeholders: "Ads" (data label `ad`) and "PSA" (data label `psa`).
"""

import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN.parents[1]))

from abkit import results as R  # noqa: E402
from abkit import state  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402
from abkit.viz import PALETTE, SIZES, apply_style, charts, save_chart  # noqa: E402

apply_style()
res = R.load_results(RUN)
st = state.load_state(RUN)
design, settings = st["design"], st["settings"]
CONTROL, TREATMENT = design["control"], design["treatment"]
NAMES = {TREATMENT: "Ads", CONTROL: "PSA"}
alpha = settings["alpha"]
ci = f"{1 - alpha:.0%} CI"                                   # interval level follows the run's alpha
primary_metric = next(m for m in st["metrics"] if m["role"] == "primary")
thr = primary_metric["practical_threshold_rel"]
csv_name = Path(st["input_csv"]).name


def rename(d):
    """Data labels -> display names, control (PSA) first."""
    return {NAMES[k]: d[k] for k in (CONTROL, TREATMENT)}


p = R.get_result(res, "primary_test")
b = R.get_result(res, "bayesian")
srm = R.get_result(res, "srm")
per_k = R.get_result(res, "impact", 0)
cred = f"{b['extra'].get('credible_level', 1 - alpha):.0%}"
n_total = sum(p["n"].values())
src = f"Source: {csv_name} (test dates not recorded); n = {n_total:,} users"

# --------------------------------------------------------------------------- srm_bar
ex = srm["extra"]
obs, exp_share, obs_share = rename(ex["observed"]), rename(ex["expected_share"]), ex["observed_share"]
split = ex["intended_split"]
orig = ex["originally_stated_split"]
t = (f"Traffic split matches the intended {split} (Ads {R.fmt_prob(obs_share[TREATMENT])}, "
     f"PSA {R.fmt_prob(obs_share[CONTROL])}): no sample ratio mismatch")
sub = f"Share of users by group vs the intended {split} split (dashed line)"
s_src = src + "; chi-square goodness-of-fit test"
fig = charts.srm_bar(obs, exp_share, t, sub, s_src, srm["p_value"], ex["threshold"])
save_chart(fig, RUN, "srm_bar", t, f"No sample ratio mismatch vs {split} ({R.fmt_p_stat(srm['p_value'])})", sub, s_src,
           section="validation",
           takeaways=[f"PSA has {R.fmt_num(ex['observed'][CONTROL])} users vs {R.fmt_num(ex['expected_count'][CONTROL])} expected "
                      f"under {split}",
                      f"Chi-square {R.fmt_p_stat(srm['p_value'])} (threshold {ex['threshold']}): the split is as intended",
                      f"The first-stated {orig['split']} split failed ({R.fmt_p_stat(orig['p_value'])}); the user confirmed {split}"],
           notes="speaker note: the groups are the size they were meant to be, so the comparison can be trusted on this check.")

# --------------------------------------------------------------------------- lift_ci
rows = [{**p, "metric": "Ads vs PSA\n(z-test)"},
        {**b, "metric": "Ads vs PSA\n(Bayesian)"}]
qual = "above" if p["rel_ci_low"] > thr else "around"
t = (f"Ads lift conversion by {R.fmt_pct(p['rel_lift'])} vs PSA, statistically significant and "
     f"{qual} the {R.fmt_pct(thr, 0, signed=False)} practical threshold")
sub = f"Relative lift in conversion vs PSA; z-test {ci}, Bayesian {cred} credible interval"
l_src = src + "; two-proportion z-test and beta-binomial model"
fig = charts.lift_ci(rows, t, sub, l_src)
ax = fig.axes[0]
ax.set_xlabel("Relative lift, Ads vs PSA")
ax.axvline(thr, color=PALETTE["grey_mid"], lw=1.2, ls="--", zorder=0)
ax.annotate(f"Practical threshold {R.fmt_pct(thr, 0)}", (thr, ax.get_ylim()[1]), xytext=(4, -4), textcoords="offset points",
            ha="left", va="top", fontsize=SIZES["annotation"], color=PALETTE["grey_mid"])
save_chart(fig, RUN, "lift_ci", t, f"Conversion {R.fmt_pct(p['rel_lift'])} ({R.fmt_p_stat(p['p_value'])})", sub, l_src,
           section="results",
           takeaways=[f"Relative lift {R.fmt_pct(p['rel_lift'])}, {ci} {R.fmt_ci(p['rel_ci_low'], p['rel_ci_high'])}; "
                      f"{R.fmt_p_stat(p['p_value'])}",
                      f"Even the low end ({R.fmt_pct(p['rel_ci_low'])}) is {qual} the {R.fmt_pct(thr, 0, signed=False)} "
                      f"practical threshold",
                      f"Bayesian view agrees: {R.fmt_pct(b['rel_lift'])}, {cred} credible interval "
                      f"{R.fmt_ci(b['rel_ci_low'], b['rel_ci_high'])}"],
           notes="speaker note: the headline - ads clearly raise conversion, by far more than the bar we set.")

# --------------------------------------------------------------------------- metric_by_variant
vs = p["extra"]["variant_stats"]
t = (f"Ads users convert at {R.fmt_value(vs[TREATMENT]['mean'], 'binary')} vs {R.fmt_value(vs[CONTROL]['mean'], 'binary')} "
     f"with PSA: {R.fmt_num(per_k['estimate'], 1)} extra conversions per {R.fmt_num(per_k['extra']['per'])} users, significant")
sub = f"Conversion rate by group, {ci}"
m_src = src + "; two-proportion z-test"
fig = charts.metric_by_variant(rename(vs), t, sub, m_src, control="PSA", metric_type="binary", ylabel="Conversion rate")
fig.axes[0].yaxis.set_major_formatter(PercentFormatter(1.0, decimals=1))   # rates below 3%: whole-percent ticks repeat
save_chart(fig, RUN, "metric_by_variant", t,
           f"{R.fmt_num(per_k['estimate'], 1)} extra conversions per {R.fmt_num(per_k['extra']['per'])} users", sub, m_src,
           section="results",
           takeaways=[f"PSA: {R.fmt_value(vs[CONTROL]['mean'], 'binary')} of {R.fmt_num(vs[CONTROL]['n'])} users converted",
                      f"Ads: {R.fmt_value(vs[TREATMENT]['mean'], 'binary')} of {R.fmt_num(vs[TREATMENT]['n'])} users converted",
                      f"Difference {R.fmt_pp(p['estimate'], 2)}: {R.fmt_num(per_k['estimate'], 1)} extra per "
                      f"{R.fmt_num(per_k['extra']['per'])} users ({ci} {R.fmt_num(per_k['ci_low'], 1)} to "
                      f"{R.fmt_num(per_k['ci_high'], 1)})"],
           notes="speaker note: in plain terms, roughly eight more conversions for every thousand people who see the ads.")
print("results charts saved")
