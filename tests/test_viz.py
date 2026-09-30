"""Style tokens, chart catalogue rendering, palette discipline and the manifest."""

import json

import matplotlib
import numpy as np
import pytest
from matplotlib.colors import to_hex, to_rgba

matplotlib.use("Agg")

from abkit import power, sequential  # noqa: E402
from abkit.viz import PALETTE, apply_style, charts, finalize, new_figure, save_chart, variant_colors  # noqa: E402

ALLOWED = {v.lower() for v in PALETTE.values()} | {"#000000"}

ROW = {"metric": "Conversion", "rel_lift": 0.032, "rel_ci_low": 0.012, "rel_ci_high": 0.052, "significant": True,
       "p_value": 0.002, "segment": "All", "n": {"control": 100, "treatment": 100}}
VS = {"control": {"mean": 0.34, "ci_low": 0.335, "ci_high": 0.345}, "treatment": {"mean": 0.35, "ci_low": 0.345, "ci_high": 0.355}}
DAILY = [{"date": f"2026-09-{d:02d}", "control_mean": 0.34, "treatment_mean": 0.35 + d / 1000, "rel_lift": 0.03,
          "rel_ci_low": 0.0, "rel_ci_high": 0.06} for d in range(1, 8)]


def sample_calls():
    curve = power.power_curve("proportion", 0.3, [0.03, 0.05], [1000, 10_000, 100_000]).to_dict("records")
    table = power.sample_size_table("proportion", 0.3, [0.03, 0.05], daily_units=4000).to_dict("records")
    bnd = sequential.boundaries([0.5, 1.0]).to_dict("records")
    hist = {"edges": [0, 1, 2, 3], "variants": {"control": [0.2, 0.5, 0.3], "treatment": [0.1, 0.5, 0.4]}}
    guard = [{"metric": "Revenue", "rel_lift": 0.01, "rel_ci_low": -0.002, "rel_ci_high": 0.02, "extra": {"status": "pass", "margin_rel": 0.01}}]
    return {
        "lift_ci": lambda: charts.lift_ci([ROW, {**ROW, "metric": "Revenue", "significant": False}], "t"),
        "metric_by_variant": lambda: charts.metric_by_variant(VS, "t", control="control", metric_type="binary"),
        "cumulative_daily": lambda: charts.cumulative_daily(DAILY, "t", metric_type="binary"),
        "daily_lift": lambda: charts.daily_lift(DAILY, "t", overall=0.03),
        "segment_forest": lambda: charts.segment_forest([ROW, {**ROW, "segment": "iOS", "rel_lift": -0.02, "rel_ci_low": -0.04,
                                                                "rel_ci_high": -0.01}], "t"),
        "power_curve": lambda: charts.power_curve(curve, "t", planned_n=20_000),
        "sample_size_vs_mde": lambda: charts.sample_size_vs_mde(table, "t", highlight_mde=0.05),
        "posterior_distributions": lambda: charts.posterior_distributions(
            {"control": {"dist": "beta", "a": 340, "b": 660}, "treatment": {"dist": "beta", "a": 360, "b": 640}}, "t", control="control"),
        "prob_to_beat_control": lambda: charts.prob_to_beat_control({"B": 0.97, "C": 0.6}, "t"),
        "srm_bar": lambda: charts.srm_bar({"control": 5200, "treatment": 4800}, {"control": 0.5, "treatment": 0.5}, "t", p_value=1e-4),
        "distribution_compare": lambda: charts.distribution_compare(hist, "t", control="control"),
        "cuped_variance_reduction": lambda: charts.cuped_variance_reduction([{"label": "m", "ci_width_unadjusted": 3, "ci_width_adjusted": 2}], "t"),
        "sequential_boundaries": lambda: charts.sequential_boundaries(bnd, "t", observed=[{"info_fraction": 0.5, "z": 1.5}]),
        "guardrail_scorecard": lambda: charts.guardrail_scorecard(guard, "t"),
        "did_trends": lambda: charts.did_trends([{"week": w, "control": 100 + w, "treated": 101 + w * 1.1} for w in range(10)], "t", intervention=5),
    }


def figure_colors(fig):
    cols = set()
    for obj in fig.findobj():
        if hasattr(obj, "get_visible") and not obj.get_visible():
            continue
        for getter in ("get_color", "get_facecolor", "get_edgecolor", "get_markerfacecolor", "get_markeredgecolor"):
            if not hasattr(obj, getter):
                continue
            try:
                val = getattr(obj, getter)()
            except Exception:
                continue
            vals = val if (isinstance(val, np.ndarray) and val.ndim == 2) else [val]
            for v in vals:
                try:
                    rgba = to_rgba(v)
                except (ValueError, TypeError):
                    continue
                if rgba[3] > 0:
                    cols.add(to_hex(rgba[:3]))
    return cols


def test_palette_tokens_are_the_spec():
    assert PALETTE["ink"] == "#1A1A1A" and PALETTE["navy"] == "#0B2545" and PALETTE["accent"] == "#2251FF"
    assert PALETTE["accent_light"] == "#9DB4FF" and PALETTE["grey_mid"] == "#8C8C8C" and PALETTE["grey_light"] == "#E3E3E3"
    assert PALETTE["positive"] == "#1B7F5A" and PALETTE["negative"] == "#C0392B" and PALETTE["neutral"] == "#B08900"


def test_apply_style_sets_fonts_and_spines():
    apply_style()
    rc = matplotlib.rcParams
    assert rc["font.sans-serif"][0] == "Arial" and not rc["axes.spines.top"] and not rc["axes.spines.right"]
    assert rc["savefig.dpi"] == 300 and rc["svg.fonttype"] == "none"


def test_variant_colors_consistent():
    m = variant_colors(["treatment", "control"], control="control")
    assert m == {"control": PALETTE["navy"], "treatment": PALETTE["accent"]}
    assert variant_colors(["control", "B", "C"], "control")["C"] == PALETTE["accent_light"]
    with pytest.raises(ValueError):
        variant_colors(list("abcde"))


def test_catalogue_is_complete():
    expected = {"lift_ci", "metric_by_variant", "cumulative_daily", "daily_lift", "segment_forest", "power_curve",
                "sample_size_vs_mde", "posterior_distributions", "prob_to_beat_control", "srm_bar", "distribution_compare",
                "cuped_variance_reduction", "sequential_boundaries", "guardrail_scorecard", "did_trends"}
    assert set(charts.CATALOGUE) == expected == set(sample_calls())


@pytest.mark.parametrize("name", sorted(sample_calls()))
def test_every_chart_renders_with_palette_colours_only(name):
    import matplotlib.pyplot as plt

    fig = sample_calls()[name]()
    fig.canvas.draw()
    stray = figure_colors(fig) - ALLOWED
    plt.close(fig)
    assert not stray, f"{name} uses colours outside the palette: {stray}"


def test_title_rules_and_save_manifest(tmp_path):
    fig, _ = new_figure()
    with pytest.raises(ValueError):
        finalize(fig, "word " * 60)
    fig = charts.lift_ci([ROW], "Variant B lifts conversion by 3.2%", "Relative lift", "Source: test")
    e = save_chart(fig, tmp_path, "lift_ci", "Variant B lifts conversion by 3.2%", "Lift is positive", takeaways=["a", "b", "c", "d"])
    assert (tmp_path / "charts" / "lift_ci.png").stat().st_size > 10_000 and (tmp_path / "charts" / "lift_ci.svg").is_file()
    assert len(e["takeaways"]) == 3
    fig = charts.lift_ci([ROW], "Updated title")
    save_chart(fig, tmp_path, "lift_ci", "Updated title", "msg")
    man = json.loads((tmp_path / "charts" / "manifest.json").read_text())
    assert [c["title"] for c in man["charts"]] == ["Updated title"]
