"""Heterogeneous treatment effects: pre-specified segments, interaction tests, Simpson's paradox.

Rules of thumb (see heterogeneous_effects.md):
- Only pre-specified segments are confirmatory; anything else is exploratory.
- Correct across segments (Benjamini-Hochberg by default).
- A significant effect in one segment and not another is NOT evidence of a
  difference between segments - use :func:`interaction_test` for that.

Example
-------
>>> from abkit.segments import segment_effects
>>> rows = segment_effects(df, "converted", "binary", "platform", "variant", "control", "treatment")  # doctest: +SKIP
>>> [r.segment for r in rows]                                                                        # doctest: +SKIP
['All', 'Android', 'Web', 'iOS']
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from abkit.frequentist import compare
from abkit.multiple_testing import apply_correction
from abkit.results import StatResult


def segment_effects(
    df: pd.DataFrame, metric: str, metric_type: str, segment_col: str, variant_col: str, control: str, treatment: str,
    alpha: float = 0.05, correction: str = "benjamini-hochberg", min_n: int = 100, include_overall: bool = True,
) -> list[StatResult]:
    """Effect per segment level (plus an 'All' row). Correction applies across segment rows only."""
    out = []
    if include_overall:
        r = compare(df, metric, metric_type, variant_col, control, treatment, alpha, role="segment")
        r.segment = "All"
        out.append(r)
    seg_rows = []
    for level, g in df.groupby(segment_col):
        n = g[variant_col].astype(str).value_counts()
        if min(n.get(str(control), 0), n.get(str(treatment), 0)) < min_n:
            continue
        r = compare(g, metric, metric_type, variant_col, control, treatment, alpha, role="segment")
        r.segment = str(level)
        r.extra["segment_col"] = segment_col
        r.extra["share"] = float(len(g) / len(df))
        seg_rows.append(r)
    if len(seg_rows) > 1:
        apply_correction(seg_rows, correction, alpha)
    return out + seg_rows


def interaction_test(
    df: pd.DataFrame, metric: str, segment_col: str, variant_col: str, control: str, treatment: str, alpha: float = 0.05,
) -> StatResult:
    """Joint Wald test that the (absolute) treatment effect is the same in every segment.

    OLS of metric on treatment x segment with HC1 SEs (a linear probability model for
    binary metrics). ``p_value`` < alpha means the effect genuinely differs across segments.
    """
    import statsmodels.formula.api as smf

    d = df[df[variant_col].astype(str).isin([str(control), str(treatment)])][[metric, segment_col, variant_col]].dropna().copy()
    d["_t"] = (d[variant_col].astype(str) == str(treatment)).astype(float)
    d["_s"] = d[segment_col].astype(str)
    fit = smf.ols(f"Q('{metric}') ~ _t * C(_s)", data=d).fit(cov_type="HC1")
    inter = [n for n in fit.params.index if n.startswith("_t:")]
    if not inter:
        raise ValueError(f"Segment column {segment_col!r} has a single level")
    R = np.zeros((len(inter), len(fit.params)))
    for i, name in enumerate(inter):
        R[i, list(fit.params.index).index(name)] = 1
    w = fit.wald_test(R, scalar=True)
    p = float(w.pvalue)
    return StatResult(
        method="segments.interaction_test", metric=metric, estimate=float(w.statistic), p_value=p, alpha=alpha,
        significant=p < alpha, segment=segment_col, n={"rows": int(len(d)), "levels": int(d["_s"].nunique())},
        extra={"df": len(inter), "interaction_terms": {k: float(fit.params[k]) for k in inter}},
        notes=["Tests heterogeneity of the absolute effect; " +
               ("evidence that the effect differs by segment." if p < alpha else "no evidence the effect differs by segment.")],
    )


def simpsons_check(
    df: pd.DataFrame, metric: str, segment_col: str, variant_col: str, control: str, treatment: str,
) -> StatResult:
    """Compare the pooled difference with a segment-standardised difference.

    Flags Simpson's paradox when the pooled and standardised effects have opposite signs,
    and reports how different the segment mix is between variants (the usual cause).
    """
    d = df[df[variant_col].astype(str).isin([str(control), str(treatment)])]
    is_t = d[variant_col].astype(str) == str(treatment)
    pooled = float(d.loc[is_t, metric].mean() - d.loc[~is_t, metric].mean())
    by = d.groupby([segment_col, is_t.rename("_t")])[metric].mean().unstack()
    share = d[segment_col].value_counts(normalize=True)
    diffs = (by[True] - by[False]).dropna()
    standardised = float((diffs * share.reindex(diffs.index)).sum() / share.reindex(diffs.index).sum())
    mix = pd.crosstab(d[segment_col], is_t, normalize="columns")
    mix_gap = float((mix[True] - mix[False]).abs().max()) if True in mix and False in mix else 0.0
    flagged = bool(np.sign(pooled) != np.sign(standardised) and abs(standardised) > 0)
    signs = {str(k): float(v) for k, v in diffs.items()}
    return StatResult(
        method="segments.simpsons_check", metric=metric, estimate=standardised, segment=segment_col,
        significant=flagged, extra={"pooled_diff": pooled, "standardised_diff": standardised, "segment_diffs": signs,
                                    "max_mix_gap": mix_gap, "flagged": flagged},
        notes=["Simpson's paradox: pooled and within-segment effects point in opposite directions." if flagged
               else "Pooled and segment-standardised effects agree in direction."],
    )
