"""Bayesian readouts: beta-binomial for conversion, normal model for continuous metrics.

Both return ``probability`` = P(treatment better than control) (in the metric's
good direction), a credible interval for the absolute (``ci_*``) and relative
(``rel_ci_*``) lift, and expected loss in ``extra`` - the average amount you
give up if you ship the variant and it is actually worse.

Prior choice (config: ``bayesian.prior``):
- ``weakly_informative`` (default): conversion -> Beta(1, 1); or, if a historical
  baseline is given, Beta centred on it worth ``prior_strength`` pseudo-users.
  Continuous -> N(0, tau^2) prior on the difference with tau = 10% of the control mean
  (lifts beyond +/-20% are a priori unlikely), which shrinks noisy estimates slightly.
- ``flat``: Beta(1, 1) / improper flat prior; results match frequentist intervals.

Example
-------
>>> from abkit.bayesian import beta_binomial
>>> r = beta_binomial(x_c=500, n_c=10000, x_t=560, n_t=10000)
>>> round(r.probability, 2)
0.97
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats

from abkit.results import StatResult


def beta_binomial(
    x_c: int, n_c: int, x_t: int, n_t: int, prior: str | tuple[float, float] = "weakly_informative",
    baseline: float | None = None, prior_strength: float = 20.0, cred: float = 0.95, n_draws: int = 200_000,
    seed: int = 42, direction: str = "increase", metric: str | None = None,
    control: str = "control", treatment: str = "treatment",
) -> StatResult:
    """Beta-binomial model for a conversion rate."""
    if isinstance(prior, tuple):
        a0, b0 = prior
    elif prior == "weakly_informative" and baseline is not None:
        a0, b0 = baseline * prior_strength, (1 - baseline) * prior_strength
    elif prior in ("weakly_informative", "flat"):
        a0, b0 = 1.0, 1.0
    else:
        raise ValueError(f"Unknown prior {prior!r}")
    ac, bc = a0 + x_c, b0 + n_c - x_c
    at, bt = a0 + x_t, b0 + n_t - x_t
    rng = np.random.default_rng(seed)
    pc, pt = rng.beta(ac, bc, n_draws), rng.beta(at, bt, n_draws)
    return _summarise(pc, pt, cred, direction, "bayesian.beta_binomial", metric, control, treatment,
                      {control: int(n_c), treatment: int(n_t)},
                      posteriors={control: {"dist": "beta", "a": ac, "b": bc}, treatment: {"dist": "beta", "a": at, "b": bt}},
                      prior={"dist": "beta", "a": a0, "b": b0})


def normal_model(
    control_values: Iterable[float], treatment_values: Iterable[float], prior: str = "weakly_informative",
    prior_sd_rel: float = 0.10, cred: float = 0.95, n_draws: int = 200_000, seed: int = 42,
    direction: str = "increase", metric: str | None = None, control: str = "control", treatment: str = "treatment",
) -> StatResult:
    """Normal model for a mean (large-sample likelihood) with a N(0, tau^2) prior on the difference."""
    c = np.asarray(pd.Series(control_values).dropna(), dtype=float)
    t = np.asarray(pd.Series(treatment_values).dropna(), dtype=float)
    if c.size < 2 or t.size < 2:
        raise ValueError("Need at least 2 values per group")
    mc, mt = c.mean(), t.mean()
    se_c, se_t = c.std(ddof=1) / np.sqrt(c.size), t.std(ddof=1) / np.sqrt(t.size)
    d_hat, se_d = mt - mc, np.sqrt(se_c**2 + se_t**2)
    if prior == "flat":
        post_m, post_sd, tau = d_hat, se_d, None
    elif prior == "weakly_informative":
        tau = prior_sd_rel * abs(mc) if mc != 0 else 10 * se_d
        w = tau**2 / (tau**2 + se_d**2)
        post_m, post_sd = w * d_hat, np.sqrt(w) * se_d
    else:
        raise ValueError(f"Unknown prior {prior!r}")
    rng = np.random.default_rng(seed)
    draws_c = rng.normal(mc, se_c, n_draws)
    draws_t = draws_c + rng.normal(post_m, post_sd, n_draws)
    r = _summarise(draws_c, draws_t, cred, direction, "bayesian.normal_model", metric, control, treatment,
                   {control: int(c.size), treatment: int(t.size)},
                   posteriors={control: {"dist": "normal", "mean": float(mc), "sd": float(se_c)},
                               treatment: {"dist": "normal", "mean": float(mc + post_m), "sd": float(np.sqrt(se_c**2 + post_sd**2))}},
                   prior={"dist": "normal", "mean": 0.0, "sd": tau} if tau else {"dist": "flat"})
    r.assumptions.append({"check": "large-sample normal likelihood for the mean", "passed": bool(min(c.size, t.size) >= 100),
                          "detail": f"n = {c.size:,}/{t.size:,}"})
    return r


def _summarise(pc, pt, cred, direction, method, metric, control, treatment, n, posteriors, prior) -> StatResult:
    sign = 1 if direction in ("increase", "no_decrease") else -1
    diff = pt - pc
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = pt / pc - 1
    rel = rel[np.isfinite(rel)]
    lo, hi = (1 - cred) / 2 * 100, (1 + cred) / 2 * 100
    prob = float((sign * diff > 0).mean())
    loss_t = float(np.maximum(-sign * diff, 0).mean())    # expected loss if we ship treatment
    loss_c = float(np.maximum(sign * diff, 0).mean())     # expected loss if we keep control
    return StatResult(
        method=method, metric=metric, control=control, treatment=treatment,
        estimate=float(diff.mean()), ci_low=float(np.percentile(diff, lo)), ci_high=float(np.percentile(diff, hi)),
        probability=prob, n=n, control_value=float(pc.mean()), treatment_value=float(pt.mean()),
        rel_lift=float(np.median(rel)), rel_ci_low=float(np.percentile(rel, lo)), rel_ci_high=float(np.percentile(rel, hi)),
        alpha=1 - cred,
        extra={"prob_beat_control": prob, "expected_loss_treatment": loss_t, "expected_loss_control": loss_c,
               "expected_loss_treatment_rel": loss_t / abs(float(pc.mean())) if pc.mean() else None,
               "credible_level": cred, "posteriors": posteriors, "prior": prior, "direction": direction,
               "variant_stats": {control: {"mean": float(pc.mean()), "ci_low": float(np.percentile(pc, lo)), "ci_high": float(np.percentile(pc, hi))},
                                 treatment: {"mean": float(pt.mean()), "ci_low": float(np.percentile(pt, lo)), "ci_high": float(np.percentile(pt, hi))}}},
        notes=["Credible interval: there is a {:.0%} posterior probability the true lift lies inside it.".format(cred)],
    )


def decide(r: StatResult | dict, threshold: float = 0.95, max_loss_rel: float = 0.001) -> str:
    """'ship' if P(beat) >= threshold and expected loss is tiny; 'dont_ship' if P(beat) <= 1 - threshold; else 'extend'."""
    get = (lambda k: r[k]) if isinstance(r, dict) else (lambda k: getattr(r, k))
    prob, extra = get("probability"), get("extra")
    loss = extra.get("expected_loss_treatment_rel") or 0
    if prob >= threshold and loss <= max_loss_rel:
        return "ship"
    if prob <= 1 - threshold:
        return "dont_ship"
    return "extend"


def posterior_prob_best(samples: dict[str, np.ndarray], direction: str = "increase") -> dict[str, float]:
    """For multi-arm tests: P(each variant is the best) from posterior draws of equal length."""
    names = list(samples)
    mat = np.vstack([samples[k] for k in names])
    best = mat.argmax(axis=0) if direction in ("increase", "no_decrease") else mat.argmin(axis=0)
    return {k: float((best == i).mean()) for i, k in enumerate(names)}
