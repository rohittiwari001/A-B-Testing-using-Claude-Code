"""Sequential testing: group-sequential boundaries (alpha spending) and mSPRT.

Peeking at a fixed-horizon test and stopping at the first p < 0.05 inflates the
false-positive rate (see :func:`peeking_simulation`). Two remedies:

1. Group-sequential design: pre-plan K looks; Lan-DeMets spending functions
   (O'Brien-Fleming-type or Pocock-type) give z boundaries per look.
   Boundaries are computed exactly by recursive numerical integration.
2. Always-valid inference (mixture SPRT, Johari et al. 2017): p-values and CIs
   that stay valid under continuous monitoring.

Example
-------
>>> from abkit.sequential import boundaries
>>> b = boundaries([0.2, 0.4, 0.6, 0.8, 1.0], alpha=0.05, kind="obrien-fleming")
>>> [round(z, 2) for z in b["z_boundary"]]
[4.88, 3.36, 2.68, 2.29, 2.03]
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from scipy import optimize, stats

from abkit.results import StatResult

KINDS = ("obrien-fleming", "pocock")


def spending(t: float | np.ndarray, alpha: float = 0.05, kind: str = "obrien-fleming") -> np.ndarray:
    """Cumulative two-sided alpha spent by information fraction ``t`` (Lan-DeMets).

    Symmetric two-sided design: alpha/2 is spent per side, the convention used by
    gsDesign, rpact and ldbounds (so boundaries match those packages).
    """
    t = np.clip(np.asarray(t, dtype=float), 1e-12, 1.0)
    if kind == "obrien-fleming":
        return 2 * (2 - 2 * stats.norm.cdf(stats.norm.ppf(1 - alpha / 4) / np.sqrt(t)))
    if kind == "pocock":
        return alpha * np.log(1 + (np.e - 1) * t)
    raise ValueError(f"kind must be one of {KINDS}")


def _grid(c: float, t: float, m: int) -> np.ndarray:
    return np.linspace(-c * np.sqrt(t), c * np.sqrt(t), m)


def boundaries(info_fractions: Sequence[float], alpha: float = 0.05, kind: str = "obrien-fleming", grid: int = 801) -> pd.DataFrame:
    """Symmetric two-sided z boundaries for each look.

    Works on the Brownian-motion scale B(t) = Z(t) * sqrt(t): the density of B inside the
    continuation region is propagated look to look, and each boundary is solved so the
    probability of first crossing at that look equals the alpha spent in that interval.
    """
    t = np.asarray(info_fractions, dtype=float)
    if np.any(np.diff(t) <= 0) or t[0] <= 0 or t[-1] > 1 + 1e-9:
        raise ValueError("info_fractions must be increasing in (0, 1]")
    cum = spending(t, alpha, kind)
    inc = np.diff(np.concatenate([[0.0], cum]))
    zs = [float(stats.norm.ppf(1 - cum[0] / 2))]
    b = _grid(zs[0], t[0], grid)
    f = stats.norm.pdf(b, scale=np.sqrt(t[0]))          # density of B(t1) on continuation region
    for k in range(1, len(t)):
        dt = t[k] - t[k - 1]
        sd = np.sqrt(dt)
        w = np.full(b.size, b[1] - b[0])                 # trapezoid weights for the integral
        w[[0, -1]] /= 2

        def cross_prob(c: float) -> float:
            upper = c * np.sqrt(t[k])
            p_out = stats.norm.sf((upper - b) / sd) + stats.norm.cdf((-upper - b) / sd)
            return float(np.sum(f * p_out * w))

        target = inc[k]
        c_k = optimize.brentq(lambda c: cross_prob(c) - target, 0.5, 12.0)
        zs.append(float(c_k))
        new_b = _grid(c_k, t[k], grid)
        kern = stats.norm.pdf((new_b[:, None] - b[None, :]) / sd) / sd
        f = kern @ (f * w)
        b = new_b
    zs_arr = np.array(zs)
    return pd.DataFrame({"look": np.arange(1, len(t) + 1), "info_fraction": t, "cum_alpha": cum,
                         "z_boundary": zs_arr, "nominal_p": 2 * stats.norm.sf(zs_arr)})


def group_sequential_test(z_values: Sequence[float], info_fractions: Sequence[float], alpha: float = 0.05,
                          kind: str = "obrien-fleming", planned_fractions: Sequence[float] | None = None) -> StatResult:
    """Compare observed z statistics at each look with the boundaries.

    ``planned_fractions`` defaults to ``info_fractions`` (boundaries are recomputed for
    the actual information at each look, which the spending approach allows).
    """
    fr = planned_fractions or info_fractions
    bnd = boundaries(fr, alpha, kind)
    z = np.asarray(z_values, dtype=float)
    k = len(z)
    crossed = np.abs(z) >= bnd["z_boundary"].to_numpy()[:k]
    stop_at = int(np.argmax(crossed)) + 1 if crossed.any() else None
    table = bnd.iloc[:k].assign(z_observed=z, crossed=crossed)
    return StatResult(
        method=f"sequential.group_sequential_{kind}", estimate=float(z[-1]), alpha=alpha, sidedness="two-sided",
        significant=stop_at is not None,
        extra={"stopped_at_look": stop_at, "looks_done": k, "looks_planned": len(fr), "table": table.to_dict(orient="records")},
        notes=[f"Efficacy boundary crossed at look {stop_at}." if stop_at else
               f"No boundary crossed after {k} of {len(fr)} looks; continue to the next planned look."],
    )


# --------------------------------------------------------------------------- mSPRT


def msprt(diff: float, var_diff: float, tau: float, alpha: float = 0.05) -> dict[str, float]:
    """Mixture SPRT statistic for one look.

    ``diff`` = observed treatment - control, ``var_diff`` = its variance, ``tau`` = SD of the
    N(0, tau^2) mixing distribution over true effects (set it near the effect size you expect).
    Returns the likelihood ratio, 1/LR (a one-look always-valid p before the running minimum),
    and the always-valid CI half-width.
    """
    v, t2 = var_diff, tau**2
    lr = np.sqrt(v / (v + t2)) * np.exp(diff**2 * t2 / (2 * v * (v + t2)))
    half = np.sqrt(v * (v + t2) / t2 * (2 * np.log(1 / alpha) + np.log((v + t2) / v)))
    return {"lr": float(lr), "p": float(min(1.0, 1 / lr)), "half_width": float(half)}


def msprt_path(df: pd.DataFrame, metric: str, date_col: str, variant_col: str, control: str, treatment: str,
               alpha: float = 0.05, tau_rel: float = 0.05, metric_type: str = "binary") -> StatResult:
    """Always-valid p-values and CIs computed after each day of data (cumulative).

    ``tau_rel`` sets tau as a share of the control mean (0.05 -> effects around +/-5% expected).
    The always-valid p is the running minimum of 1/LR; the CI is the running intersection.
    """
    d = df.copy()
    d["_day"] = pd.to_datetime(d[date_col]).dt.normalize()
    rows, p_run, lo_run, hi_run = [], 1.0, -np.inf, np.inf
    tau = None
    for day in sorted(d["_day"].unique()):
        cum = d[d["_day"] <= day]
        c = cum.loc[cum[variant_col].astype(str) == str(control), metric].astype(float)
        t = cum.loc[cum[variant_col].astype(str) == str(treatment), metric].astype(float)
        if len(c) < 2 or len(t) < 2:
            continue
        diff = t.mean() - c.mean()
        var = c.var(ddof=1) / len(c) + t.var(ddof=1) / len(t)
        if tau is None:
            tau = max(tau_rel * abs(c.mean()), 1e-12)
        m = msprt(diff, var, tau, alpha)
        p_run = min(p_run, m["p"])
        lo_run, hi_run = max(lo_run, diff - m["half_width"]), min(hi_run, diff + m["half_width"])
        naive_p = float(2 * stats.norm.sf(abs(diff) / np.sqrt(var)))
        rows.append({"date": pd.Timestamp(day).date().isoformat(), "n_control": len(c), "n_treatment": len(t),
                     "diff": float(diff), "always_valid_p": p_run, "ci_low": lo_run, "ci_high": hi_run, "naive_p": naive_p})
    if not rows:
        raise ValueError("Not enough data for any look")
    last = rows[-1]
    mc = float(df.loc[df[variant_col].astype(str) == str(control), metric].mean())
    return StatResult(
        method="sequential.msprt", metric=metric, control=control, treatment=treatment, estimate=last["diff"],
        ci_low=last["ci_low"], ci_high=last["ci_high"], p_value=last["always_valid_p"], alpha=alpha, sidedness="two-sided",
        significant=last["always_valid_p"] < alpha, control_value=mc,
        rel_lift=last["diff"] / mc if mc else None,
        rel_ci_low=last["ci_low"] / mc if mc else None, rel_ci_high=last["ci_high"] / mc if mc else None,
        n={control: last["n_control"], treatment: last["n_treatment"]},
        extra={"tau": tau, "tau_rel": tau_rel, "path": rows,
               "first_significant_date": next((r["date"] for r in rows if r["always_valid_p"] < alpha), None),
               "first_naive_significant_date": next((r["date"] for r in rows if r["naive_p"] < alpha), None)},
        notes=["Always-valid (mSPRT) inference: valid no matter how often the results were checked."],
    )


def peeking_simulation(n_looks: int = 14, n_per_look: int = 500, alpha: float = 0.05, n_sims: int = 2000, seed: int = 0) -> dict[str, float]:
    """A/A simulation: false-positive rate when stopping at the first naive p < alpha across ``n_looks``."""
    rng = np.random.default_rng(seed)
    zc = stats.norm.ppf(1 - alpha / 2)
    inc = rng.normal(size=(n_sims, n_looks)) * np.sqrt(2 / n_per_look)   # per-look increments of the mean difference
    sums = np.cumsum(inc * n_per_look, axis=1)
    n = n_per_look * np.arange(1, n_looks + 1)
    z = (sums / n) / np.sqrt(2 / n)
    return {"fixed_horizon_fpr": float((np.abs(z[:, -1]) > zc).mean()), "peeking_fpr": float((np.abs(z) > zc).any(axis=1).mean()),
            "n_looks": n_looks}
