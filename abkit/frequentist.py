"""Frequentist comparisons of a treatment against a control.

Pick the test by metric type (see the ab-methods skill, frequentist_tests.md):

=============  ======================================  ==========================
metric type    default                                 alternatives
=============  ======================================  ==========================
binary         :func:`two_proportion_ztest`            :func:`chi_square_test`
continuous     :func:`welch_ttest`                     :func:`bootstrap_diff`, :func:`mann_whitney`
count          :func:`welch_ttest`                     :func:`bootstrap_diff`
ratio          ``abkit.ratio_metrics``                 (delta method / clustered SE)
=============  ======================================  ==========================

Conventions: ``estimate`` = treatment - control (absolute lift); ``rel_lift`` =
treatment / control - 1 with a delta-method CI; for ``alternative`` other than
two-sided the CI is the matching (1 - 2*alpha) two-sided interval so its bound
agrees with the one-sided test.

Example
-------
>>> from abkit.frequentist import two_proportion_ztest
>>> r = two_proportion_ztest(x_c=500, n_c=10000, x_t=560, n_t=10000)
>>> round(r.rel_lift, 3), round(r.p_value, 3)
(0.12, 0.058)
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from abkit.results import StatResult

ALTERNATIVES = ("two-sided", "greater", "less")


# --------------------------------------------------------------------------- helpers


def z_crit(alpha: float, alternative: str = "two-sided") -> float:
    """Critical z for the CI that matches the test."""
    _check_alt(alternative)
    return float(stats.norm.ppf(1 - alpha / 2)) if alternative == "two-sided" else float(stats.norm.ppf(1 - alpha))


def alternative_for(sidedness: str, direction: str) -> str:
    """Map run settings to a scipy-style alternative ('one-sided' + 'decrease' -> 'less')."""
    if sidedness == "two-sided":
        return "two-sided"
    return "less" if direction in ("decrease", "no_increase") else "greater"


def p_from_z(z: float, alternative: str) -> float:
    if alternative == "two-sided":
        return float(2 * stats.norm.sf(abs(z)))
    return float(stats.norm.sf(z)) if alternative == "greater" else float(stats.norm.cdf(z))


def relative_lift_ci(mean_c: float, se_c: float, mean_t: float, se_t: float, zc: float) -> tuple[float, float, float]:
    """Delta-method CI for treatment/control - 1 (independent groups)."""
    if mean_c == 0:
        return (float("nan"),) * 3
    rel = mean_t / mean_c - 1
    se = np.sqrt(se_t**2 / mean_c**2 + mean_t**2 * se_c**2 / mean_c**4)
    return float(rel), float(rel - zc * se), float(rel + zc * se)


def mean_ci(x: np.ndarray, alpha: float = 0.05) -> dict[str, float]:
    """Mean with a normal-approximation CI (used for per-variant bars)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    m = float(x.mean()) if n else float("nan")
    se = float(x.std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan")
    z = stats.norm.ppf(1 - alpha / 2)
    return {"mean": m, "ci_low": m - z * se, "ci_high": m + z * se, "se": se, "n": int(n)}


def _check_alt(alternative: str) -> None:
    if alternative not in ALTERNATIVES:
        raise ValueError(f"alternative must be one of {ALTERNATIVES}, got {alternative!r}")


def _arr(x: Iterable[float], name: str) -> np.ndarray:
    a = np.asarray(pd.Series(x).dropna(), dtype=float)
    if a.size < 2:
        raise ValueError(f"{name} needs at least 2 non-missing values, got {a.size}")
    return a


def _finish(r: StatResult, alpha: float, alternative: str) -> StatResult:
    r.alpha, r.sidedness = alpha, alternative
    if r.p_value is not None and not np.isnan(r.p_value):
        r.significant = bool(r.p_value < alpha)
    if alternative != "two-sided":
        r.notes.append(f"One-sided test ({alternative}); CI shown at {1 - 2 * alpha:.0%} two-sided to match.")
    return r


# --------------------------------------------------------------------------- tests


def two_proportion_ztest(
    x_c: int, n_c: int, x_t: int, n_t: int,
    alpha: float = 0.05, alternative: str = "two-sided",
    metric: str | None = None, control: str = "control", treatment: str = "treatment",
) -> StatResult:
    """Two-proportion z-test (pooled SE for the test, unpooled SE for the CI).

    >>> two_proportion_ztest(100, 1000, 130, 1000).significant
    True
    """
    _check_alt(alternative)
    if min(n_c, n_t) <= 0 or not (0 <= x_c <= n_c and 0 <= x_t <= n_t):
        raise ValueError("Need 0 <= successes <= trials and trials > 0 in each group")
    p_c, p_t = x_c / n_c, x_t / n_t
    p_pool = (x_c + x_t) / (n_c + n_t)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))
    z = (p_t - p_c) / se_pool if se_pool > 0 else 0.0
    se_c, se_t = np.sqrt(p_c * (1 - p_c) / n_c), np.sqrt(p_t * (1 - p_t) / n_t)
    se = np.sqrt(se_c**2 + se_t**2)
    zc = z_crit(alpha, alternative)
    rel, rlo, rhi = relative_lift_ci(p_c, se_c, p_t, se_t, zc)
    ok = min(x_c, n_c - x_c, x_t, n_t - x_t) >= 10
    r = StatResult(
        method="frequentist.two_proportion_ztest", metric=metric, control=control, treatment=treatment,
        estimate=p_t - p_c, ci_low=p_t - p_c - zc * se, ci_high=p_t - p_c + zc * se,
        p_value=p_from_z(z, alternative), n={control: int(n_c), treatment: int(n_t)},
        control_value=p_c, treatment_value=p_t, rel_lift=rel, rel_ci_low=rlo, rel_ci_high=rhi,
        assumptions=[
            {"check": "independent units (one row per randomisation unit)", "passed": None, "detail": "verify in validation"},
            {"check": "normal approximation: >= 10 successes and failures per group", "passed": ok,
             "detail": f"min cell = {min(x_c, n_c - x_c, x_t, n_t - x_t)}"},
        ],
        extra={"z": float(z), "se": float(se), "variant_stats": {
            control: _prop_stats(x_c, n_c, alpha), treatment: _prop_stats(x_t, n_t, alpha)}},
    )
    if not ok:
        r.notes.append("Small counts: prefer Fisher's exact test (scipy.stats.fisher_exact).")
    return _finish(r, alpha, alternative)


def welch_ttest(
    control_values: Iterable[float], treatment_values: Iterable[float],
    alpha: float = 0.05, alternative: str = "two-sided",
    metric: str | None = None, control: str = "control", treatment: str = "treatment",
) -> StatResult:
    """Welch's unequal-variance t-test on means with a Welch-Satterthwaite CI."""
    _check_alt(alternative)
    c, t = _arr(control_values, "control"), _arr(treatment_values, "treatment")
    res = stats.ttest_ind(t, c, equal_var=False, alternative=alternative)
    vc, vt = c.var(ddof=1) / c.size, t.var(ddof=1) / t.size
    se = np.sqrt(vc + vt)
    df = se**4 / (vc**2 / (c.size - 1) + vt**2 / (t.size - 1)) if se > 0 else np.inf
    q = stats.t.ppf(1 - alpha / 2, df) if alternative == "two-sided" else stats.t.ppf(1 - alpha, df)
    diff = t.mean() - c.mean()
    rel, rlo, rhi = relative_lift_ci(c.mean(), np.sqrt(vc), t.mean(), np.sqrt(vt), q)
    skew = float(max(abs(stats.skew(c)), abs(stats.skew(t))))
    clt_ok = min(c.size, t.size) >= 30 and (skew < 2 or min(c.size, t.size) >= 1000)
    r = StatResult(
        method="frequentist.welch_ttest", metric=metric, control=control, treatment=treatment,
        estimate=float(diff), ci_low=float(diff - q * se), ci_high=float(diff + q * se),
        p_value=float(res.pvalue), n={control: int(c.size), treatment: int(t.size)},
        control_value=float(c.mean()), treatment_value=float(t.mean()),
        rel_lift=rel, rel_ci_low=rlo, rel_ci_high=rhi,
        assumptions=[
            {"check": "independent units", "passed": None, "detail": "verify in validation"},
            {"check": "sampling distribution of the mean ~ normal (CLT)", "passed": bool(clt_ok),
             "detail": f"n = {c.size:,}/{t.size:,}, max |skew| = {skew:.1f}"},
        ],
        extra={"t": float(res.statistic), "df": float(df), "se": float(se), "variant_stats": {
            control: mean_ci(c, alpha), treatment: mean_ci(t, alpha)}},
    )
    if skew > 5:
        r.notes.append("Heavy-tailed metric: confirm with bootstrap_diff and consider winsorising (report both).")
    return _finish(r, alpha, alternative)


def bootstrap_diff(
    control_values: Iterable[float], treatment_values: Iterable[float],
    stat: str = "mean", n_resamples: int = 10_000, seed: int = 42, alpha: float = 0.05,
    metric: str | None = None, control: str = "control", treatment: str = "treatment",
) -> StatResult:
    """Percentile bootstrap CI for the difference and relative lift of a statistic ('mean' or 'median').

    The p-value is the two-sided bootstrap p (2 x share of resampled differences on the other side of 0).
    """
    c, t = _arr(control_values, "control"), _arr(treatment_values, "treatment")
    fn = {"mean": np.mean, "median": np.median}[stat]
    rng = np.random.default_rng(seed)
    diffs, rels = np.empty(n_resamples), np.empty(n_resamples)
    chunk = max(1, int(4e6 // max(c.size, t.size)))
    for start in range(0, n_resamples, chunk):
        k = min(chunk, n_resamples - start)
        bc = fn(c[rng.integers(0, c.size, (k, c.size))], axis=1)
        bt = fn(t[rng.integers(0, t.size, (k, t.size))], axis=1)
        diffs[start:start + k] = bt - bc
        with np.errstate(divide="ignore", invalid="ignore"):
            rels[start:start + k] = bt / bc - 1
    lo, hi = 100 * alpha / 2, 100 * (1 - alpha / 2)
    est = float(fn(t) - fn(c))
    p = float(min(1.0, 2 * min((diffs <= 0).mean(), (diffs >= 0).mean())))
    rels = rels[np.isfinite(rels)]
    r = StatResult(
        method=f"frequentist.bootstrap_{stat}_diff", metric=metric, control=control, treatment=treatment,
        estimate=est, ci_low=float(np.percentile(diffs, lo)), ci_high=float(np.percentile(diffs, hi)),
        p_value=p, n={control: int(c.size), treatment: int(t.size)},
        control_value=float(fn(c)), treatment_value=float(fn(t)),
        rel_lift=float(fn(t) / fn(c) - 1) if fn(c) != 0 else None,
        rel_ci_low=float(np.percentile(rels, lo)) if rels.size else None,
        rel_ci_high=float(np.percentile(rels, hi)) if rels.size else None,
        assumptions=[{"check": "independent units; sample represents population", "passed": None, "detail": ""}],
        extra={"n_resamples": n_resamples, "seed": seed, "stat": stat},
    )
    return _finish(r, alpha, "two-sided")


def mann_whitney(
    control_values: Iterable[float], treatment_values: Iterable[float],
    alpha: float = 0.05, alternative: str = "two-sided",
    metric: str | None = None, control: str = "control", treatment: str = "treatment",
) -> StatResult:
    """Mann-Whitney U test. ``probability`` = P(T > C) + 0.5 P(T = C); ``estimate`` = difference in medians.

    Tests a shift in distribution, not a difference in means: do not use it to make
    claims about revenue per user totals.
    """
    _check_alt(alternative)
    c, t = _arr(control_values, "control"), _arr(treatment_values, "treatment")
    res = stats.mannwhitneyu(t, c, alternative=alternative)
    prob_sup = float(res.statistic / (c.size * t.size))
    r = StatResult(
        method="frequentist.mann_whitney", metric=metric, control=control, treatment=treatment,
        estimate=float(np.median(t) - np.median(c)), p_value=float(res.pvalue), probability=prob_sup,
        n={control: int(c.size), treatment: int(t.size)},
        control_value=float(np.median(c)), treatment_value=float(np.median(t)),
        assumptions=[{"check": "independent units; ordinal outcome", "passed": None, "detail": ""}],
        notes=["Rank test: answers 'does treatment shift the distribution?', not 'did the mean change?'."],
        extra={"U": float(res.statistic), "prob_superiority": prob_sup},
    )
    return _finish(r, alpha, alternative)


def chi_square_test(table: pd.DataFrame | np.ndarray, alpha: float = 0.05, metric: str | None = None) -> StatResult:
    """Chi-square test of independence on a variants x outcome-categories table.

    ``estimate`` is Cramer's V (effect size).
    """
    tab = np.asarray(table, dtype=float)
    chi2, p, dof, expected = stats.chi2_contingency(tab, correction=False)
    v = np.sqrt(chi2 / (tab.sum() * (min(tab.shape) - 1)))
    rows = list(table.index) if isinstance(table, pd.DataFrame) else list(range(tab.shape[0]))
    r = StatResult(
        method="frequentist.chi_square_test", metric=metric, estimate=float(v), p_value=float(p),
        n={str(k): int(v_) for k, v_ in zip(rows, tab.sum(axis=1))},
        assumptions=[{"check": "expected count >= 5 in every cell", "passed": bool((expected >= 5).all()),
                      "detail": f"min expected = {expected.min():.1f}"}],
        extra={"chi2": float(chi2), "dof": int(dof), "cramers_v": float(v)},
    )
    return _finish(r, alpha, "two-sided")


def noninferiority_test(
    control_values: Iterable[float] | None = None, treatment_values: Iterable[float] | None = None,
    margin_rel: float = 0.01, direction: str = "no_decrease", alpha: float = 0.05,
    metric: str | None = None, control: str = "control", treatment: str = "treatment",
    counts: tuple[int, int, int, int] | None = None,
) -> StatResult:
    """One-sided non-inferiority test for a guardrail.

    H0: treatment is worse than control by more than ``margin_rel`` (relative).
    ``direction`` 'no_decrease' (bigger is better) or 'no_increase' (e.g. latency, errors).
    Pass raw values, or ``counts=(x_c, n_c, x_t, n_t)`` for a binary metric.

    ``extra['status']``: 'pass' (non-inferior), 'breach' (the whole CI is past the margin),
    or 'inconclusive'. The CI is two-sided at 1 - 2*alpha (the standard NI convention).
    """
    if direction not in ("no_decrease", "no_increase"):
        raise ValueError("direction must be 'no_decrease' or 'no_increase'")
    if counts is not None:
        x_c, n_c, x_t, n_t = counts
        mc, mt = x_c / n_c, x_t / n_t
        se_c, se_t = np.sqrt(mc * (1 - mc) / n_c), np.sqrt(mt * (1 - mt) / n_t)
        n = {control: int(n_c), treatment: int(n_t)}
    else:
        c, t = _arr(control_values, "control"), _arr(treatment_values, "treatment")
        mc, mt = c.mean(), t.mean()
        se_c, se_t = c.std(ddof=1) / np.sqrt(c.size), t.std(ddof=1) / np.sqrt(t.size)
        n = {control: int(c.size), treatment: int(t.size)}
    se = np.sqrt(se_c**2 + se_t**2)
    diff = mt - mc
    margin_abs = abs(margin_rel * mc)
    sign = 1 if direction == "no_decrease" else -1
    z = (sign * diff + margin_abs) / se
    p = float(stats.norm.sf(z))
    zc = stats.norm.ppf(1 - alpha)
    lo, hi = diff - zc * se, diff + zc * se
    rel, rlo, rhi = relative_lift_ci(mc, se_c, mt, se_t, zc)
    worst = hi if direction == "no_decrease" else -lo   # the CI bound on the "harm" side, signed so that < -margin is a breach
    status = "pass" if p < alpha else ("breach" if worst < -margin_abs else "inconclusive")
    r = StatResult(
        method="frequentist.noninferiority_test", metric=metric, role="guardrail", control=control, treatment=treatment,
        estimate=float(diff), ci_low=float(lo), ci_high=float(hi), p_value=p, n=n,
        control_value=float(mc), treatment_value=float(mt), rel_lift=rel, rel_ci_low=rlo, rel_ci_high=rhi,
        significant=p < alpha, alpha=alpha, sidedness="one-sided",
        assumptions=[{"check": "normal approximation for the difference", "passed": None, "detail": ""}],
        notes=[f"Non-inferiority margin {margin_rel:.1%} relative ({direction}); CI at {1 - 2 * alpha:.0%}."],
        extra={"status": status, "margin_rel": margin_rel, "margin_abs": float(margin_abs), "direction": direction, "z": float(z)},
    )
    return r


# --------------------------------------------------------------------------- DataFrame conveniences


def compare(
    df: pd.DataFrame, metric: str, metric_type: str, variant_col: str,
    control: str, treatment: str, alpha: float = 0.05, alternative: str = "two-sided", role: str | None = None,
) -> StatResult:
    """Run the default test for ``metric_type`` on unit-level rows of ``df``."""
    for col in (metric, variant_col):
        if col not in df.columns:
            raise KeyError(f"Column {col!r} not in data; have {list(df.columns)}")
    g = df[[variant_col, metric]].dropna()
    c = g.loc[g[variant_col].astype(str) == str(control), metric]
    t = g.loc[g[variant_col].astype(str) == str(treatment), metric]
    if c.empty or t.empty:
        raise ValueError(f"Empty group: control {control!r} n={len(c)}, treatment {treatment!r} n={len(t)}")
    if metric_type == "binary":
        r = two_proportion_ztest(int(c.sum()), len(c), int(t.sum()), len(t), alpha, alternative, metric, control, treatment)
    elif metric_type in ("continuous", "count"):
        r = welch_ttest(c, t, alpha, alternative, metric, control, treatment)
    elif metric_type == "ratio":
        raise ValueError("Ratio metrics need abkit.ratio_metrics.delta_method_ratio (analysis unit != randomisation unit).")
    else:
        raise ValueError(f"Unknown metric_type {metric_type!r}")
    r.role = role
    return r


def compare_to_control(
    df: pd.DataFrame, metric: str, metric_type: str, variant_col: str, control: str,
    treatments: Sequence[str] | None = None, alpha: float = 0.05, correction: str = "holm",
    alternative: str = "two-sided", role: str | None = None, dunnett: bool = False,
) -> list[StatResult]:
    """Multi-arm: every treatment vs control, then a multiple-comparison correction.

    ``dunnett=True`` (continuous metrics) replaces the corrected p-values with
    Dunnett's many-to-one p-values (scipy.stats.dunnett), which account for the
    shared control and are less conservative than Holm.
    """
    from abkit.multiple_testing import apply_correction

    arms = treatments or [v for v in sorted(df[variant_col].astype(str).unique()) if v != str(control)]
    out = [compare(df, metric, metric_type, variant_col, control, arm, alpha, alternative, role) for arm in arms]
    if len(out) > 1:
        apply_correction(out, correction, alpha)
        if dunnett and metric_type in ("continuous", "count"):
            samples = [df.loc[df[variant_col].astype(str) == a, metric].dropna().to_numpy() for a in arms]
            ctrl = df.loc[df[variant_col].astype(str) == str(control), metric].dropna().to_numpy()
            res = stats.dunnett(*samples, control=ctrl, alternative=alternative)
            for r, p in zip(out, res.pvalue):
                r.p_value_adjusted, r.correction, r.significant = float(p), "dunnett", bool(p < alpha)
    return out


def _prop_stats(x: int, n: int, alpha: float) -> dict[str, Any]:
    p = x / n
    se = np.sqrt(p * (1 - p) / n)
    z = stats.norm.ppf(1 - alpha / 2)
    return {"mean": p, "ci_low": p - z * se, "ci_high": p + z * se, "se": float(se), "n": int(n)}
