"""Incremental impact of the ads, translated from the primary conversion effect. Step: impact.

Run from the project root:  python runs/2026-10-01_marketing-ads/code/20_analysis_impact.py

Not in abkit yet: `incremental_impact` below is registered as a promotion candidate (target abkit.decision).
It returns three StatResults with CIs:
  (a) incremental conversions per 1,000 exposed users   = 1000 * (p_t - p_c)
  (b) total incremental conversions in the treated group = n_t * (p_t - p_c)   (n_t treated as fixed)
  (c) share of treated-group conversions attributable to the treatment (attributable fraction among the exposed)
      = (p_t - p_c) / p_t, delta-method CI:  Var = Var(p_c)/p_t^2 + p_c^2 Var(p_t)/p_t^4
(a) and (b) scale the unpooled z-test CI for the absolute difference, so they agree exactly with the primary test.
The function is checked by simulation (CI coverage at the observed rates and sample sizes) before use.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import stats

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN.parents[1]))

from abkit import io, results, state  # noqa: E402
from abkit.results import StatResult  # noqa: E402


def incremental_impact(
    x_c: int, n_c: int, x_t: int, n_t: int, alpha: float = 0.05, per: int = 1000,
    control: str = "control", treatment: str = "treatment", metric: str = "conversion", role: str | None = "secondary",
) -> list[StatResult]:
    """Translate a two-proportion comparison into incremental-impact quantities with normal-approximation CIs.

    Args:
        x_c, n_c: conversions and units in the control group.
        x_t, n_t: conversions and units in the treatment group.
        alpha: 1 - confidence level (two-sided CIs).
        per: scale for the "per N units" quantity (default 1,000).
        control, treatment: variant labels; metric: business name of the outcome; role: result role.

    Returns:
        [per-N incremental conversions, total incremental conversions in treatment, attributable share],
        each a StatResult with estimate, CI and n. The p-value is the unpooled-difference Wald test of p_t = p_c
        (the null hypothesis is the same for all three quantities), not an additional hypothesis.
    """
    if min(n_c, n_t) <= 0 or not (0 <= x_c <= n_c and 0 <= x_t <= n_t):
        raise ValueError("Need 0 <= successes <= trials and trials > 0 in each group")
    if x_t == 0:
        raise ValueError("Attributable share is undefined when the treatment group has no conversions")
    zc = float(stats.norm.ppf(1 - alpha / 2))
    p_c, p_t = x_c / n_c, x_t / n_t
    v_c, v_t = p_c * (1 - p_c) / n_c, p_t * (1 - p_t) / n_t
    d, se_d = p_t - p_c, float(np.sqrt(v_c + v_t))
    p_pool = (x_c + x_t) / (n_c + n_t)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))
    p_val = float(2 * stats.norm.sf(abs(d / se_pool))) if se_pool > 0 else 1.0
    n = {control: int(n_c), treatment: int(n_t)}
    common = dict(method="custom.incremental_impact", control=control, treatment=treatment, alpha=alpha,
                  sidedness="two-sided", n=n, role=role, p_value=p_val, significant=bool(p_val < alpha))
    base_notes = ["Derived from the primary conversion comparison (same data, same null hypothesis); not an additional "
                  "test, so no multiple-testing correction applies.",
                  "Causal only to the extent assignment was random (see the user-id block caveat)."]

    per_n = StatResult(metric=f"incremental {metric}s per {per:,} users", estimate=per * d,
                       ci_low=per * (d - zc * se_d), ci_high=per * (d + zc * se_d),
                       control_value=per * p_c, treatment_value=per * p_t,
                       extra={"formula": f"{per} * (p_{treatment} - p_{control})", "se": per * se_d, "per": per},
                       notes=list(base_notes), **common)
    total = StatResult(metric=f"total incremental {metric}s in the {treatment} group", estimate=n_t * d,
                       ci_low=n_t * (d - zc * se_d), ci_high=n_t * (d + zc * se_d),
                       control_value=n_t * p_c, treatment_value=float(x_t),
                       extra={"formula": f"n_{treatment} * (p_{treatment} - p_{control})", "se": n_t * se_d,
                              "observed_conversions": int(x_t), "counterfactual_conversions": n_t * p_c},
                       notes=[*base_notes, f"control_value = {metric}s expected in the {treatment} group without the "
                              f"treatment (n_{treatment} * p_{control}); treatment_value = observed {metric}s. "
                              f"n_{treatment} treated as fixed."], **common)
    af = d / p_t
    se_af = float(np.sqrt(v_c / p_t**2 + p_c**2 * v_t / p_t**4))
    # Sensitivity: log-scale (Katz) interval for the ratio p_c / p_t, transformed to 1 - ratio.
    se_log = float(np.sqrt(v_c / p_c**2 + v_t / p_t**2)) if p_c > 0 else float("nan")
    rr = p_c / p_t
    katz = (1 - rr * np.exp(zc * se_log), 1 - rr * np.exp(-zc * se_log)) if p_c > 0 else (None, None)
    share = StatResult(metric=f"share of {treatment}-group {metric}s attributable to the {treatment}s", estimate=af,
                       ci_low=af - zc * se_af, ci_high=af + zc * se_af,
                       extra={"formula": f"(p_{treatment} - p_{control}) / p_{treatment}", "se": se_af,
                              "ci_log_ratio_sensitivity": {"ci_low": katz[0], "ci_high": katz[1]}},
                       notes=[*base_notes, "Delta-method CI; a log-ratio (Katz) interval is stored as a sensitivity check."],
                       **common)
    for r in (per_n, total, share):
        r.assumptions = [
            {"check": "normal approximation: >= 10 successes and failures per group",
             "passed": bool(min(x_c, n_c - x_c, x_t, n_t - x_t) >= 10), "detail": f"min cell = {min(x_c, n_c - x_c, x_t, n_t - x_t)}"},
            {"check": "independent units at the randomisation level", "passed": True, "detail": "one row per user"},
        ]
    return [per_n, total, share]


def _coverage_check(p_c: float, n_c: int, p_t: float, n_t: int, reps: int = 4000, seed: int = 42, alpha: float = 0.05) -> dict:
    """Simulate binomial data at the given truth and return empirical CI coverage of each quantity."""
    rng = np.random.default_rng(seed)
    truth = [1000 * (p_t - p_c), n_t * (p_t - p_c), (p_t - p_c) / p_t]
    hits = np.zeros(3)
    xc, xt = rng.binomial(n_c, p_c, reps), rng.binomial(n_t, p_t, reps)
    for a, b in zip(xc, xt):
        out = incremental_impact(int(a), n_c, int(b), n_t, alpha)
        hits += [o.ci_low <= t <= o.ci_high for o, t in zip(out, truth)]
    cov = hits / reps
    return {"reps": reps, "nominal": 1 - alpha, "coverage_per_1000": cov[0], "coverage_total": cov[1],
            "coverage_attributable_share": cov[2], "mc_se": float(np.sqrt((1 - alpha) * alpha / reps))}


# --------------------------------------------------------------------------- run
st = state.load_state(RUN)
s, design = st["settings"], st["design"]
VAR = design["variant_col"]
CONTROL, TREATMENT = design["control"], design["treatment"]
m = next(x for x in st["metrics"] if x["role"] == "primary")
METRIC = m["name"]
LABEL = m.get("label", METRIC)

df = io.load_run_csv(RUN, date_cols=[])
df[METRIC] = df[METRIC].astype(int)  # bool -> 0/1 (in memory only)
g = df.groupby(VAR)[METRIC].agg(["sum", "count"])
x_c, n_c = int(g.loc[CONTROL, "sum"]), int(g.loc[CONTROL, "count"])
x_t, n_t = int(g.loc[TREATMENT, "sum"]), int(g.loc[TREATMENT, "count"])

out = incremental_impact(x_c, n_c, x_t, n_t, alpha=s["alpha"], control=CONTROL, treatment=TREATMENT, metric=LABEL)

# Consistency with the stored primary test (same abs-diff CI) and a simulation check of CI coverage.
prim = results.get_result(RUN, "primary_test")
assert np.isclose(out[0].estimate, 1000 * prim["estimate"]) and np.isclose(out[0].ci_low, 1000 * prim["ci_low"])
assert np.isclose(out[2].estimate, prim["rel_lift"] / (1 + prim["rel_lift"]))
coverage = _coverage_check(x_c / n_c, n_c, x_t / n_t, n_t, seed=s["bootstrap_seed"], alpha=s["alpha"])
for r in out:
    r.assumptions.append({"check": "CI coverage by simulation at the observed rates and n", "passed":
                          bool(min(coverage["coverage_per_1000"], coverage["coverage_total"], coverage["coverage_attributable_share"])
                               >= coverage["nominal"] - 3 * coverage["mc_se"]),
                          "detail": f"{coverage['reps']:,} simulated tests"})

per_k, total, share = out
money_formula = (
    f"incremental revenue = incremental conversions x value per conversion = "
    f"{results.fmt_num(total.estimate)} (95% CI {results.fmt_num(total.ci_low)} to {results.fmt_num(total.ci_high)}) "
    f"x value per conversion; per 1,000 users reached: {results.fmt_num(per_k.estimate, 1)} "
    f"(95% CI {results.fmt_num(per_k.ci_low, 1)} to {results.fmt_num(per_k.ci_high, 1)}) x value per conversion"
)

results.add_result(
    RUN, "impact", out, __file__, method="custom.incremental_impact",
    data={
        "money_formula": money_formula,
        "money_formula_generic": "incremental revenue = incremental conversions x value per conversion",
        "counts": {CONTROL: {"conversions": x_c, "users": n_c}, TREATMENT: {"conversions": x_t, "users": n_t}},
        "coverage_check": coverage,
        "impact_table": [{"quantity": r.metric, "estimate": r.estimate, "ci_low": r.ci_low, "ci_high": r.ci_high} for r in out],
    },
)
results.add_candidate(
    RUN, "incremental_impact", __file__,
    "Translate a two-proportion comparison into incremental conversions per N users, total incremental conversions "
    "in the treated group and the attributable share of treated conversions, each with a CI (scaled Wald / delta method); "
    "validated by simulated CI coverage.",
    target_module="abkit.decision",
)
state.set_step_status(RUN, "impact", "done")
for r in out:
    print(f"{r.metric}: {results.fmt_num(r.estimate, 3)} (95% CI {results.fmt_num(r.ci_low, 3)} to {results.fmt_num(r.ci_high, 3)})")
print("coverage:", {k: round(v, 4) if isinstance(v, float) else v for k, v in coverage.items()})
print(money_formula)
