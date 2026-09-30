"""Effects over time: daily and cumulative lifts, novelty / primacy checks.

- :func:`effects_by` - lift with CI for each level of a time column (calendar day,
  or days since exposure for a cohort-by-exposure-day view).
- :func:`cumulative_effects` - the metric per variant accumulated day by day.
- :func:`trend_test` - weighted regression of daily lift on time; a significant
  negative slope for a positive effect suggests novelty, positive suggests primacy / learning.

Example
-------
>>> from abkit.time_effects import effects_by, trend_test
>>> daily = effects_by(df, "clicks", "count", "days_since_exposure", "variant", "control", "treatment")  # doctest: +SKIP
>>> trend_test(daily).extra["pattern"]                                                                 # doctest: +SKIP
'novelty (effect decays)'
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from abkit.frequentist import compare
from abkit.results import StatResult


def effects_by(
    df: pd.DataFrame, metric: str, metric_type: str, time_col: str, variant_col: str, control: str, treatment: str,
    alpha: float = 0.05, min_n: int = 30,
) -> pd.DataFrame:
    """One row per time level: control/treatment means, n, absolute and relative lift with CIs."""
    rows = []
    for level, g in df.groupby(time_col):
        n = g[variant_col].astype(str).value_counts()
        if min(n.get(str(control), 0), n.get(str(treatment), 0)) < min_n:
            continue
        r = compare(g, metric, metric_type, variant_col, control, treatment, alpha)
        rows.append({time_col: level.date().isoformat() if isinstance(level, pd.Timestamp) else level,
                     "control_mean": r.control_value, "treatment_mean": r.treatment_value,
                     "n_control": r.n[str(control)], "n_treatment": r.n[str(treatment)],
                     "abs_lift": r.estimate, "ci_low": r.ci_low, "ci_high": r.ci_high,
                     "rel_lift": r.rel_lift, "rel_ci_low": r.rel_ci_low, "rel_ci_high": r.rel_ci_high, "p_value": r.p_value})
    return pd.DataFrame(rows)


def daily_effects(df, metric, metric_type, date_col, variant_col, control, treatment, alpha=0.05) -> pd.DataFrame:
    """:func:`effects_by` on the calendar date (normalised to days)."""
    d = df.assign(**{date_col: pd.to_datetime(df[date_col]).dt.normalize()})
    return effects_by(d, metric, metric_type, date_col, variant_col, control, treatment, alpha)


def cumulative_effects(
    df: pd.DataFrame, metric: str, metric_type: str, date_col: str, variant_col: str, control: str, treatment: str,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """Cumulative mean per variant up to each day plus the cumulative relative lift and CI.

    Returns long-ish columns: date, control_mean, treatment_mean, rel_lift, rel_ci_low, rel_ci_high, n_control, n_treatment.
    """
    d = df.assign(_day=pd.to_datetime(df[date_col]).dt.normalize())
    rows = []
    for day in sorted(d["_day"].unique()):
        cum = d[d["_day"] <= day]
        try:
            r = compare(cum, metric, metric_type, variant_col, control, treatment, alpha)
        except ValueError:
            continue
        rows.append({"date": pd.Timestamp(day).date().isoformat(), "control_mean": r.control_value,
                     "treatment_mean": r.treatment_value, "n_control": r.n[str(control)], "n_treatment": r.n[str(treatment)],
                     "rel_lift": r.rel_lift, "rel_ci_low": r.rel_ci_low, "rel_ci_high": r.rel_ci_high, "p_value": r.p_value})
    return pd.DataFrame(rows)


def trend_test(daily: pd.DataFrame, lift_col: str = "rel_lift", alpha: float = 0.05) -> StatResult:
    """Inverse-variance weighted regression of the per-period lift on period index.

    Needs columns ``lift_col``, ``rel_ci_low``/``rel_ci_high`` (or ``ci_low``/``ci_high``).
    """
    import statsmodels.api as sm

    d = daily.dropna(subset=[lift_col]).reset_index(drop=True)
    if len(d) < 4:
        raise ValueError("Need at least 4 periods for a trend test")
    lo, hi = ("rel_ci_low", "rel_ci_high") if lift_col == "rel_lift" else ("ci_low", "ci_high")
    se = (d[hi] - d[lo]) / (2 * stats.norm.ppf(0.975))
    w = 1 / np.maximum(se.to_numpy() ** 2, 1e-18)
    X = sm.add_constant(np.arange(len(d), dtype=float))
    fit = sm.WLS(d[lift_col].to_numpy(float), X, weights=w).fit()
    slope, p = float(fit.params[1]), float(fit.pvalues[1])
    mean_lift = float(np.average(d[lift_col], weights=w))
    if p >= alpha:
        pattern = "stable (no significant trend)"
    elif np.sign(slope) != np.sign(mean_lift):
        pattern = "novelty (effect decays)"
    else:
        pattern = "primacy / learning (effect grows)"
    k = len(d) // 3 or 1
    return StatResult(
        method="time_effects.trend_test", estimate=slope, ci_low=float(fit.conf_int(alpha)[1][0]), ci_high=float(fit.conf_int(alpha)[1][1]),
        p_value=p, alpha=alpha, significant=p < alpha,
        extra={"pattern": pattern, "periods": int(len(d)), "weighted_mean_lift": mean_lift,
               "first_third_lift": float(d[lift_col].iloc[:k].mean()), "last_third_lift": float(d[lift_col].iloc[-k:].mean())},
        notes=[f"Slope of {lift_col} per period; pattern: {pattern}."],
    )


def early_vs_late(
    df: pd.DataFrame, metric: str, metric_type: str, time_col: str, split_at, variant_col: str, control: str, treatment: str,
    alpha: float = 0.05,
) -> list[StatResult]:
    """Effect before and from ``split_at`` (e.g. exposure day 7) - a simple novelty contrast."""
    early = compare(df[df[time_col] < split_at], metric, metric_type, variant_col, control, treatment, alpha)
    late = compare(df[df[time_col] >= split_at], metric, metric_type, variant_col, control, treatment, alpha)
    early.segment, late.segment = f"{time_col} < {split_at}", f"{time_col} >= {split_at}"
    return [early, late]
