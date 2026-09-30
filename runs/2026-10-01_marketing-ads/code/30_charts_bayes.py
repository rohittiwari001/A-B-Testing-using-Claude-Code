"""Charts for 2026-10-01_marketing-ads: posterior_distributions, prob_to_beat_control (numbers from results.json).

Run from the project root:  python runs/2026-10-01_marketing-ads/code/30_charts_bayes.py
Display names for stakeholders: "Ads" (data label `ad`) and "PSA" (data label `psa`).
"""

import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN.parents[1]))

from abkit import results as R  # noqa: E402
from abkit import state  # noqa: E402
from abkit.viz import apply_style, charts, save_chart  # noqa: E402

apply_style()
res = R.load_results(RUN)
st = state.load_state(RUN)
design, settings = st["design"], st["settings"]
CONTROL, TREATMENT = design["control"], design["treatment"]
NAMES = {TREATMENT: "Ads", CONTROL: "PSA"}
alpha = settings["alpha"]
csv_name = Path(st["input_csv"]).name
DISPLAY_CAP = 0.999          # probabilities above this are shown as "> 99.9%" (never "100%")


def rename(d):
    return {NAMES[k]: d[k] for k in (CONTROL, TREATMENT)}


def prob_txt(x):
    return f"> {R.fmt_prob(DISPLAY_CAP)}" if x > DISPLAY_CAP else R.fmt_prob(x)


b = R.get_result(res, "bayesian")
bx = b["extra"]
bdata = R.get_step(res, "bayesian")["data"]
cred = f"{bx.get('credible_level', 1 - alpha):.0%}"
prior = bx["prior"]
n_total = sum(b["n"].values())
src = (f"Source: {csv_name} (test dates not recorded); beta-binomial model, Beta({R.fmt_num(prior['a'])}, "
       f"{R.fmt_num(prior['b'])}) prior; n = {n_total:,} users")
p_beat = bdata["prob_to_beat_control"]["probability"]
threshold = bdata["prob_to_beat_control"].get("threshold", settings["bayes_decision_threshold"])
thr_rel = bx["practical_threshold_rel"]
vs = bx["variant_stats"]

# --------------------------------------------------------------------------- posterior_distributions
t = (f"Plausible conversion rates for Ads and PSA do not overlap: Ads beat PSA with {prob_txt(p_beat)} probability")
sub = f"Posterior distribution of the conversion rate by group; label = posterior mean"
fig = charts.posterior_distributions(rename(bx["posteriors"]), t, sub, src, control="PSA", metric_type="binary")
fig.axes[0].set_xlabel("Plausible conversion rate (posterior)")
save_chart(fig, RUN, "posterior_distributions", t, f"P(Ads beat PSA) {prob_txt(p_beat)}", sub, src, section="results",
           takeaways=[f"PSA: {R.fmt_value(vs[CONTROL]['mean'], 'binary')}, {cred} credible interval "
                      f"{R.fmt_value(vs[CONTROL]['ci_low'], 'binary')} to {R.fmt_value(vs[CONTROL]['ci_high'], 'binary')}",
                      f"Ads: {R.fmt_value(vs[TREATMENT]['mean'], 'binary')}, {cred} credible interval "
                      f"{R.fmt_value(vs[TREATMENT]['ci_low'], 'binary')} to {R.fmt_value(vs[TREATMENT]['ci_high'], 'binary')}",
                      f"The ranges are fully separated; the flat prior carries negligible weight at this sample size"],
           notes="speaker note: the Ads curve sits entirely to the right of the PSA curve - no plausible world where PSA wins.")

# --------------------------------------------------------------------------- prob_to_beat_control
t = (f"Ads beat PSA on conversion with {prob_txt(p_beat)} probability, above the "
     f"{R.fmt_pct(threshold, 0, signed=False)} decision threshold")
sub = "Posterior probability that Ads convert better than PSA"
fig = charts.prob_to_beat_control({"Ads": p_beat}, t, sub, src, threshold=threshold)
ax = fig.axes[0]
for txt in ax.texts:                       # bar label: show a capped probability instead of a rounded "100.0%"
    if txt.get_text() == R.fmt_prob(p_beat) and p_beat > DISPLAY_CAP:
        txt.set_text(prob_txt(p_beat))
ax.set_xlabel("Probability that Ads beat PSA")
loss_psa = bx["expected_loss_control"]
save_chart(fig, RUN, "prob_to_beat_control", t, f"P(Ads beat PSA) {prob_txt(p_beat)}", sub, src, section="results",
           takeaways=[f"P(Ads beat PSA) {prob_txt(p_beat)} vs a {R.fmt_pct(threshold, 0, signed=False)} decision threshold",
                      f"P(lift above the {R.fmt_pct(thr_rel, 0, signed=False)} practical threshold) "
                      f"{prob_txt(bx['prob_rel_lift_above_threshold'])}",
                      f"Staying with PSA would cost an expected {R.fmt_pp(loss_psa, 2).lstrip('+')} of conversion"],
           notes="speaker note: the Bayesian decision rule says ship - the chance ads are worse than PSA is negligible.")
print("bayes charts saved")
