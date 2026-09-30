"""Bayesian readout of conversion (ads vs PSA): beta-binomial, prior from settings. Step: bayesian.

Run from the project root:  python runs/2026-10-01_marketing-ads/code/20_analysis_bayesian.py
Same counts as the primary z-test. Posteriors (Beta parameters) are stored in extra and data for the
posterior_distributions and prob_to_beat_control charts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import stats

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN.parents[1]))

from abkit import bayesian, io, results, state  # noqa: E402

st = state.load_state(RUN)
s, design = st["settings"], st["design"]
VAR = design["variant_col"]
CONTROL, TREATMENT = design["control"], design["treatment"]
m = next(x for x in st["metrics"] if x["role"] == "primary")
METRIC, DIRECTION = m["name"], m["direction"]

df = io.load_run_csv(RUN, date_cols=[])
df[METRIC] = df[METRIC].astype(int)  # bool -> 0/1 (in memory only)
g = df.groupby(VAR)[METRIC].agg(["sum", "count"])
x_c, n_c = int(g.loc[CONTROL, "sum"]), int(g.loc[CONTROL, "count"])
x_t, n_t = int(g.loc[TREATMENT, "sum"]), int(g.loc[TREATMENT, "count"])

cred = s["confidence_level"]
r = bayesian.beta_binomial(x_c, n_c, x_t, n_t, prior=s["bayes_prior"], cred=cred, seed=s["bootstrap_seed"],
                           direction=DIRECTION, metric=METRIC, control=CONTROL, treatment=TREATMENT)
r.role = "secondary"
decision = bayesian.decide(r, threshold=s["bayes_decision_threshold"])
r.extra["decision"] = decision
r.extra["decision_threshold"] = s["bayes_decision_threshold"]
threshold = m.get("practical_threshold_rel")

# P(relative lift >= practical threshold), from the same posterior draws the summary used (same seed).
rng = np.random.default_rng(s["bootstrap_seed"])
post = r.extra["posteriors"]
pc = rng.beta(post[CONTROL]["a"], post[CONTROL]["b"], 200_000)
pt = rng.beta(post[TREATMENT]["a"], post[TREATMENT]["b"], 200_000)
rel_draws = pt / pc - 1
r.extra["prob_rel_lift_above_threshold"] = float((rel_draws >= threshold).mean())
r.extra["practical_threshold_rel"] = threshold
r.assumptions.append({"check": "prior chosen before seeing results (settings.bayes_prior)", "passed": True,
                      "detail": f"{s['bayes_prior']} -> Beta({r.extra['prior']['a']:g}, {r.extra['prior']['b']:g})"})
srm = results.get_result(RUN, "srm")
r.assumptions.append({"check": "no sample ratio mismatch vs intended split", "passed": not bool(srm.get("significant")),
                      "detail": f"SRM {results.fmt_p_stat(srm.get('p_value'))} (step srm, threshold {s['srm_threshold']})"})
r.alpha = round(r.alpha, 10)  # 1 - credible level, without floating-point noise
r.notes.append("Prior sensitivity: without a historical baseline the weakly informative prior is Beta(1, 1), identical to the "
               "flat prior, so a flat-prior rerun gives the same answer. With this many users the prior has negligible weight.")

# Density curves for the posterior_distributions chart (numbers only from this model).
lo = min(stats.beta.ppf(1e-4, post[k]["a"], post[k]["b"]) for k in (CONTROL, TREATMENT))
hi = max(stats.beta.ppf(1 - 1e-4, post[k]["a"], post[k]["b"]) for k in (CONTROL, TREATMENT))
grid = np.linspace(lo, hi, 300)
dens = {k: stats.beta.pdf(grid, post[k]["a"], post[k]["b"]) for k in (CONTROL, TREATMENT)}
hist, edges = np.histogram(rel_draws, bins=80)

results.add_result(
    RUN, "bayesian", r, __file__, method="bayesian.beta_binomial",
    data={
        "posteriors": post, "prior": r.extra["prior"],
        "posterior_density": {"x": grid, **{k: v for k, v in dens.items()}},
        "rel_lift_hist": {"counts": hist, "edges": edges},
        "prob_to_beat_control": {"variant": TREATMENT, "probability": r.probability,
                                 "threshold": s["bayes_decision_threshold"]},
        "counts": {CONTROL: {"conversions": x_c, "users": n_c}, TREATMENT: {"conversions": x_t, "users": n_t}},
    },
)
state.set_step_status(RUN, "bayesian", "done")
print(results.describe(r.to_dict()))
print(f"expected loss (rel) {r.extra['expected_loss_treatment_rel']:.2e}; decision {decision}; "
      f"P(rel lift >= {threshold}) = {r.extra['prob_rel_lift_above_threshold']:.4f}")
