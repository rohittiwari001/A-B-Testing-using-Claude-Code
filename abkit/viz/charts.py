"""The chart catalogue. Every function takes data straight from results.json and returns a Figure.

Each function takes ``title`` (the action title: state the takeaway), ``subtitle`` (metric and
units) and ``source`` (data file, dates, test, n). Colours come only from the palette; the key
element uses accent or a status colour, everything else is grey. Results carry a text label and a
filled (significant) / hollow (not significant) marker so colour is never the only cue.

Catalogue: lift_ci, metric_by_variant, cumulative_daily, daily_lift, segment_forest, power_curve,
sample_size_vs_mde, posterior_distributions, prob_to_beat_control, srm_bar, distribution_compare,
cuped_variance_reduction, sequential_boundaries, guardrail_scorecard, did_trends.

Example
-------
>>> from abkit.viz import charts, save_chart
>>> fig = charts.lift_ci([{"metric": "Conversion", "rel_lift": 0.032, "rel_ci_low": 0.012,
...                        "rel_ci_high": 0.052, "significant": True}], title="Variant B lifts conversion by 3.2%")
>>> fig.axes[0].get_xlabel()
'Relative lift vs control'
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
from matplotlib.ticker import FuncFormatter, MaxNLocator, PercentFormatter

from abkit.results import fmt_ci, fmt_num, fmt_p_stat, fmt_pct, fmt_prob, fmt_value
from abkit.viz.style import PALETTE, SIZES, apply_style, finalize, new_figure, status_color, variant_colors

P = PALETTE
ANN = SIZES["annotation"]

__all__ = ["apply_style"]  # re-exported so plotting scripts can import everything from here


def _x_values(records, x_key):
    """x values for time charts: ISO date strings become datetimes (whatever the column is called)."""
    import pandas as pd

    raw = [r[x_key] for r in records]
    if raw and isinstance(raw[0], str):
        parsed = pd.to_datetime(raw, errors="coerce")
        if parsed.notna().all():
            return parsed, True
    return np.array(raw), False


def _date_axis(ax) -> None:
    import matplotlib.dates as mdates

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))


def _pct_axis(axis, decimals: int = 0) -> None:
    axis.set_major_formatter(PercentFormatter(1.0, decimals=decimals))


def _num_axis(axis) -> None:
    def f(v, _):
        s = fmt_num(v, 0) if abs(v) >= 1000 else f"{v:g}"
        return s.replace("-", "−")

    axis.set_major_formatter(FuncFormatter(f))


def _end_label(ax, x, y, text, color, dx: float = 6) -> None:
    ax.annotate(text, (x, y), xytext=(dx, 0), textcoords="offset points", va="center", ha="left", fontsize=ANN,
                color=P["ink"], fontweight="bold" if color == P["accent"] else "normal")


def _dot_whisker(ax, rows: Sequence[Mapping[str, Any]], labels: Sequence[str], direction: str, bold_first: bool = False) -> None:
    y = np.arange(len(rows))[::-1]
    for yi, r in zip(y, rows):
        c = status_color(r, direction=direction)
        sig = c != P["neutral"]
        ax.plot([r["rel_ci_low"], r["rel_ci_high"]], [yi, yi], color=c, lw=2.2, solid_capstyle="round")
        ax.plot(r["rel_lift"], yi, "o", ms=9, color=c, mfc=c if sig else "white", mew=2)
        ax.annotate(f"{fmt_pct(r['rel_lift'])}  {fmt_ci(r['rel_ci_low'], r['rel_ci_high'])}", (r["rel_ci_high"], yi),
                    xytext=(8, 0), textcoords="offset points", va="center", fontsize=ANN, color=P["ink"])
    ax.axvline(0, color=P["ink"], lw=1)
    ax.set_yticks(y, labels)
    if bold_first and len(rows):
        ax.get_yticklabels()[0].set_fontweight("bold")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    lo = min(r["rel_ci_low"] for r in rows)
    hi = max(r["rel_ci_high"] for r in rows)
    span = max(max(hi, 0) - min(lo, 0), 1e-4)
    ax.set_xlim(min(lo, 0) - 0.08 * span, max(hi, 0) + 0.45 * span)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    _pct_axis(ax.xaxis, 1 if span < 0.05 else 0)
    ax.set_xlabel("Relative lift vs control")
    ax.spines["left"].set_visible(False)


def _legend_note(ax, text: str = "Filled = statistically significant, hollow = not significant") -> None:
    ax.text(1.0, -0.13, text, transform=ax.transAxes, ha="right", va="top", fontsize=SIZES["source"], color=P["grey_mid"])


# --------------------------------------------------------------------------- 1. lift_ci


def lift_ci(rows: Sequence[Mapping[str, Any]], title: str, subtitle: str = "", source: str = "",
            label_key: str = "metric", direction: str = "increase"):
    """Dot-and-whisker of relative lift with CI per metric (or per comparison), zero line."""
    labels = [str(r.get(label_key) or f"{r.get('treatment')} vs {r.get('control')}") for r in rows]
    fig, ax = new_figure(left=0.22)
    _dot_whisker(ax, rows, labels, direction)
    _legend_note(ax)
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 2. metric_by_variant


def metric_by_variant(variant_stats: Mapping[str, Mapping[str, float]], title: str, subtitle: str = "", source: str = "",
                      control: str | None = None, metric_type: str | None = None, ylabel: str = ""):
    """Bars of the metric per variant with CI error bars and direct value labels."""
    names = list(variant_stats)
    if control in names:
        names.remove(control)
        names.insert(0, control)
    colors = variant_colors(names, control)
    fig, ax = new_figure()
    x = np.arange(len(names))
    means = [variant_stats[n]["mean"] for n in names]
    lo = [variant_stats[n]["mean"] - variant_stats[n]["ci_low"] for n in names]
    hi = [variant_stats[n]["ci_high"] - variant_stats[n]["mean"] for n in names]
    ax.bar(x, means, width=0.55, color=[colors[n] for n in names])
    ax.errorbar(x, means, yerr=[lo, hi], fmt="none", ecolor=P["ink"], elinewidth=1.2, capsize=5)
    for xi, m, h in zip(x, means, hi):
        ax.annotate(fmt_value(m, metric_type), (xi, m + h), xytext=(0, 5), textcoords="offset points", ha="center",
                    va="bottom", fontsize=ANN, fontweight="bold", color=P["ink"])
    ax.set_xticks(x, names)
    ax.set_ylim(0, max(m + h for m, h in zip(means, hi)) * 1.18)
    if metric_type == "binary":
        _pct_axis(ax.yaxis)
    else:
        _num_axis(ax.yaxis)
    ax.set_ylabel(ylabel)
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 3. cumulative_daily


def cumulative_daily(records: Sequence[Mapping[str, Any]], title: str, subtitle: str = "", source: str = "",
                     control: str = "control", treatment: str = "treatment", metric_type: str | None = None, x_key: str = "date"):
    """Cumulative metric per variant over time (records from time_effects.cumulative_effects)."""
    fig, ax = new_figure(right=0.84)
    x, is_date = _x_values(records, x_key)
    colors = variant_colors([control, treatment], control)
    for key, name in (("control_mean", control), ("treatment_mean", treatment)):
        y = [r[key] for r in records]
        ax.plot(x, y, color=colors[name], lw=2)
        _end_label(ax, x[-1], y[-1], f"{name} {fmt_value(y[-1], metric_type)}", colors[name])
    if metric_type == "binary":
        _pct_axis(ax.yaxis, 1)
    else:
        _num_axis(ax.yaxis)
    if is_date:
        _date_axis(ax)
    ax.set_ylabel("Cumulative value")
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 4. daily_lift


def daily_lift(records: Sequence[Mapping[str, Any]], title: str, subtitle: str = "", source: str = "",
               x_key: str = "date", overall: float | None = None, xlabel: str = ""):
    """Per-period relative lift with a CI band - the novelty / primacy check."""
    fig, ax = new_figure()
    x, is_date = _x_values(records, x_key)
    y = np.array([r["rel_lift"] for r in records], dtype=float)
    lo = np.array([r["rel_ci_low"] for r in records], dtype=float)
    hi = np.array([r["rel_ci_high"] for r in records], dtype=float)
    ax.fill_between(x, lo, hi, color=P["grey_light"], lw=0)
    ax.plot(x, y, color=P["accent"], lw=2, marker="o", ms=5)
    ax.axhline(0, color=P["ink"], lw=1)
    if overall is not None:
        ax.axhline(overall, color=P["grey_mid"], lw=1.2, ls="--")
        ax.annotate(f"Overall {fmt_pct(overall)}", (x[-1], overall), xytext=(0, 5), textcoords="offset points",
                    ha="right", fontsize=ANN, color=P["grey_mid"])
    _pct_axis(ax.yaxis)
    if is_date:
        _date_axis(ax)
    else:
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylabel("Relative lift (CI band)")
    ax.set_xlabel(xlabel)
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 5. segment_forest


def segment_forest(rows: Sequence[Mapping[str, Any]], title: str, subtitle: str = "", source: str = "", direction: str = "increase"):
    """Forest plot of relative lift by segment; an 'All' row (if present) sits on top in bold."""
    rows = sorted(rows, key=lambda r: (r.get("segment") != "All", str(r.get("segment"))))
    labels = [f"{r.get('segment')}  (n={fmt_num(sum((r.get('n') or {}).values()))})" for r in rows]
    fig, ax = new_figure(left=0.24)
    _dot_whisker(ax, rows, labels, direction, bold_first=rows[0].get("segment") == "All")
    if rows[0].get("segment") == "All" and len(rows) > 1:
        ax.axhline(len(rows) - 1.5, color=P["grey_light"], lw=1)
    _legend_note(ax, "Filled = significant after correction, hollow = not significant")
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 6. power_curve


def power_curve(records: Sequence[Mapping[str, Any]], title: str, subtitle: str = "", source: str = "",
                target_power: float = 0.8, highlight_mde: float | None = None, planned_n: float | None = None):
    """Power vs sample size per variant, one line per MDE (records from power.power_curve)."""
    import pandas as pd

    df = pd.DataFrame(records)
    mdes = sorted(df["mde"].unique())
    if len(mdes) > 4:
        raise ValueError("Show at most four MDE lines")
    highlight = highlight_mde if highlight_mde is not None else mdes[len(mdes) // 2]
    fig, ax = new_figure()
    for m in mdes:
        d = df[df["mde"] == m].sort_values("n")
        key = bool(np.isclose(m, highlight))
        c = P["accent"] if key else P["grey_mid"]
        ax.plot(d["n"], d["power"], color=c, lw=2.4 if key else 1.5)
        i = int(np.argmin(np.abs(d["power"].to_numpy() - 0.5)))
        ax.annotate(f"MDE {fmt_pct(m)}", (d["n"].iloc[i], d["power"].iloc[i]), xytext=(-8, 0), textcoords="offset points",
                    ha="right", va="center", fontsize=ANN, color=P["ink"], fontweight="bold" if key else "normal")
    ax.axhline(target_power, color=P["ink"], lw=1, ls="--")
    ax.annotate(f"{target_power:.0%} power", (df["n"].min(), target_power), xytext=(0, 4), textcoords="offset points",
                fontsize=ANN, color=P["ink"])
    if planned_n:
        ax.axvline(planned_n, color=P["grey_mid"], lw=1, ls=":")
        ax.annotate(f"Available n = {fmt_num(planned_n)}", (planned_n, 0.05), xytext=(4, 0), textcoords="offset points",
                    fontsize=ANN, color=P["grey_mid"])
    ax.set_xscale("log")
    _num_axis(ax.xaxis)
    _pct_axis(ax.yaxis)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Units per variant (log scale)")
    ax.set_ylabel("Power")
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 7. sample_size_vs_mde


def sample_size_vs_mde(records: Sequence[Mapping[str, Any]], title: str, subtitle: str = "", source: str = "",
                       highlight_mde: float | None = None):
    """Required units per variant for each relative MDE (records from power.sample_size_table)."""
    fig, ax = new_figure()
    x = np.array([r["mde"] for r in records])
    y = np.array([r["n_per_variant"] for r in records])
    ax.plot(x, y, color=P["grey_mid"], lw=1.5, zorder=1)
    for r in records:
        key = highlight_mde is not None and bool(np.isclose(r["mde"], highlight_mde))
        ax.plot(r["mde"], r["n_per_variant"], "o", ms=9 if key else 7, color=P["accent"] if key else P["navy"], zorder=2)
        lab = f"{fmt_num(r['n_per_variant'])}" + (f"\n{r['days']} days" if r.get("days") else "")
        ax.annotate(lab, (r["mde"], r["n_per_variant"]), xytext=(7, 4), textcoords="offset points", fontsize=ANN,
                    color=P["ink"], fontweight="bold" if key else "normal")
    _num_axis(ax.yaxis)
    _pct_axis(ax.xaxis, 1)
    ax.set_xlim(x.min() * 0.85, x.max() * 1.15)
    ax.set_ylim(0, y.max() * 1.15)
    ax.set_xlabel("Minimum detectable effect (relative)")
    ax.set_ylabel("Units per variant")
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 8. posterior_distributions


def posterior_distributions(posteriors: Mapping[str, Mapping[str, Any]], title: str, subtitle: str = "", source: str = "",
                            control: str | None = None, metric_type: str | None = None):
    """Posterior density of each variant's metric (params from bayesian results extra['posteriors'])."""
    from scipy import stats

    dists = {name: (stats.beta(p["a"], p["b"]) if p["dist"] == "beta" else stats.norm(p["mean"], p["sd"]))
             for name, p in posteriors.items()}
    lo = min(d.ppf(0.0005) for d in dists.values())
    hi = max(d.ppf(0.9995) for d in dists.values())
    x = np.linspace(lo, hi, 600)
    colors = variant_colors(list(posteriors), control)
    fig, ax = new_figure()
    for name, d in dists.items():
        y = d.pdf(x)
        ax.fill_between(x, y, color=colors[name], alpha=0.18, lw=0)
        ax.plot(x, y, color=colors[name], lw=2)
        ax.annotate(f"{name}\n{fmt_value(d.mean(), metric_type)}", (d.mean(), y.max()), xytext=(0, 6), textcoords="offset points",
                    ha="center", va="bottom", fontsize=ANN, color=P["ink"])
    ax.set_ylim(0, max(d.pdf(x).max() for d in dists.values()) * 1.25)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.grid(False)
    if metric_type == "binary":
        _pct_axis(ax.xaxis, 1)
    else:
        _num_axis(ax.xaxis)
    ax.set_xlabel("Plausible values of the metric (posterior)")
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 9. prob_to_beat_control


def prob_to_beat_control(probs: Mapping[str, float], title: str, subtitle: str = "", source: str = "", threshold: float = 0.95):
    """Horizontal bars of P(variant beats control) with the decision threshold."""
    names = list(probs)
    fig, ax = new_figure(left=0.18)
    y = np.arange(len(names))[::-1]
    for yi, n in zip(y, names):
        p = probs[n]
        ax.barh(yi, p, height=0.5, color=P["accent"] if p >= threshold else P["grey_mid"])
        ax.annotate(fmt_prob(p), (p, yi), xytext=(6, 0), textcoords="offset points", va="center", fontsize=ANN,
                    fontweight="bold", color=P["ink"])
    ax.axvline(threshold, color=P["ink"], lw=1, ls="--")
    ax.annotate(f"Decision threshold {fmt_prob(threshold)}", (threshold, y.max() + 0.45), xytext=(-4, 0), textcoords="offset points",
                ha="right", fontsize=ANN, color=P["ink"])
    ax.set_yticks(y, names)
    ax.set_xlim(0, 1.12)
    ax.set_ylim(-0.6, len(names) - 0.2)
    _pct_axis(ax.xaxis)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlabel("Probability of beating control")
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 10. srm_bar


def srm_bar(observed: Mapping[str, int], expected_share: Mapping[str, float], title: str, subtitle: str = "", source: str = "",
            p_value: float | None = None, threshold: float = 0.001):
    """Observed traffic share per variant against the intended split (dashed markers)."""
    names = list(expected_share)
    total = sum(observed[n] for n in names)
    share = {n: observed[n] / total for n in names}
    srm = p_value is not None and p_value < threshold
    short = min(names, key=lambda n: share[n] - expected_share[n])   # the variant missing the most units
    fig, ax = new_figure()
    x = np.arange(len(names))
    for xi, n in zip(x, names):
        c = P["negative"] if (srm and n == short) else P["grey_mid"]
        ax.bar(xi, share[n], width=0.5, color=c)
        ax.plot([xi - 0.32, xi + 0.32], [expected_share[n]] * 2, color=P["ink"], lw=1.6, ls="--")
        ax.annotate(f"{fmt_prob(share[n])} observed\n{fmt_prob(expected_share[n])} expected\n(n={fmt_num(observed[n])})",
                    (xi, max(share[n], expected_share[n])), xytext=(0, 6), textcoords="offset points", ha="center",
                    fontsize=ANN, color=P["ink"])
    ax.set_xticks(x, names)
    ax.set_ylim(0, max(max(share.values()), max(expected_share.values())) * 1.35)
    _pct_axis(ax.yaxis)
    ax.set_ylabel("Share of units")
    if p_value is not None:
        verdict = "SRM detected" if srm else "No SRM"
        ax.text(1.0, 1.02, f"{verdict}: chi-square {fmt_p_stat(p_value)} (threshold {threshold})", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=ANN, color=P["negative"] if srm else P["ink"], fontweight="bold")
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 11. distribution_compare


def histogram_data(df, metric: str, variant_col: str, bins: int = 40, clip_quantile: float | None = 0.99,
                   drop_zeros: bool = False) -> dict[str, Any]:
    """Shared-bin density per variant, ready to store in results.json and pass to distribution_compare."""
    d = df[[metric, variant_col]].dropna()
    if drop_zeros:
        d = d[d[metric] != 0]
    hi = d[metric].quantile(clip_quantile) if clip_quantile else d[metric].max()
    edges = np.linspace(d[metric].min(), hi, bins + 1)
    out = {"edges": edges.tolist(), "variants": {}, "clip_quantile": clip_quantile, "drop_zeros": drop_zeros}
    for v, g in d.groupby(variant_col):
        dens, _ = np.histogram(g[metric].clip(upper=hi), bins=edges, density=True)
        out["variants"][str(v)] = dens.tolist()
    return out


def distribution_compare(hist: Mapping[str, Any], title: str, subtitle: str = "", source: str = "", control: str | None = None,
                         kind: str = "hist", xlabel: str = ""):
    """Overlaid step histograms (or ECDFs, ``kind='ecdf'``) per variant on shared bins (from :func:`histogram_data`)."""
    edges = np.asarray(hist["edges"])
    colors = variant_colors(list(hist["variants"]), control)
    fig, ax = new_figure()
    widths = np.diff(edges)
    for name, dens in hist["variants"].items():
        dens = np.asarray(dens)
        y = np.cumsum(dens * widths) if kind == "ecdf" else dens
        ax.stairs(y, edges, color=colors[name], lw=2, fill=False, label=name)
    ax.legend(loc="lower right" if kind == "ecdf" else "upper right", handlelength=1.5)
    if kind == "ecdf":
        _pct_axis(ax.yaxis)
        ax.set_ylabel("Share of units at or below value")
    else:
        ax.set_yticks([])
        ax.set_ylabel("Density")
    _num_axis(ax.xaxis)
    ax.set_xlabel(xlabel)
    if hist.get("clip_quantile"):
        ax.text(1.0, -0.13, f"Values above the {hist['clip_quantile']:.0%} quantile are shown in the last bin",
                transform=ax.transAxes, ha="right", va="top", fontsize=SIZES["source"], color=P["grey_mid"])
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 12. cuped_variance_reduction


def cuped_variance_reduction(rows: Sequence[Mapping[str, Any]], title: str, subtitle: str = "", source: str = ""):
    """CI width before vs after CUPED for each metric; label shows how much narrower the interval is.

    ``rows``: ``{"label", "ci_width_unadjusted", "ci_width_adjusted"}`` (from cuped results' extra).
    """
    fig, ax = new_figure(left=0.2)
    y = np.arange(len(rows))[::-1]
    h = 0.34
    for yi, r in zip(y, rows):
        u, a = r["ci_width_unadjusted"], r["ci_width_adjusted"]
        ax.barh(yi + h / 2 + 0.02, u, height=h, color=P["grey_mid"])
        ax.barh(yi - h / 2 - 0.02, a, height=h, color=P["accent"])
        ax.annotate("Unadjusted " + fmt_num(u), (u, yi + h / 2 + 0.02), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=ANN, color=P["ink"])
        ax.annotate(f"CUPED {fmt_num(a)}  ({fmt_pct(a / u - 1, 0)} width)", (a, yi - h / 2 - 0.02), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=ANN, fontweight="bold", color=P["ink"])
    ax.set_yticks(y, [r["label"] for r in rows])
    ax.set_xlim(0, max(r["ci_width_unadjusted"] for r in rows) * 1.45)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    _num_axis(ax.xaxis)
    ax.set_xlabel("Width of the confidence interval for the difference (metric units)")
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 13. sequential_boundaries


def sequential_boundaries(boundary: Sequence[Mapping[str, Any]], title: str, subtitle: str = "", source: str = "",
                          observed: Sequence[Mapping[str, Any]] | None = None, fixed_z: float = 1.96):
    """Efficacy boundaries (+/- z) by information fraction with the observed z path."""
    t = np.array([b["info_fraction"] for b in boundary])
    z = np.array([b["z_boundary"] for b in boundary])
    fig, ax = new_figure(right=0.82)
    for sign in (1, -1):
        ax.plot(t, sign * z, color=P["navy"], lw=2, marker="o", ms=5)
    ax.fill_between(t, -z, z, color=P["grey_light"], alpha=0.5, lw=0)
    _end_label(ax, t[-1], z[-1], "Stop: treatment wins", P["navy"])
    _end_label(ax, t[-1], -z[-1], "Stop: treatment loses", P["navy"])
    ax.axhline(fixed_z, color=P["grey_mid"], lw=1, ls=":")
    ax.axhline(-fixed_z, color=P["grey_mid"], lw=1, ls=":")
    ax.annotate(f"±{fixed_z} fixed horizon", (0.01, fixed_z), xytext=(0, 3), textcoords="offset points",
                fontsize=SIZES["source"], color=P["grey_mid"])
    if observed:
        ot = [o["info_fraction"] for o in observed]
        oz = [o["z"] for o in observed]
        ax.plot(ot, oz, color=P["accent"], lw=2.4, marker="o", ms=8)
        ax.annotate(f"Observed z = {oz[-1]:.2f}", (ot[-1], oz[-1]), xytext=(0, 10), textcoords="offset points", ha="center",
                    fontsize=ANN, fontweight="bold", color=P["ink"])
    ax.axhline(0, color=P["ink"], lw=1)
    _pct_axis(ax.xaxis)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Information fraction (share of planned sample)")
    ax.set_ylabel("z statistic")
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 14. guardrail_scorecard


def guardrail_scorecard(rows: Sequence[Mapping[str, Any]], title: str, subtitle: str = "", source: str = ""):
    """Table-like chart: metric, change, CI, margin and a coloured PASS / BREACH / INCONCLUSIVE status."""
    from matplotlib.patches import FancyBboxPatch

    fig, ax = new_figure(left=0.04, right=0.96, bottom=0.1)
    ax.axis("off")
    cols = [("Guardrail", 0.0), ("Change", 0.34), ("CI", 0.49), ("NI margin", 0.70), ("Status", 0.84)]
    row_h = min(0.16, 0.85 / max(len(rows), 1))
    top = 0.95
    for name, x in cols:
        ax.text(x, top, name.upper(), fontsize=SIZES["source"] + 1, color=P["grey_mid"], fontweight="bold", va="center")
    ax.plot([0, 1], [top - row_h * 0.5] * 2, color=P["ink"], lw=1)
    colors = {"pass": P["positive"], "breach": P["negative"], "inconclusive": P["neutral"]}
    for i, r in enumerate(rows):
        y = top - row_h * (i + 1)
        extra = r.get("extra") or {}
        status = str(extra.get("status") or r.get("status") or "inconclusive")
        margin = extra.get("margin_rel", r.get("margin_rel"))
        ax.text(0.0, y, str(r.get("metric")), fontsize=ANN + 1, color=P["ink"], va="center", fontweight="bold")
        ax.text(0.34, y, fmt_pct(r.get("rel_lift")), fontsize=ANN + 1, color=P["ink"], va="center")
        ax.text(0.49, y, fmt_ci(r.get("rel_ci_low"), r.get("rel_ci_high")), fontsize=ANN, color=P["ink"], va="center")
        ax.text(0.70, y, f"{margin:.1%}" if margin is not None else "n/a", fontsize=ANN, color=P["ink"], va="center")
        ax.add_patch(FancyBboxPatch((0.84, y - row_h * 0.28), 0.15, row_h * 0.56, boxstyle="round,pad=0.005,rounding_size=0.01",
                                    color=colors.get(status, P["neutral"]), transform=ax.transAxes, clip_on=False))
        ax.text(0.915, y, status.upper(), fontsize=ANN, color=P["white"], va="center", ha="center", fontweight="bold")
        ax.plot([0, 1], [y - row_h * 0.5] * 2, color=P["grey_light"], lw=0.8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    finalize(fig, title, subtitle, source)
    return fig


# --------------------------------------------------------------------------- 15. did_trends


def did_trends(records: Sequence[Mapping[str, Any]], title: str, subtitle: str = "", source: str = "", time_key: str = "week",
               intervention=None, treated_label: str = "Launch regions", control_label: str = "Other regions",
               counterfactual_key: str | None = None, ylabel: str = ""):
    """Treated vs control group over time with the intervention marked (records from quasi.group_trends)."""
    fig, ax = new_figure(right=0.84)
    x = [r[time_key] for r in records]
    yc = [r["control"] for r in records]
    yt = [r["treated"] for r in records]
    ax.plot(x, yc, color=P["grey_mid"], lw=2)
    ax.plot(x, yt, color=P["accent"], lw=2.4)
    if counterfactual_key:
        ax.plot(x, [r[counterfactual_key] for r in records], color=P["accent"], lw=1.4, ls="--")
    _end_label(ax, x[-1], yc[-1], control_label, P["grey_mid"])
    _end_label(ax, x[-1], yt[-1], treated_label, P["accent"])
    if intervention is not None:
        ax.axvline(intervention, color=P["ink"], lw=1, ls="--")
        ax.annotate("Launch", (intervention, ax.get_ylim()[1]), xytext=(4, -12), textcoords="offset points", fontsize=ANN,
                    color=P["ink"])
    _num_axis(ax.yaxis)
    ax.set_xlabel(time_key.replace("_", " ").capitalize())
    ax.set_ylabel(ylabel)
    finalize(fig, title, subtitle, source)
    return fig


CATALOGUE = {
    "lift_ci": lift_ci, "metric_by_variant": metric_by_variant, "cumulative_daily": cumulative_daily, "daily_lift": daily_lift,
    "segment_forest": segment_forest, "power_curve": power_curve, "sample_size_vs_mde": sample_size_vs_mde,
    "posterior_distributions": posterior_distributions, "prob_to_beat_control": prob_to_beat_control, "srm_bar": srm_bar,
    "distribution_compare": distribution_compare, "cuped_variance_reduction": cuped_variance_reduction,
    "sequential_boundaries": sequential_boundaries, "guardrail_scorecard": guardrail_scorecard, "did_trends": did_trends,
}
