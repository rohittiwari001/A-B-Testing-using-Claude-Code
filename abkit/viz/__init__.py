"""Consulting-style charts: ``apply_style()``, the palette and the chart catalogue.

>>> from abkit.viz import apply_style, PALETTE, charts, save_chart
"""

from abkit.viz.style import (FIGSIZE, FONT_FAMILY, PALETTE, SIZES, apply_style, finalize, load_manifest, new_figure,
                             save_chart, status_color, variant_colors)
from abkit.viz import charts

__all__ = ["FIGSIZE", "FONT_FAMILY", "PALETTE", "SIZES", "apply_style", "charts", "finalize", "load_manifest", "new_figure",
           "save_chart", "status_color", "variant_colors"]
