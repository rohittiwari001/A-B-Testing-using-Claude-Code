"""The visual system: palette, fonts, sizes, figure layout, saving and the chart manifest.

Every plotting script calls :func:`apply_style` first (the style_guard hook checks this),
takes colours only from :data:`PALETTE`, and saves with :func:`save_chart`, which writes
PNG (300 dpi) + SVG into ``<run>/charts/`` and records the chart in ``charts/manifest.json``.

Example
-------
>>> from abkit.viz import apply_style, PALETTE
>>> apply_style()
>>> PALETTE["accent"]
'#2251FF'
"""

from __future__ import annotations

import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PALETTE: dict[str, str] = {
    "ink": "#1A1A1A",
    "navy": "#0B2545",
    "accent": "#2251FF",
    "accent_light": "#9DB4FF",
    "grey_mid": "#8C8C8C",
    "grey_light": "#E3E3E3",
    "positive": "#1B7F5A",
    "negative": "#C0392B",
    "neutral": "#B08900",
    "white": "#FFFFFF",
}
FONT_FAMILY = ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"]
SIZES = {"title": 14, "subtitle": 11, "axis": 10, "annotation": 10, "source": 8}
FIGSIZE = (10, 5.625)          # 16:9, drops straight into a deck chart slot
STYLE_FILE = Path(__file__).with_name("consulting.mplstyle")
TITLE_WRAP = 88                 # characters per title line at 14 pt on a 10 in figure


def apply_style() -> None:
    """Apply the consulting style to matplotlib (idempotent)."""
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    plt.style.use(str(STYLE_FILE))
    matplotlib.rcParams["font.sans-serif"] = FONT_FAMILY
    matplotlib.rcParams["svg.fonttype"] = "none"


def variant_colors(variants: Iterable[str], control: str | None = None) -> dict[str, str]:
    """Consistent variant -> colour mapping: control navy, first treatment accent, then accent_light, grey_mid."""
    vs = [str(v) for v in variants]
    if control is not None and str(control) in vs:
        vs.remove(str(control))
        vs.insert(0, str(control))
    order = [PALETTE["navy"], PALETTE["accent"], PALETTE["accent_light"], PALETTE["grey_mid"]]
    if control is None:
        order = order[1:] + [PALETTE["navy"]]
    if len(vs) > 4:
        raise ValueError("At most four series per chart; facet or group the rest into 'Other'.")
    return {v: order[i] for i, v in enumerate(vs)}


def status_color(result: dict[str, Any] | None = None, significant: bool | None = None, value: float | None = None,
                 direction: str = "increase") -> str:
    """positive / negative / neutral colour for a result (significance x direction)."""
    if result is not None:
        significant = result.get("significant")
        value = result.get("rel_lift", result.get("estimate"))
        if result.get("p_value") is None and result.get("probability") is not None:
            significant = result["probability"] >= 0.95 or result["probability"] <= 0.05
    if not significant or value is None or value == 0:
        return PALETTE["neutral"]
    good = (value > 0) == (direction in ("increase", "no_decrease"))
    return PALETTE["positive"] if good else PALETTE["negative"]


def new_figure(left: float = 0.08, right: float = 0.95, bottom: float = 0.14, figsize=FIGSIZE):
    """Figure + axes with room reserved for the action title, subtitle and source line."""
    import matplotlib.pyplot as plt

    apply_style()
    fig, ax = plt.subplots(figsize=figsize)
    fig.subplots_adjust(left=left, right=right, bottom=bottom, top=0.78)
    return fig, ax


def finalize(fig, title: str, subtitle: str | None = None, source: str | None = None) -> None:
    """Add the action title (max two lines), subtitle and source/notes line in fixed positions."""
    lines = textwrap.wrap(title, TITLE_WRAP)
    if len(lines) > 2:
        raise ValueError(f"Action title longer than two lines ({len(title)} chars): shorten it")
    x = 0.04
    fig.text(x, 0.955, "\n".join(lines), fontsize=SIZES["title"], fontweight="bold", color=PALETTE["ink"], va="top", ha="left",
             linespacing=1.15)
    y_sub = 0.955 - 0.058 * len(lines) - 0.012
    fig._abkit_title_crop = round(1 - y_sub - 0.004, 4)     # share of height above the subtitle (deck slides crop it)
    if subtitle:
        fig.text(x, y_sub, subtitle, fontsize=SIZES["subtitle"], color=PALETTE["grey_mid"], va="top", ha="left")
    top = y_sub - (0.075 if subtitle else 0.02)
    fig.subplots_adjust(top=min(top, fig.subplotpars.top))
    if source:
        fig.text(x, 0.025, textwrap.shorten(source, 190, placeholder="..."), fontsize=SIZES["source"], color=PALETTE["grey_mid"],
                 va="bottom", ha="left")


def save_chart(
    fig, run_dir: str | Path, chart_id: str, title: str, key_message: str, subtitle: str = "", source: str = "",
    section: str = "results", takeaways: list[str] | None = None, notes: str = "", out_dir: str | Path | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """Save PNG (300 dpi) + SVG and upsert the chart in ``charts/manifest.json``. Returns the manifest entry.

    ``section`` places the chart in the deck/report: setup, validation, results, secondary,
    guardrails, segments, time, power, appendix. ``takeaways`` are up to three short bullets
    for the chart slide (build them with f-strings from results.json values). ``tag`` puts a sticker on the
    slide (e.g. "Exploratory", "Preliminary"). Charts appear in the deck in the order they are saved, so save
    the headline chart of each section first.
    """
    import matplotlib.pyplot as plt

    charts = Path(out_dir) if out_dir else Path(run_dir) / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    png, svg = charts / f"{chart_id}.png", charts / f"{chart_id}.svg"
    fig.savefig(png, dpi=300)
    fig.savefig(svg)
    plt.close(fig)
    entry = {"id": chart_id, "title": title, "subtitle": subtitle, "key_message": key_message, "takeaways": (takeaways or [])[:3],
             "section": section, "source": source, "notes": notes, "png": png.name, "svg": svg.name,
             "title_crop": getattr(fig, "_abkit_title_crop", 0.0), "tag": tag,
             "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    manifest = load_manifest(charts.parent if not out_dir else charts, charts_dir=charts)
    manifest["charts"] = [c for c in manifest["charts"] if c["id"] != chart_id] + [entry]
    (charts / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return entry


def load_manifest(run_dir: str | Path, charts_dir: str | Path | None = None) -> dict[str, Any]:
    path = Path(charts_dir or Path(run_dir) / "charts") / "manifest.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"charts": []}
