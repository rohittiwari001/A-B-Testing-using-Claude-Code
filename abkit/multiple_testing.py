"""Multiple-testing corrections: Bonferroni, Holm, Benjamini-Hochberg.

Use Holm for a small family of secondary metrics (controls the family-wise error
rate, uniformly more powerful than Bonferroni); Benjamini-Hochberg for many
segments / exploratory cuts (controls the false discovery rate).

Example
-------
>>> from abkit.multiple_testing import adjust_pvalues
>>> [round(float(p), 3) for p in adjust_pvalues([0.01, 0.02, 0.04], "holm")]
[0.03, 0.04, 0.04]
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from abkit.results import StatResult

METHODS = {"none": None, "bonferroni": "bonferroni", "holm": "holm", "benjamini-hochberg": "fdr_bh"}


def adjust_pvalues(pvalues: Sequence[float], method: str = "holm") -> np.ndarray:
    """Return adjusted p-values (capped at 1). ``method``: none | bonferroni | holm | benjamini-hochberg."""
    if method not in METHODS:
        raise ValueError(f"Unknown correction {method!r}; choose from {list(METHODS)}")
    p = np.asarray(pvalues, dtype=float)
    if p.size == 0 or method == "none":
        return p.copy()
    if np.any((p < 0) | (p > 1)):
        raise ValueError("p-values must lie in [0, 1]")
    from statsmodels.stats.multitest import multipletests

    return multipletests(p, method=METHODS[method])[1]


def apply_correction(results: list[StatResult | dict[str, Any]], method: str, alpha: float = 0.05) -> list:
    """Set ``p_value_adjusted``, ``correction`` and ``significant`` on each result in place.

    Results without a p-value are left untouched. Returns the same list.
    """
    idx = [i for i, r in enumerate(results) if _get(r, "p_value") is not None]
    adj = adjust_pvalues([_get(results[i], "p_value") for i in idx], method)
    for i, p_adj in zip(idx, adj):
        r = results[i]
        _set(r, "p_value_adjusted", float(p_adj))
        _set(r, "correction", method)
        _set(r, "significant", bool(p_adj < alpha))
        notes = _get(r, "notes") or []
        notes.append(f"{method} correction across {len(idx)} tests (alpha {alpha}).")
        _set(r, "notes", notes)
    return results


def _get(r, key):
    return r.get(key) if isinstance(r, dict) else getattr(r, key)


def _set(r, key, value):
    if isinstance(r, dict):
        r[key] = value
    else:
        setattr(r, key, value)
