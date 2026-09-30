"""Quasi-experiments for when randomisation was not possible.

- :func:`diff_in_diff` - two-way fixed-effects DiD with unit-clustered SEs.
- :func:`parallel_trends_test` - pre-period differential trend test (the key DiD assumption).
- :func:`group_trends` - treated vs control means over time (for the did_trends chart).
- :func:`interrupted_time_series` - segmented regression with HAC (Newey-West) SEs.
- :func:`synthetic_control` - convex donor weights fitted on the pre-period, placebo p-value.

Example
-------
>>> from abkit.quasi import diff_in_diff
>>> r = diff_in_diff(df, "orders", "rolled_out", "post_launch", unit_col="region", time_col="week")  # doctest: +SKIP
>>> round(r.rel_lift, 3)                                                                            # doctest: +SKIP
0.04
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from scipy import optimize, stats

from abkit.results import StatResult


def diff_in_diff(
    df: pd.DataFrame, outcome: str, treated_col: str, post_col: str, unit_col: str | None = None,
    time_col: str | None = None, log: bool = False, alpha: float = 0.05,
) -> StatResult:
    """DiD estimate of the effect of treatment on the treated.

    With ``unit_col`` and ``time_col`` it fits unit and time fixed effects (TWFE) and clusters
    SEs by unit; otherwise the classic 2x2 regression. ``log=True`` models log(outcome) so the
    effect is relative (``rel_lift`` = exp(b) - 1).
    """
    import statsmodels.formula.api as smf

    d = df.copy()
    y = f"np.log(Q('{outcome}'))" if log else f"Q('{outcome}')"
    d["_did"] = d[treated_col].astype(float) * d[post_col].astype(float)
    if unit_col and time_col:
        formula = f"{y} ~ _did + C({unit_col}) + C({time_col})"
        fit = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d[unit_col])[0]})
        n_clusters = d[unit_col].nunique()
    else:
        formula = f"{y} ~ Q('{treated_col}') + Q('{post_col}') + _did"
        fit = smf.ols(formula, data=d).fit(cov_type="HC1")
        n_clusters = None
    b, se = float(fit.params["_did"]), float(fit.bse["_did"])
    lo, hi = fit.conf_int(alpha).loc["_did"]
    tp = d[(d[treated_col] == 1) & (d[post_col] == 1)][outcome].mean()
    if log:
        rel, rlo, rhi = np.exp(b) - 1, np.exp(lo) - 1, np.exp(hi) - 1
        counterfactual = tp / np.exp(b)
    else:
        counterfactual = tp - b
        rel, rlo, rhi = b / counterfactual, lo / counterfactual, hi / counterfactual
    r = StatResult(
        method="quasi.diff_in_diff", metric=outcome, estimate=b, ci_low=float(lo), ci_high=float(hi), p_value=float(fit.pvalues["_did"]),
        control="counterfactual", treatment="treated", control_value=float(counterfactual), treatment_value=float(tp),
        rel_lift=float(rel), rel_ci_low=float(rlo), rel_ci_high=float(rhi), alpha=alpha, sidedness="two-sided",
        significant=bool(fit.pvalues["_did"] < alpha),
        n={"treated_units": int(d.loc[d[treated_col] == 1, unit_col].nunique()) if unit_col else int((d[treated_col] == 1).sum()),
           "control_units": int(d.loc[d[treated_col] == 0, unit_col].nunique()) if unit_col else int((d[treated_col] == 0).sum())},
        assumptions=[{"check": "parallel trends in the pre-period", "passed": None, "detail": "see parallel_trends_test"},
                     {"check": "no anticipation / spillover to control units", "passed": None, "detail": "domain judgement"}],
        extra={"se": se, "log": log, "clusters": n_clusters, "specification": formula},
    )
    if n_clusters is not None and n_clusters < 30:
        r.notes.append(f"Only {n_clusters} clusters: cluster-robust SEs can be too small; consider a placebo/permutation check.")
    return r


def parallel_trends_test(
    df: pd.DataFrame, outcome: str, treated_col: str, time_col: str, post_col: str, unit_col: str | None = None,
    log: bool = False, alpha: float = 0.05,
) -> StatResult:
    """Pre-period only: does the treated group trend differently? (treated x linear time)."""
    import statsmodels.formula.api as smf

    d = df[df[post_col] == 0].copy()
    d["_time"] = d[time_col].astype(float)
    y = f"np.log(Q('{outcome}'))" if log else f"Q('{outcome}')"
    kw = {"cov_type": "cluster", "cov_kwds": {"groups": pd.factorize(d[unit_col])[0]}} if unit_col else {"cov_type": "HC1"}
    fe = f" + C({unit_col})" if unit_col else f" + Q('{treated_col}')"
    fit = smf.ols(f"{y} ~ C({time_col}){fe} + Q('{treated_col}'):_time", data=d).fit(**kw)
    name = f"Q('{treated_col}'):_time"
    p = float(fit.pvalues[name])
    return StatResult(
        method="quasi.parallel_trends_test", metric=outcome, estimate=float(fit.params[name]), p_value=p, alpha=alpha,
        significant=p < alpha, ci_low=float(fit.conf_int(alpha).loc[name][0]), ci_high=float(fit.conf_int(alpha).loc[name][1]),
        notes=["Differential pre-trend detected: DiD estimate is likely biased." if p < alpha
               else "No evidence of differential pre-trends (absence of evidence, not proof)."],
        extra={"pre_periods": int(d[time_col].nunique())},
    )


def group_trends(df: pd.DataFrame, outcome: str, treated_col: str, time_col: str, index_to_pre: bool = False,
                 post_col: str | None = None) -> pd.DataFrame:
    """Mean outcome per period for treated and control groups (optionally indexed to pre-period mean = 100)."""
    t = df.groupby([time_col, treated_col])[outcome].mean().unstack()
    t.columns = ["control" if c == 0 else "treated" for c in t.columns]
    if index_to_pre and post_col:
        pre_periods = df.loc[df[post_col] == 0, time_col].unique()
        t = t / t.loc[t.index.isin(pre_periods)].mean() * 100
    return t.reset_index()


def interrupted_time_series(
    df: pd.DataFrame, time_col: str, outcome: str, intervention, alpha: float = 0.05, maxlags: int = 2,
) -> StatResult:
    """Segmented regression: y = b0 + b1*t + b2*post + b3*(t - t0)*post, Newey-West SEs.

    ``estimate`` is the immediate level change (b2); ``extra['slope_change']`` is b3.
    """
    import statsmodels.api as sm

    d = df[[time_col, outcome]].dropna().sort_values(time_col).reset_index(drop=True)
    t = np.arange(len(d), dtype=float)
    post = (d[time_col] >= intervention).to_numpy().astype(float)
    if post.sum() == 0 or post.sum() == len(d):
        raise ValueError("Intervention must fall inside the series")
    t0 = t[post.argmax()]
    X = sm.add_constant(np.column_stack([t, post, (t - t0) * post]))
    fit = sm.OLS(d[outcome].to_numpy(float), X).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    b = fit.params
    ci = fit.conf_int(alpha)
    cf = b[0] + b[1] * t[post == 1]
    actual = d[outcome].to_numpy(float)[post == 1]
    return StatResult(
        method="quasi.interrupted_time_series", metric=outcome, estimate=float(b[2]), ci_low=float(ci[2][0]), ci_high=float(ci[2][1]),
        p_value=float(fit.pvalues[2]), alpha=alpha, significant=bool(fit.pvalues[2] < alpha),
        control_value=float(cf.mean()), treatment_value=float(actual.mean()), rel_lift=float(actual.mean() / cf.mean() - 1),
        extra={"slope_change": float(b[3]), "slope_change_p": float(fit.pvalues[3]), "pre_slope": float(b[1]),
               "series": [{"t": str(d[time_col].iloc[i]), "actual": float(d[outcome].iloc[i]),
                           "fitted_counterfactual": float(b[0] + b[1] * t[i])} for i in range(len(d))]},
        assumptions=[{"check": "no other change coincides with the intervention", "passed": None, "detail": "domain judgement"}],
    )


def synthetic_control(
    df: pd.DataFrame, unit_col: str, time_col: str, outcome: str, treated_units: Sequence[str], intervention,
    placebo: bool = True,
) -> StatResult:
    """Basic synthetic control on the average of ``treated_units``.

    Donor weights are non-negative and sum to 1, fitted to minimise pre-period MSE. The
    placebo p-value ranks the treated post/pre RMSPE ratio among donors given the same treatment.
    """
    wide = df.pivot_table(index=time_col, columns=unit_col, values=outcome).sort_index()
    treated_units = [str(u) for u in treated_units]
    wide.columns = [str(c) for c in wide.columns]
    donors = [c for c in wide.columns if c not in treated_units]
    pre = wide.index < intervention
    if pre.sum() < 3:
        raise ValueError("Need at least 3 pre-intervention periods")

    def fit_weights(target: np.ndarray, pool: np.ndarray) -> np.ndarray:
        k = pool.shape[1]
        obj = lambda w: np.mean((target - pool @ w) ** 2)
        res = optimize.minimize(obj, np.full(k, 1 / k), method="SLSQP", bounds=[(0, 1)] * k,
                                constraints={"type": "eq", "fun": lambda w: w.sum() - 1})
        return res.x

    def gap_stats(target_name: str | None, target: np.ndarray, pool_cols: list[str]):
        pool = wide[pool_cols].to_numpy()
        w = fit_weights(target[pre], pool[pre])
        synth = pool @ w
        gap = target - synth
        ratio = np.sqrt(np.mean(gap[~pre] ** 2)) / max(np.sqrt(np.mean(gap[pre] ** 2)), 1e-12)
        return w, synth, gap, ratio

    y = wide[treated_units].mean(axis=1).to_numpy()
    w, synth, gap, ratio = gap_stats(None, y, donors)
    p = None
    if placebo and len(donors) >= 4:
        ratios = [gap_stats(dn, wide[dn].to_numpy(), [c for c in donors if c != dn])[3] for dn in donors]
        p = float((1 + sum(r >= ratio for r in ratios)) / (1 + len(ratios)))
    effect = float(gap[~pre].mean())
    return StatResult(
        method="quasi.synthetic_control", metric=outcome, estimate=effect, p_value=p, control="synthetic", treatment="treated",
        control_value=float(synth[~pre].mean()), treatment_value=float(y[~pre].mean()),
        rel_lift=float(y[~pre].mean() / synth[~pre].mean() - 1),
        extra={"weights": {d: float(x) for d, x in zip(donors, w) if x > 0.001},
               "pre_rmspe": float(np.sqrt(np.mean(gap[pre] ** 2))), "post_pre_rmspe_ratio": float(ratio),
               "series": [{"t": str(i), "treated": float(a), "synthetic": float(s)} for i, a, s in zip(wide.index, y, synth)]},
        notes=["Placebo-in-space p-value (rank of post/pre RMSPE ratio)." if p is not None else "Too few donors for a placebo test."],
    )
