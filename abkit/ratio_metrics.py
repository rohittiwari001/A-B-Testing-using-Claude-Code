"""Ratio metrics and analysis units finer than the randomisation unit.

When users are randomised but the metric is per session / pageview / order
(e.g. CTR = clicks / pageviews), rows from the same user are correlated. A
naive test treating rows as independent understates the variance and produces
false positives. Two correct options:

- :func:`delta_method_ratio`: aggregate to one row per randomisation unit
  (sum numerator, sum denominator) and use the delta method for the variance
  of the ratio of means.
- :func:`cluster_robust_test`: regress the row-level metric on treatment with
  standard errors clustered by randomisation unit.

Example
-------
>>> from abkit.ratio_metrics import delta_method_ratio
>>> r = delta_method_ratio(df, "clicks", "pageviews", "user_id", "variant", "control", "treatment")  # doctest: +SKIP
>>> r.extra["design_effect"] > 1                                                                   # doctest: +SKIP
True
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from abkit.frequentist import p_from_z, z_crit
from abkit.results import StatResult


def _ratio_stats(num: np.ndarray, den: np.ndarray) -> tuple[float, float]:
    """Ratio of means and its delta-method variance, from unit-level sums."""
    n = num.size
    mx, my = num.mean(), den.mean()
    vx, vy = num.var(ddof=1), den.var(ddof=1)
    cxy = np.cov(num, den, ddof=1)[0, 1]
    r = mx / my
    var = (vx / my**2 - 2 * mx * cxy / my**3 + mx**2 * vy / my**4) / n
    return float(r), float(var)


def delta_method_ratio(
    df: pd.DataFrame, numerator: str, denominator: str, unit_col: str, variant_col: str, control: str, treatment: str,
    alpha: float = 0.05, alternative: str = "two-sided", metric: str | None = None, role: str | None = None,
) -> StatResult:
    """Difference in a ratio metric (sum num / sum den) with delta-method standard errors.

    ``extra`` includes the naive row-level SE and the design effect (variance inflation the
    naive test ignores).
    """
    agg = df.groupby([unit_col, variant_col], as_index=False)[[numerator, denominator]].sum()
    out = {}
    for v in (control, treatment):
        g = agg[agg[variant_col].astype(str) == str(v)]
        if len(g) < 2:
            raise ValueError(f"Variant {v!r} has fewer than 2 units")
        if (g[denominator] <= 0).all():
            raise ValueError(f"Denominator {denominator!r} is zero for every unit in {v!r}")
        out[v] = (*_ratio_stats(g[numerator].to_numpy(float), g[denominator].to_numpy(float)), len(g), g)
    rc, vc, nc, gc = out[control]
    rt, vt, nt, gt = out[treatment]
    diff, se = rt - rc, np.sqrt(vc + vt)
    z = diff / se
    zc = z_crit(alpha, alternative)
    rel = rt / rc - 1
    se_rel = np.sqrt(vt / rc**2 + rt**2 * vc / rc**4)
    # Naive: treat each row's denominator units as independent Bernoulli trials (what a row-level test does)
    rows_c = df[df[variant_col].astype(str) == str(control)]
    rows_t = df[df[variant_col].astype(str) == str(treatment)]
    naive_var = sum(r * (1 - r) / max(g[denominator].sum(), 1) if 0 <= r <= 1 else np.nan
                    for r, g in ((rc, rows_c), (rt, rows_t)))
    naive_p = float(2 * stats.norm.sf(abs(diff) / np.sqrt(naive_var))) if naive_var and naive_var > 0 else None
    z2 = stats.norm.ppf(1 - alpha / 2)
    vs = {v: {"mean": out[v][0], "ci_low": out[v][0] - z2 * np.sqrt(out[v][1]),
              "ci_high": out[v][0] + z2 * np.sqrt(out[v][1]), "n": out[v][2]} for v in (control, treatment)}
    r = StatResult(
        method="ratio_metrics.delta_method_ratio", metric=metric or f"{numerator}/{denominator}", role=role,
        control=control, treatment=treatment, estimate=float(diff), ci_low=float(diff - zc * se), ci_high=float(diff + zc * se),
        p_value=p_from_z(z, alternative), n={control: int(nc), treatment: int(nt)}, control_value=rc, treatment_value=rt,
        rel_lift=float(rel), rel_ci_low=float(rel - zc * se_rel), rel_ci_high=float(rel + zc * se_rel),
        alpha=alpha, sidedness=alternative,
        assumptions=[{"check": "randomisation unit = aggregation unit", "passed": None, "detail": f"aggregated by {unit_col}"},
                     {"check": "enough units for the delta-method normal approximation", "passed": bool(min(nc, nt) >= 200),
                      "detail": f"{nc:,} / {nt:,} units"}],
        extra={"se": float(se), "z": float(z), "naive_se": float(np.sqrt(naive_var)) if naive_var else None, "naive_p": naive_p,
               "design_effect": float((vc + vt) / naive_var) if naive_var else None, "rows": {control: len(rows_c), treatment: len(rows_t)},
               "variant_stats": vs},
    )
    r.significant = bool(r.p_value < alpha)
    return r


def cluster_robust_test(
    df: pd.DataFrame, metric: str, cluster_col: str, variant_col: str, control: str, treatment: str,
    alpha: float = 0.05, weights: str | None = None, role: str | None = None,
) -> StatResult:
    """OLS of the row-level metric on a treatment dummy with cluster-robust (CR1) SEs.

    For a ratio metric pass the row ratio as ``metric`` and the denominator as ``weights``
    (WLS), which reproduces the ratio-of-sums estimate.
    """
    import statsmodels.api as sm

    d = df[df[variant_col].astype(str).isin([str(control), str(treatment)])].dropna(subset=[metric])
    X = sm.add_constant((d[variant_col].astype(str) == str(treatment)).astype(float).rename("treatment"))
    groups = pd.factorize(d[cluster_col])[0]
    model = sm.WLS(d[metric].astype(float), X, weights=d[weights].astype(float)) if weights else sm.OLS(d[metric].astype(float), X)
    fit = model.fit(cov_type="cluster", cov_kwds={"groups": groups})
    b0, b1 = float(fit.params["const"]), float(fit.params["treatment"])
    cov = fit.cov_params()
    lo, hi = fit.conf_int(alpha).loc["treatment"]
    # relative lift b1 / b0 with delta method using the joint covariance
    g = np.array([-b1 / b0**2, 1 / b0])
    se_rel = float(np.sqrt(g @ cov.loc[["const", "treatment"], ["const", "treatment"]].to_numpy() @ g))
    zc = stats.norm.ppf(1 - alpha / 2)
    naive = (sm.WLS(d[metric].astype(float), X, weights=d[weights].astype(float)) if weights else sm.OLS(d[metric].astype(float), X)).fit()
    r = StatResult(
        method="ratio_metrics.cluster_robust_test", metric=metric, role=role, control=control, treatment=treatment,
        estimate=b1, ci_low=float(lo), ci_high=float(hi), p_value=float(fit.pvalues["treatment"]),
        n={control: int(d.loc[X["treatment"] == 0, cluster_col].nunique()), treatment: int(d.loc[X["treatment"] == 1, cluster_col].nunique())},
        control_value=b0, treatment_value=b0 + b1, rel_lift=b1 / b0, rel_ci_low=b1 / b0 - zc * se_rel, rel_ci_high=b1 / b0 + zc * se_rel,
        alpha=alpha, sidedness="two-sided", significant=bool(fit.pvalues["treatment"] < alpha),
        assumptions=[{"check": "enough clusters for cluster-robust SEs (>= 50 per arm)", "passed": bool(len(np.unique(groups)) >= 100),
                      "detail": f"{len(np.unique(groups)):,} clusters"}],
        extra={"se": float(fit.bse["treatment"]), "naive_se": float(naive.bse["treatment"]), "naive_p": float(naive.pvalues["treatment"]),
               "design_effect": float(fit.bse["treatment"] ** 2 / naive.bse["treatment"] ** 2), "rows": int(len(d))},
    )
    return r
