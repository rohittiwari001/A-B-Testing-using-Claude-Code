"""Variance reduction with pre-experiment covariates: CUPED and regression adjustment.

CUPED: Y_adj = Y - theta * (X - mean(X)), theta = cov(Y, X) / var(X) pooled across
variants. The treatment effect estimate stays unbiased (X is measured before
assignment) while variance falls by roughly corr(X, Y)^2.

Example
-------
>>> from abkit.variance_reduction import cuped
>>> r = cuped(df, "minutes", "pre_minutes", "variant", "control", "treatment")   # doctest: +SKIP
>>> r.extra["variance_reduction"]                                                # doctest: +SKIP
0.52
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from abkit.frequentist import welch_ttest
from abkit.results import StatResult


def cuped(
    df: pd.DataFrame, metric: str, covariate: str, variant_col: str, control: str, treatment: str,
    alpha: float = 0.05, alternative: str = "two-sided", role: str | None = None,
) -> StatResult:
    """CUPED-adjusted Welch test. ``extra`` holds theta, correlation, variance reduction and the unadjusted result.

    Missing covariate values are filled with the pooled covariate mean (they get no adjustment).
    """
    for col in (metric, covariate, variant_col):
        if col not in df.columns:
            raise KeyError(f"Column {col!r} not in data")
    d = df[df[variant_col].astype(str).isin([str(control), str(treatment)])].dropna(subset=[metric])
    x = d[covariate].astype(float)
    n_missing = int(x.isna().sum())
    x = x.fillna(x.mean())
    y = d[metric].astype(float)
    var_x = x.var(ddof=1)
    if var_x == 0:
        raise ValueError(f"Covariate {covariate!r} has zero variance")
    theta = float(np.cov(y, x, ddof=1)[0, 1] / var_x)
    y_adj = y - theta * (x - x.mean())
    is_t = d[variant_col].astype(str) == str(treatment)
    raw = welch_ttest(y[~is_t], y[is_t], alpha, alternative, metric, control, treatment)
    adj = welch_ttest(y_adj[~is_t], y_adj[is_t], alpha, alternative, metric, control, treatment)
    # Relative lift is expressed against the unadjusted control mean (the business-facing level)
    mc, mt = raw.control_value, raw.control_value + adj.estimate
    se_c = float(np.sqrt(y_adj[~is_t].var(ddof=1) / (~is_t).sum()))
    se_t = float(np.sqrt(y_adj[is_t].var(ddof=1) / is_t.sum()))
    from abkit.frequentist import relative_lift_ci, z_crit

    rel, rlo, rhi = relative_lift_ci(mc, se_c, mt, se_t, z_crit(alpha, alternative))
    corr = float(np.corrcoef(y, x)[0, 1])
    var_red = float(1 - y_adj.var(ddof=1) / y.var(ddof=1))
    adj.method = "variance_reduction.cuped"
    adj.role = role
    adj.control_value, adj.treatment_value = float(mc), float(mt)
    adj.rel_lift, adj.rel_ci_low, adj.rel_ci_high = rel, rlo, rhi
    adj.assumptions.append({"check": "covariate measured before assignment (unaffected by treatment)", "passed": None,
                            "detail": f"{covariate}: confirm it is pre-period"})
    adj.assumptions.append({"check": "covariate balanced across variants", "passed": bool(_balanced(x, is_t)),
                            "detail": f"mean {x[~is_t].mean():.3g} vs {x[is_t].mean():.3g}"})
    if n_missing:
        adj.notes.append(f"{n_missing:,} missing covariate values filled with the pooled mean.")
    adj.extra.update({
        "theta": theta, "covariate": covariate, "correlation": corr, "variance_reduction": var_red,
        "effective_sample_multiplier": float(1 / (1 - var_red)) if var_red < 1 else None,
        "ci_width_unadjusted": float(raw.ci_high - raw.ci_low), "ci_width_adjusted": float(adj.ci_high - adj.ci_low),
        "unadjusted": raw.to_dict(),
    })
    return adj


def regression_adjustment(
    df: pd.DataFrame, metric: str, covariates: Sequence[str], variant_col: str, control: str, treatment: str,
    alpha: float = 0.05, role: str | None = None,
) -> StatResult:
    """Lin (2013) regression adjustment: Y ~ T + Xc + T:Xc with centred covariates and HC2 robust SEs.

    Handles several covariates (and categorical ones via one-hot encoding).
    """
    import statsmodels.api as sm

    d = df[df[variant_col].astype(str).isin([str(control), str(treatment)])].dropna(subset=[metric, *covariates])
    T = (d[variant_col].astype(str) == str(treatment)).astype(float).to_numpy()
    X = pd.get_dummies(d[list(covariates)], drop_first=True).astype(float)
    Xc = X - X.mean()
    design = pd.concat([pd.Series(T, index=d.index, name="treatment"), Xc,
                        Xc.mul(T, axis=0).add_suffix(":treatment")], axis=1)
    design = sm.add_constant(design)
    fit = sm.OLS(d[metric].astype(float), design).fit(cov_type="HC2")
    est, se = float(fit.params["treatment"]), float(fit.bse["treatment"])
    lo, hi = fit.conf_int(alpha).loc["treatment"]
    from scipy import stats

    mc = float(d.loc[T == 0, metric].mean())
    se_c = float(d.loc[T == 0, metric].std(ddof=1) / np.sqrt((T == 0).sum()))
    z = stats.norm.ppf(1 - alpha / 2)
    rel = est / mc
    se_rel = float(np.sqrt(se**2 / mc**2 + est**2 * se_c**2 / mc**4))   # delta method for est / control mean
    rlo, rhi = rel - z * se_rel, rel + z * se_rel
    return StatResult(
        method="variance_reduction.regression_adjustment", metric=metric, role=role, control=control, treatment=treatment,
        estimate=est, ci_low=float(lo), ci_high=float(hi), p_value=float(fit.pvalues["treatment"]),
        n={control: int((T == 0).sum()), treatment: int((T == 1).sum())}, control_value=mc, treatment_value=mc + est,
        rel_lift=rel, rel_ci_low=rlo, rel_ci_high=rhi, alpha=alpha, sidedness="two-sided",
        significant=bool(fit.pvalues["treatment"] < alpha),
        assumptions=[{"check": "covariates measured pre-assignment", "passed": None, "detail": ", ".join(covariates)}],
        extra={"r_squared": float(fit.rsquared), "covariates": list(covariates), "se": se},
    )


def _balanced(x: pd.Series, is_t: pd.Series) -> bool:
    from scipy import stats

    return stats.ttest_ind(x[is_t], x[~is_t], equal_var=False).pvalue > 0.001
