"""Power, sample size, minimum detectable effect (MDE) and runtime.

Closed-form normal-approximation formulas (the same ones statsmodels and most
online calculators use), with ``ratio`` = n_treatment / n_control and
``n_comparisons`` for a Bonferroni-style alpha split across multiple arms.

Example
-------
>>> from abkit.power import sample_size_proportions
>>> r = sample_size_proportions(baseline=0.10, mde=0.05)      # +5% relative
>>> r.estimate                                                # per variant
57763
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from scipy import optimize, stats

from abkit.results import StatResult


def _z_alpha(alpha: float, alternative: str, n_comparisons: int = 1) -> float:
    a = alpha / max(1, n_comparisons)
    return float(stats.norm.ppf(1 - a / 2)) if alternative == "two-sided" else float(stats.norm.ppf(1 - a))


def _abs_mde(baseline: float, mde: float, relative: bool) -> float:
    return baseline * mde if relative else mde


# --------------------------------------------------------------------------- proportions


def power_proportions(baseline: float, mde: float, n_control: float, relative: bool = True, alpha: float = 0.05,
                      alternative: str = "two-sided", ratio: float = 1.0, n_comparisons: int = 1) -> float:
    """Power to detect ``mde`` on a conversion rate with ``n_control`` units in control."""
    p1 = baseline
    p2 = baseline + _abs_mde(baseline, mde, relative)
    if not (0 < p1 < 1 and 0 < p2 < 1):
        raise ValueError(f"Rates must be in (0, 1): baseline={p1}, treatment={p2}")
    n1, n2 = n_control, n_control * ratio
    pbar = (p1 * n1 + p2 * n2) / (n1 + n2)
    se0 = math.sqrt(pbar * (1 - pbar) * (1 / n1 + 1 / n2))
    se1 = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    za = _z_alpha(alpha, alternative, n_comparisons)
    return float(stats.norm.cdf((abs(p2 - p1) - za * se0) / se1))


def sample_size_proportions(baseline: float, mde: float, relative: bool = True, alpha: float = 0.05, power: float = 0.8,
                            alternative: str = "two-sided", ratio: float = 1.0, n_comparisons: int = 1) -> StatResult:
    """Units needed in control (``estimate``) to detect ``mde`` with the requested power.

    ``mde`` is relative (0.05 = +5%) unless ``relative=False`` (absolute, e.g. 0.005 = 0.5 pp).
    """
    p1 = baseline
    d = _abs_mde(baseline, mde, relative)
    p2 = p1 + d
    if d == 0 or not (0 < p1 < 1 and 0 < p2 < 1):
        raise ValueError("Need a non-zero MDE and rates in (0, 1)")
    k = ratio
    pbar = (p1 + k * p2) / (1 + k)
    za, zb = _z_alpha(alpha, alternative, n_comparisons), stats.norm.ppf(power)
    n1 = (za * math.sqrt(pbar * (1 - pbar) * (1 + 1 / k)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2) / k)) ** 2 / d**2
    n1 = math.ceil(n1)
    n2 = math.ceil(n1 * k)
    return StatResult(
        method="power.sample_size_proportions", estimate=n1, n={"control": n1, "treatment": n2}, alpha=alpha,
        sidedness=alternative, control_value=p1, treatment_value=p2, rel_lift=d / p1,
        extra={"baseline": p1, "mde_abs": d, "mde_rel": d / p1, "power": power, "ratio": ratio,
               "n_comparisons": n_comparisons, "total": n1 + n2 * max(1, n_comparisons)},
        notes=[f"{n1:,} units per variant to detect {d / p1:+.1%} relative ({d * 100:+.2f} pp) at power {power:.0%}."],
    )


def mde_proportions(baseline: float, n_control: float, alpha: float = 0.05, power: float = 0.8,
                    alternative: str = "two-sided", ratio: float = 1.0, n_comparisons: int = 1) -> StatResult:
    """Smallest relative lift detectable with ``n_control`` units (``estimate`` = relative MDE)."""
    f = lambda m: power_proportions(baseline, m, n_control, True, alpha, alternative, ratio, n_comparisons) - power
    upper = min(10.0, (1 - baseline) / baseline * 0.999)
    rel = optimize.brentq(f, 1e-6, upper)
    return StatResult(
        method="power.mde_proportions", estimate=float(rel), n={"control": int(n_control), "treatment": int(n_control * ratio)},
        alpha=alpha, sidedness=alternative, control_value=baseline,
        extra={"baseline": baseline, "mde_rel": float(rel), "mde_abs": float(rel * baseline), "power": power},
    )


# --------------------------------------------------------------------------- means


def power_means(sd: float, mde_abs: float, n_control: float, alpha: float = 0.05, alternative: str = "two-sided",
                ratio: float = 1.0, n_comparisons: int = 1, sd_treatment: float | None = None) -> float:
    sd_t = sd_treatment or sd
    se = math.sqrt(sd**2 / n_control + sd_t**2 / (n_control * ratio))
    za = _z_alpha(alpha, alternative, n_comparisons)
    return float(stats.norm.cdf(abs(mde_abs) / se - za))


def sample_size_means(sd: float, mde_abs: float, alpha: float = 0.05, power: float = 0.8, alternative: str = "two-sided",
                      ratio: float = 1.0, n_comparisons: int = 1, baseline_mean: float | None = None) -> StatResult:
    """Units in control (``estimate``) to detect an absolute difference ``mde_abs`` in a mean."""
    if sd <= 0 or mde_abs == 0:
        raise ValueError("Need sd > 0 and a non-zero MDE")
    za, zb = _z_alpha(alpha, alternative, n_comparisons), stats.norm.ppf(power)
    n1 = math.ceil((za + zb) ** 2 * sd**2 * (1 + 1 / ratio) / mde_abs**2)
    n2 = math.ceil(n1 * ratio)
    rel = mde_abs / baseline_mean if baseline_mean else None
    return StatResult(
        method="power.sample_size_means", estimate=n1, n={"control": n1, "treatment": n2}, alpha=alpha, sidedness=alternative,
        control_value=baseline_mean, rel_lift=rel,
        extra={"sd": sd, "mde_abs": mde_abs, "mde_rel": rel, "power": power, "ratio": ratio,
               "n_comparisons": n_comparisons, "total": n1 + n2 * max(1, n_comparisons)},
    )


def mde_means(sd: float, n_control: float, alpha: float = 0.05, power: float = 0.8, alternative: str = "two-sided",
              ratio: float = 1.0, n_comparisons: int = 1, baseline_mean: float | None = None) -> StatResult:
    """Smallest absolute difference in means detectable (``estimate``); relative in ``rel_lift`` if baseline given."""
    za, zb = _z_alpha(alpha, alternative, n_comparisons), stats.norm.ppf(power)
    d = (za + zb) * sd * math.sqrt(1 / n_control + 1 / (n_control * ratio))
    return StatResult(
        method="power.mde_means", estimate=float(d), n={"control": int(n_control), "treatment": int(n_control * ratio)},
        alpha=alpha, sidedness=alternative, control_value=baseline_mean,
        rel_lift=float(d / baseline_mean) if baseline_mean else None,
        extra={"sd": sd, "mde_abs": float(d), "mde_rel": float(d / baseline_mean) if baseline_mean else None, "power": power},
    )


# --------------------------------------------------------------------------- curves, tables, runtime


def power_curve(kind: str, baseline_or_sd: float, mdes: Sequence[float], n_values: Iterable[int] | None = None,
                alpha: float = 0.05, alternative: str = "two-sided", baseline_mean: float | None = None) -> pd.DataFrame:
    """Power vs sample size per variant for several MDEs (relative for 'proportion', relative to
    ``baseline_mean`` for 'mean'). Returns columns n, mde, power."""
    n_values = list(n_values) if n_values is not None else list(np.unique(np.geomspace(500, 500_000, 40).astype(int)))
    rows = []
    for m in mdes:
        for n in n_values:
            if kind == "proportion":
                p = power_proportions(baseline_or_sd, m, n, True, alpha, alternative)
            elif kind == "mean":
                if not baseline_mean:
                    raise ValueError("baseline_mean is required for kind='mean'")
                p = power_means(baseline_or_sd, m * baseline_mean, n, alpha, alternative)
            else:
                raise ValueError("kind must be 'proportion' or 'mean'")
            rows.append({"n": int(n), "mde": m, "power": p})
    return pd.DataFrame(rows)


def sample_size_table(kind: str, baseline_or_sd: float, mdes: Sequence[float], alpha: float = 0.05, power: float = 0.8,
                      alternative: str = "two-sided", baseline_mean: float | None = None, daily_units: float | None = None,
                      n_variants: int = 2, prefer_full_weeks: bool = True, min_days: int = 7) -> pd.DataFrame:
    """Required n per variant (and days, if ``daily_units`` given) for each relative MDE."""
    rows = []
    for m in mdes:
        if kind == "proportion":
            n = sample_size_proportions(baseline_or_sd, m, True, alpha, power, alternative, n_comparisons=n_variants - 1).estimate
        else:
            n = sample_size_means(baseline_or_sd, m * baseline_mean, alpha, power, alternative, n_comparisons=n_variants - 1).estimate
        row = {"mde": m, "n_per_variant": int(n), "total": int(n * n_variants)}
        if daily_units:
            row["days"] = runtime_days(n, daily_units, n_variants, prefer_full_weeks=prefer_full_weeks, min_days=min_days)
        rows.append(row)
    return pd.DataFrame(rows)


def runtime_days(n_per_variant: float, daily_units: float, n_variants: int = 2, traffic_fraction: float = 1.0,
                 min_days: int = 7, prefer_full_weeks: bool = True) -> int:
    """Days to reach ``n_per_variant`` given eligible ``daily_units`` (new units per day)."""
    if daily_units <= 0:
        raise ValueError("daily_units must be > 0")
    days = math.ceil(n_per_variant * n_variants / (daily_units * traffic_fraction))
    days = max(days, min_days)
    return int(math.ceil(days / 7) * 7) if prefer_full_weeks else int(days)


def variance_from_history(values: Iterable[float]) -> dict[str, float]:
    """Mean / SD / CV from historical unit-level data (binary -> rate and Bernoulli SD)."""
    x = np.asarray(pd.Series(values).dropna(), dtype=float)
    if x.size < 2:
        raise ValueError("Need at least 2 historical values")
    is_binary = set(np.unique(x)) <= {0.0, 1.0}
    m = float(x.mean())
    sd = float(math.sqrt(m * (1 - m))) if is_binary else float(x.std(ddof=1))
    return {"mean": m, "sd": sd, "cv": sd / m if m else float("nan"), "n": int(x.size), "binary": bool(is_binary)}


def simulate_power(kind: str, baseline: float, mde_rel: float, n_per_variant: int, sd: float | None = None,
                   alpha: float = 0.05, n_sims: int = 2000, seed: int = 0) -> float:
    """Monte-Carlo power (used to validate the analytic formulas)."""
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n_sims):
        if kind == "proportion":
            xc = rng.binomial(n_per_variant, baseline)
            xt = rng.binomial(n_per_variant, baseline * (1 + mde_rel))
            pc, pt = xc / n_per_variant, xt / n_per_variant
            pp = (xc + xt) / (2 * n_per_variant)
            se = math.sqrt(pp * (1 - pp) * 2 / n_per_variant)
            z = (pt - pc) / se if se else 0
        else:
            c = rng.normal(baseline, sd, n_per_variant)
            t = rng.normal(baseline * (1 + mde_rel), sd, n_per_variant)
            z = (t.mean() - c.mean()) / math.sqrt(c.var(ddof=1) / n_per_variant + t.var(ddof=1) / n_per_variant)
        hits += abs(z) > stats.norm.ppf(1 - alpha / 2)
    return hits / n_sims
