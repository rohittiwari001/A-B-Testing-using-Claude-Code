"""16:9 consulting-style deck built programmatically with python-pptx (no template file).

Every deck follows the same storyline, whatever the problem (see the deck-style skill):

    Title -> Executive summary (the answer first) -> Agenda
    1 The ask          what we were asked, the decision, the hypothesis, what was tested
    2 Approach         data -> quality checks -> analysis -> independent review
    3 Findings         one message per slide: headline result first, then supporting evidence
    4 Impact           what it means for the business, in a few big numbers
    5 Recommendation   risks that could change the conclusion, then the decision and next steps
    Appendix           methodology, validation, full results, supporting charts

Only chapter 3 changes with the problem type: its modules (results, secondary, guardrails, segments,
time, power) come from ``state.plan.deck_sections`` and ``charts/manifest.json``.

Two levels:

- :class:`Deck` - slide primitives with the house layout baked in (action title, chapter tracker,
  footer with source and page number, speaker notes, word-count warnings).
- :func:`build_standard_deck` - assembles the storyline for a run from ``state.json``, ``intake.md``,
  ``results.json`` (every number), ``review.md`` and ``charts/manifest.json``. It also writes
  ``deck_storyline.md`` (the slide titles alone: they must read as a story).

Example
-------
>>> from abkit.deck import build_standard_deck
>>> path = build_standard_deck("runs/2026-10-01_checkout-button")      # doctest: +SKIP
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Sequence

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from abkit import results as R
from abkit.viz.style import PALETTE

FONT = "Arial"
W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.55)
CONTENT_TOP = Inches(1.5)
FOOTER_Y = Inches(7.0)
MAX_BODY_WORDS = 40

CHAPTERS = ["The ask", "Approach", "Findings", "Impact", "Recommendation"]
FINDINGS_MODULES = ["results", "secondary", "guardrails", "segments", "time", "power"]
DEFAULT_SECTIONS = ["results", "guardrails", "segments", "appendix"]
SECTION_TITLES = {"results": "Results", "secondary": "Secondary metrics", "guardrails": "Guardrails", "segments": "Segments",
                  "time": "Effect over time", "power": "Power and sample size", "validation": "Data validation",
                  "appendix": "Appendix"}
METHOD_NAMES = {
    "two_proportion_ztest": "two-proportion z-test", "welch_ttest": "Welch t-test", "bootstrap_mean_diff": "bootstrap",
    "mann_whitney": "Mann-Whitney test", "chi_square_test": "chi-square test", "noninferiority_test": "non-inferiority test",
    "beta_binomial": "Bayesian beta-binomial model", "normal_model": "Bayesian normal model",
    "cuped": "CUPED (pre-period variance reduction)", "regression_adjustment": "regression adjustment",
    "delta_method_ratio": "delta method for ratio metrics", "cluster_robust_test": "cluster-robust regression",
    "segment_effects": "segment breakdown", "interaction_test": "interaction test", "simpsons_check": "Simpson's paradox check",
    "cumulative_effects": "effect over time", "trend_test": "novelty trend test", "diff_in_diff": "difference-in-differences",
    "synthetic_control": "synthetic control", "interrupted_time_series": "interrupted time series",
    "msprt": "always-valid sequential test", "srm_check": "traffic split check", "srm_by": "split check by segment",
    "sample_size_proportions": "sample-size calculation", "sample_size_means": "sample-size calculation",
}


def _rgb(token_or_hex: str) -> RGBColor:
    hexv = PALETTE.get(token_or_hex, token_or_hex)
    return RGBColor.from_string(hexv.lstrip("#").upper())


def _words(text: str) -> int:
    return len(re.findall(r"\S+", text))


class Deck:
    """Slide builder with the consulting layout baked in."""

    def __init__(self, source_note: str = "", chapters: Sequence[str] = CHAPTERS) -> None:
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.blank = self.prs.slide_layouts[6]
        self.source_note = source_note
        self.chapters = list(chapters)
        self.warnings: list[str] = []
        self.kinds: list[str] = []
        self.storyline: list[tuple[str, str]] = []      # (chapter, title) per slide, for the ghost-deck check

    # ------------------------------------------------------------------ primitives

    def _new(self, kind: str, chapter: str = "", title: str = ""):
        slide = self.prs.slides.add_slide(self.blank)
        self.kinds.append(kind)
        self.storyline.append((chapter, title))
        return slide

    def _text(self, slide, x, y, w, h, text: str, size: int = 14, bold: bool = False, color: str = "ink",
              align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, wrap: bool = True):
        box = slide.shapes.add_textbox(x, y, w, h)
        tf = box.text_frame
        tf.word_wrap = wrap
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = Inches(0.02)
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        for i, line in enumerate(str(text).split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            r = p.add_run()
            r.text = line
            f = r.font
            f.name, f.size, f.bold = FONT, Pt(size), bold
            f.color.rgb = _rgb(color)
        return box

    def _rect(self, slide, x, y, w, h, color: str, shape=MSO_SHAPE.RECTANGLE):
        s = slide.shapes.add_shape(shape, x, y, w, h)
        s.fill.solid()
        s.fill.fore_color.rgb = _rgb(color)
        s.line.fill.background()
        s.shadow.inherit = False
        return s

    def _shape_text(self, shape, lines: Sequence[tuple[str, int, bool]], color: str = "white", align=PP_ALIGN.LEFT,
                    anchor=MSO_ANCHOR.MIDDLE, margin: float = 0.18) -> None:
        tf = shape.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = Inches(margin)
        for i, (text, size, bold) in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            r = p.add_run()
            r.text = text
            r.font.name, r.font.size, r.font.bold = FONT, Pt(size), bold
            r.font.color.rgb = _rgb(color)

    def _title(self, slide, text: str) -> None:
        if len(text) > 130:
            self.warnings.append(f"Slide {len(self.kinds)}: title may exceed two lines ({len(text)} chars)")
        self._text(slide, MARGIN, Inches(0.42), W - 2 * MARGIN, Inches(0.95), text, size=24, bold=True, anchor=MSO_ANCHOR.TOP)
        self._rect(slide, MARGIN, Inches(1.33), Inches(0.9), Emu(38100), "accent")

    def _tracker(self, slide, chapter: str) -> None:
        """Chapter tracker at the top: the current chapter in accent, the others grey."""
        if chapter not in self.chapters:
            return
        box = slide.shapes.add_textbox(MARGIN, Inches(0.12), W - 2 * MARGIN, Inches(0.28))
        tf = box.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        for i, ch in enumerate(self.chapters):
            r = p.add_run()
            r.text = f"{i + 1}  {ch.upper()}" + ("" if i == len(self.chapters) - 1 else "      ")
            r.font.name, r.font.size, r.font.bold = FONT, Pt(9), ch == chapter
            r.font.color.rgb = _rgb("accent" if ch == chapter else "grey_mid")

    def _sticker(self, slide, text: str) -> None:
        """Small label at the top right of the content area (e.g. EXPLORATORY, PRELIMINARY)."""
        w = Inches(0.13 * len(text) + 0.5)
        s = self._rect(slide, W - MARGIN - w, Inches(1.2), w, Inches(0.3), "neutral", MSO_SHAPE.ROUNDED_RECTANGLE)
        self._shape_text(s, [(text.upper(), 10, True)], align=PP_ALIGN.CENTER, margin=0.05)

    def _footer(self, slide, source: str | None = None) -> None:
        self._rect(slide, MARGIN, FOOTER_Y - Inches(0.08), W - 2 * MARGIN, Emu(6350), "grey_light")
        self._text(slide, MARGIN, FOOTER_Y, Inches(10.8), Inches(0.35), source or self.source_note, size=9, color="grey_mid")
        self._text(slide, W - MARGIN - Inches(0.8), FOOTER_Y, Inches(0.8), Inches(0.35), str(len(self.prs.slides)), size=9,
                   color="grey_mid", align=PP_ALIGN.RIGHT)

    def _notes(self, slide, notes: str | None) -> None:
        if notes:
            slide.notes_slide.notes_text_frame.text = notes

    def _content_slide(self, kind: str, chapter: str, title: str, source: str | None, notes: str | None, tag: str | None = None):
        s = self._new(kind, chapter, title)
        self._tracker(s, chapter)
        self._title(s, title)
        if tag:
            self._sticker(s, tag)
        self._footer(s, source)
        self._notes(s, notes)
        return s

    def _bullets(self, slide, x, y, w, h, items: Sequence[str], size: int = 16, numbered: bool = False, color: str = "ink",
                 bold_prefix: bool = True, space: int = 10):
        box = slide.shapes.add_textbox(x, y, w, h)
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.02)
        for i, item in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(space)
            marker = f"{i + 1}.  " if numbered else "•  "
            r = p.add_run()
            r.text = marker
            r.font.name, r.font.size, r.font.bold = FONT, Pt(size), True
            r.font.color.rgb = _rgb("accent")
            if bold_prefix and ": " in item and len(item.split(": ", 1)[0]) <= 60:
                head, tail = item.split(": ", 1)
                r1 = p.add_run()
                r1.text = head + ": "
                r1.font.name, r1.font.size, r1.font.bold = FONT, Pt(size), True
                r1.font.color.rgb = _rgb(color)
                item = tail
            r2 = p.add_run()
            r2.text = item
            r2.font.name, r2.font.size = FONT, Pt(size)
            r2.font.color.rgb = _rgb(color)
        return box

    def _label(self, slide, x, y, w, text: str) -> None:
        self._text(slide, x, y, w, Inches(0.3), text.upper(), size=11, bold=True, color="navy")

    def _check_words(self, texts: Iterable[str], limit: int = MAX_BODY_WORDS) -> None:
        n = sum(_words(t) for t in texts)
        if n > limit:
            self.warnings.append(f"Slide {len(self.kinds)}: {n} words of body text (limit ~{limit})")

    # ------------------------------------------------------------------ storyline slides

    def title_slide(self, title: str, subtitle: str = "", date_text: str | None = None) -> None:
        s = self._new("title", "", title)
        self._rect(s, 0, 0, Inches(0.35), H, "navy")
        self._rect(s, Inches(0.9), Inches(3.55), Inches(1.2), Emu(50800), "accent")
        self._text(s, Inches(0.9), Inches(1.6), Inches(11), Inches(1.9), title, size=36, bold=True, anchor=MSO_ANCHOR.BOTTOM)
        self._text(s, Inches(0.9), Inches(3.8), Inches(11), Inches(0.8), subtitle, size=18, color="grey_mid")
        self._text(s, Inches(0.9), Inches(6.6), Inches(6), Inches(0.4), date_text or date.today().strftime("%d %B %Y"), size=12,
                   color="grey_mid")

    def exec_summary(self, headline: str, verdict_label: str, verdict_color: str, reason: str, ask: str,
                     findings: Sequence[str], meaning: str, recommendation: str, notes: str, source: str | None = None,
                     caveat: str = "") -> None:
        """The answer on one page: verdict panel on the left; the ask, findings, meaning and recommendation on the right."""
        s = self._new("exec_summary", "", headline)
        self._text(s, MARGIN, Inches(0.12), Inches(4), Inches(0.28), "EXECUTIVE SUMMARY", size=9, bold=True, color="accent")
        self._title(s, headline)
        top, panel_w = CONTENT_TOP + Inches(0.05), Inches(3.3)
        panel = self._rect(s, MARGIN, top, panel_w, Inches(5.2), verdict_color)
        self._shape_text(panel, [("RECOMMENDATION", 11, True), (verdict_label.upper(), 26, True), ("", 6, False), (reason, 13, False)],
                         anchor=MSO_ANCHOR.TOP, margin=0.25)
        panel.text_frame.margin_top = Inches(0.3)
        x = MARGIN + panel_w + Inches(0.4)
        w = W - MARGIN - x
        y = top
        self._label(s, x, y, w, "The ask")
        self._text(s, x, y + Inches(0.3), w, Inches(0.6), ask, size=14)
        y += Inches(0.95)
        self._label(s, x, y, w, "What we found")
        items = list(findings)[:5]
        self._bullets(s, x, y + Inches(0.3), w, Inches(1.9), items, size=13, space=4)
        y += Inches(0.35) + Inches(0.33) * len(items) + Inches(0.15)
        self._label(s, x, y, w, "What it means")
        self._text(s, x, y + Inches(0.3), w, Inches(0.7), meaning, size=13)
        y += Inches(1.05)
        self._label(s, x, y, w, "What we recommend")
        self._text(s, x, y + Inches(0.3), w, Inches(0.6), recommendation, size=13, bold=True)
        if caveat:
            y += Inches(0.85)
            self._label(s, x, y, w, "Main caveat")
            self._text(s, x, y + Inches(0.3), w, Inches(0.6), caveat, size=13, color="negative")
        self._check_words([ask, *items, meaning, recommendation, caveat], limit=130)
        self._footer(s, source)
        self._notes(s, notes)

    def agenda(self, items: Sequence[str], notes: str = "") -> None:
        s = self._new("agenda", "", "Agenda")
        self._title(s, "Agenda")
        y = CONTENT_TOP + Inches(0.3)
        for i, item in enumerate(items):
            num = self._rect(s, MARGIN, y, Inches(0.55), Inches(0.55), "navy" if i < len(self.chapters) else "grey_mid")
            self._shape_text(num, [(str(i + 1) if i < len(self.chapters) else "A", 16, True)], align=PP_ALIGN.CENTER, margin=0.02)
            self._text(s, MARGIN + Inches(0.8), y + Inches(0.08), Inches(10), Inches(0.45), item, size=18)
            y += Inches(0.8)
        self._footer(s, None)
        self._notes(s, notes or "The storyline: what we were asked, how we answered it, what we found, what it is worth, "
                                "and what we recommend.")

    def context(self, title: str, blocks: Sequence[tuple[str, str]], facts: Sequence[tuple[str, str]], notes: str,
                source: str | None = None) -> None:
        """The ask: decision / hypothesis / success criterion on the left; what was tested on the right."""
        s = self._content_slide("context", CHAPTERS[0], title, source, notes)
        x, w = MARGIN, Inches(5.9)
        y = CONTENT_TOP + Inches(0.15)
        for label, text in blocks:
            self._label(s, x, y, w, label)
            self._text(s, x, y + Inches(0.3), w, Inches(0.9), text, size=14)
            y += Inches(1.3)
        tx = MARGIN + Inches(6.5)
        tw = W - MARGIN - tx
        self._label(s, tx, CONTENT_TOP + Inches(0.15), tw, "What was tested")
        rows = len(facts)
        shape = s.shapes.add_table(rows, 2, tx, CONTENT_TOP + Inches(0.5), tw, Inches(0.42) * rows)
        tbl = shape.table
        tbl.columns[0].width = int(tw * 0.36)
        tbl.columns[1].width = tw - tbl.columns[0].width
        for r, (k, v) in enumerate(facts):
            for c, val in enumerate((k, v)):
                cell = tbl.cell(r, c)
                cell.text = ""
                run = cell.text_frame.paragraphs[0].add_run()
                run.text = str(val)
                run.font.name, run.font.size, run.font.bold = FONT, Pt(12), c == 0
                run.font.color.rgb = _rgb("navy" if c == 0 else "ink")
                cell.fill.solid()
                cell.fill.fore_color.rgb = _rgb("white" if r % 2 else "grey_light")
                cell.margin_left = Inches(0.1)
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        self._check_words([t for _, t in blocks], limit=90)

    def approach(self, title: str, steps: Sequence[tuple[str, str]], notes: str, source: str | None = None) -> None:
        """How we answered it: a left-to-right chevron flow with a short description under each step."""
        s = self._content_slide("approach", CHAPTERS[1], title, source, notes)
        n = len(steps)
        gap = Inches(0.05)
        cw = int((W - 2 * MARGIN - gap * (n - 1)) / n)
        y = CONTENT_TOP + Inches(0.4)
        for i, (head, body) in enumerate(steps):
            x = MARGIN + i * (cw + gap)
            shape = MSO_SHAPE.PENTAGON if i == 0 else MSO_SHAPE.CHEVRON
            c = self._rect(s, x, y, cw, Inches(0.8), "navy" if i < n - 1 else "accent", shape)
            self._shape_text(c, [(f"{i + 1}. {head}", 15, True)], align=PP_ALIGN.CENTER, margin=0.35)
            self._text(s, x + Inches(0.15), y + Inches(1.05), cw - Inches(0.3), Inches(3.2), body, size=13)
        self._check_words([b for _, b in steps], limit=110)

    def impact(self, title: str, tiles: Sequence[tuple[str, str, str]], so_what: str, notes: str, source: str | None = None,
               footnote: str = "") -> None:
        """What it is worth: up to four big-number tiles (value, label, note) and a so-what line."""
        s = self._content_slide("impact", CHAPTERS[3], title, source, notes)
        tiles = list(tiles)[:4]
        n = max(len(tiles), 1)
        gap = Inches(0.3)
        tw = int((W - 2 * MARGIN - gap * (n - 1)) / n)
        y = CONTENT_TOP + Inches(0.35)
        for i, (value, label, note) in enumerate(tiles):
            x = MARGIN + i * (tw + gap)
            self._rect(s, x, y, tw, Emu(50800), "accent" if i == 0 else "navy")
            self._text(s, x, y + Inches(0.2), tw, Inches(0.9), value, size=34 if len(value) <= 14 else 24, bold=True,
                       color="accent" if i == 0 else "navy")
            self._text(s, x, y + Inches(1.15), tw, Inches(0.7), label, size=14, bold=True)
            self._text(s, x, y + Inches(1.85), tw, Inches(0.8), note, size=12, color="grey_mid")
        box = self._rect(s, MARGIN, y + Inches(2.95), W - 2 * MARGIN, Inches(1.0), "grey_light")
        self._shape_text(box, [("SO WHAT", 11, True), (so_what, 15, False)], color="ink", anchor=MSO_ANCHOR.MIDDLE, margin=0.3)
        if footnote:
            self._text(s, MARGIN, y + Inches(4.1), W - 2 * MARGIN, Inches(0.4), footnote, size=10, color="grey_mid")
        self._check_words([t[1] + " " + t[2] for t in tiles] + [so_what], limit=90)

    def recommendation(self, title: str, verdict_label: str, verdict_color: str, reason: str,
                       steps: Sequence[tuple[str, str, str]], notes: str, source: str | None = None) -> None:
        """The decision (coloured banner) and the next steps as an Action / Owner / Timing table."""
        s = self._content_slide("recommendation", CHAPTERS[4], title, source, notes)
        banner = self._rect(s, MARGIN, CONTENT_TOP + Inches(0.1), W - 2 * MARGIN, Inches(0.85), verdict_color)
        self._shape_text(banner, [(f"DECISION: {verdict_label.upper()}", 20, True)], margin=0.3)
        self._text(s, MARGIN, CONTENT_TOP + Inches(1.1), W - 2 * MARGIN, Inches(0.5), reason, size=14, color="ink")
        self._label(s, MARGIN, CONTENT_TOP + Inches(1.7), Inches(4), "Next steps")
        steps = list(steps)[:6]
        if steps:
            width = W - 2 * MARGIN
            shape = s.shapes.add_table(len(steps) + 1, 4, MARGIN, CONTENT_TOP + Inches(2.05), width, Inches(0.42) * (len(steps) + 1))
            tbl = shape.table
            for i, frac in enumerate((0.05, 0.65, 0.17, 0.13)):
                tbl.columns[i].width = int(width * frac)
            for r, row in enumerate([("#", "Action", "Owner", "Timing"), *[(str(i + 1), *st) for i, st in enumerate(steps)]]):
                for c, val in enumerate(row):
                    cell = tbl.cell(r, c)
                    cell.text = ""
                    run = cell.text_frame.paragraphs[0].add_run()
                    run.text = str(val)
                    run.font.name, run.font.size, run.font.bold = FONT, Pt(13 if r else 12), r == 0 or c == 0
                    run.font.color.rgb = _rgb("white" if r == 0 else ("accent" if c == 0 else "ink"))
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = _rgb("navy" if r == 0 else "white")
                    cell.margin_left = Inches(0.1)
                    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        self._check_words([reason] + [st[0] for st in steps], limit=90)

    # ------------------------------------------------------------------ evidence slides

    def section(self, title: str, subtitle: str = "") -> None:
        s = self._new("section", "", title)
        self._rect(s, 0, 0, W, H, "navy")
        self._rect(s, Inches(0.9), Inches(3.9), Inches(1.2), Emu(50800), "accent")
        self._text(s, Inches(0.9), Inches(2.3), Inches(11), Inches(1.5), title, size=34, bold=True, color="white", anchor=MSO_ANCHOR.BOTTOM)
        if subtitle:
            self._text(s, Inches(0.9), Inches(4.1), Inches(11), Inches(0.8), subtitle, size=16, color="accent_light")

    def chart(self, title: str, image: str | Path, takeaways: Sequence[str], notes: str, source: str | None = None,
              crop_top: float = 0.0, chapter: str = CHAPTERS[2], tag: str | None = None) -> None:
        """Chart at ~65% width with up to three numbered takeaways. ``crop_top`` hides the chart's own title band
        (the slide title already states it); ``tag`` adds a sticker such as EXPLORATORY."""
        s = self._content_slide("chart", chapter, title, source, notes, tag)
        cw = Inches(8.3)
        ch = int(cw * 9 / 16 * (1 - crop_top))
        pic = s.shapes.add_picture(str(image), MARGIN, CONTENT_TOP + Inches(0.1), cw, ch)
        pic.crop_top = crop_top
        x = MARGIN + cw + Inches(0.35)
        w = W - MARGIN - x
        self._label(s, x, CONTENT_TOP + Inches(0.15), w, "Key takeaways")
        items = list(takeaways)[:3]
        self._check_words(items)
        self._bullets(s, x, CONTENT_TOP + Inches(0.6), w, Inches(4.5), items, size=14, numbered=True)

    def two_charts(self, title: str, left: str | Path, right: str | Path, left_caption: str, right_caption: str, notes: str,
                   source: str | None = None, chapter: str = CHAPTERS[2]) -> None:
        s = self._content_slide("two_charts", chapter, title, source, notes)
        cw = (W - 2 * MARGIN - Inches(0.3)) / 2
        ch = cw * 9 / 16
        for i, (img, cap) in enumerate(((left, left_caption), (right, right_caption))):
            x = MARGIN + i * (cw + Inches(0.3))
            s.shapes.add_picture(str(img), x, CONTENT_TOP + Inches(0.2), cw, ch)
            self._text(s, x, CONTENT_TOP + Inches(0.35) + ch, cw, Inches(0.8), cap, size=13)
        self._check_words([left_caption, right_caption])

    def table(self, title: str, header: Sequence[str], rows: Sequence[Sequence[Any]], notes: str, source: str | None = None,
              col_widths: Sequence[float] | None = None, font_size: int = 12, status_col: int | None = None,
              chapter: str = "", tag: str | None = None) -> None:
        s = self._content_slide("table", chapter, title, source, notes, tag)
        n_rows = len(rows) + 1
        width = W - 2 * MARGIN
        row_h = Inches(0.42) if n_rows <= 10 else Inches(0.32)
        shape = s.shapes.add_table(n_rows, len(header), MARGIN, CONTENT_TOP + Inches(0.15), width, row_h * n_rows)
        tbl = shape.table
        tbl.first_row = True
        if col_widths:
            tot = sum(col_widths)
            for i, cw in enumerate(col_widths):
                tbl.columns[i].width = int(width * cw / tot)
        status_colors = {"pass": "positive", "breach": "negative", "block": "negative", "warn": "neutral", "inconclusive": "neutral"}
        for r in range(n_rows):
            for c in range(len(header)):
                cell = tbl.cell(r, c)
                val = header[c] if r == 0 else rows[r - 1][c]
                cell.text = ""
                p = cell.text_frame.paragraphs[0]
                run = p.add_run()
                run.text = "" if val is None else str(val)
                run.font.name, run.font.size = FONT, Pt(font_size if r else font_size - 1)
                run.font.bold = r == 0
                cell.fill.solid()
                if r == 0:
                    cell.fill.fore_color.rgb = _rgb("navy")
                    run.font.color.rgb = _rgb("white")
                else:
                    cell.fill.fore_color.rgb = _rgb("white")
                    color = "ink"
                    if status_col is not None and c == status_col:
                        color = status_colors.get(str(val).lower(), "ink")
                        run.font.bold = True
                    run.font.color.rgb = _rgb(color)
                cell.margin_left = cell.margin_right = Inches(0.08)
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE

    def bullets(self, title: str, items: Sequence[str], notes: str, source: str | None = None, numbered: bool = False,
                kind: str = "bullets", label: str | None = None, chapter: str = "") -> None:
        s = self._content_slide(kind, chapter, title, source, notes)
        y = CONTENT_TOP + Inches(0.2)
        if label:
            self._label(s, MARGIN, y, Inches(6), label)
            y += Inches(0.45)
        self._check_words(items, limit=MAX_BODY_WORDS * 2 if kind == "appendix" else MAX_BODY_WORDS + 30)
        self._bullets(s, MARGIN, y, W - 2 * MARGIN, Inches(5), items, size=16, numbered=numbered)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        self.prs.save(path)
        return path


# --------------------------------------------------------------------------- run-level helpers (shared with the report)


def results_table(rows: Sequence[dict[str, Any]], include_segment: bool = False) -> tuple[list[str], list[list[str]]]:
    """Header + formatted rows for a list of result dicts (shared by deck and report)."""
    header = ["Metric", "Comparison", "Control", "Treatment", "Rel. lift", "CI", "p / P(beat)", "Method"]
    if include_segment:
        header.insert(1, "Segment")
    out = []
    for r in rows:
        mtype = "binary" if any(k in (r.get("method") or "") for k in ("proportion", "beta_binomial")) else None
        if r.get("p_value_adjusted") is not None:
            ev = f"{R.fmt_p(r['p_value_adjusted'])} (adj.)"
        elif r.get("p_value") is not None:
            ev = R.fmt_p(r["p_value"])
        elif r.get("probability") is not None:
            ev = R.fmt_prob(r["probability"])
        else:
            ev = "n/a"
        row = [str(r.get("metric") or ""), f"{r.get('treatment', '')} vs {r.get('control', '')}",
               R.fmt_value(r.get("control_value"), mtype), R.fmt_value(r.get("treatment_value"), mtype),
               R.fmt_pct(r.get("rel_lift")), R.fmt_ci(r.get("rel_ci_low"), r.get("rel_ci_high")), ev,
               (r.get("method") or "").split(".")[-1].replace("_", " ")]
        if include_segment:
            row.insert(1, str(r.get("segment") or ""))
        out.append(row)
    return header, out


def intake_sections(run: Path) -> dict[str, str]:
    """intake.md split into {lower-case heading: body}."""
    f = Path(run) / "intake.md"
    if not f.is_file():
        return {}
    out, cur, buf = {}, "_top", []
    for line in f.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#{1,4}\s+(.*)", line)
        if m:
            out[cur] = "\n".join(buf).strip()
            cur, buf = m.group(1).strip().lower(), []
        else:
            buf.append(line)
    out[cur] = "\n".join(buf).strip()
    return out


def run_context(run_dir: str | Path) -> dict[str, Any]:
    """Everything the deck and report builders read, in one place."""
    from abkit import state
    from abkit.viz.style import load_manifest

    run = Path(run_dir)
    st = state.load_state(run)
    res = R.load_results(run)
    man = load_manifest(run)
    title = st.get("title") or run.name.split("_", 1)[-1].replace("-", " ").capitalize()
    val = res.get("validation") or {}
    dates = next((c for c in val.get("checks", []) if c["check"] == "dates"), None)
    period = f"{dates['data']['start']} to {dates['data']['end']}" if dates and dates.get("data") else ""
    csv = st.get("input_csv", "data")
    source = f"Source: {Path(csv).name}" + (f", {period}" if period else "") + f"; run {run.name}"
    return {"run": run, "state": st, "results": res, "manifest": man, "title": title, "source": source, "period": period,
            "intake": intake_sections(run)}


def _charts_for(ctx: dict[str, Any], section: str) -> list[dict[str, Any]]:
    return [c for c in ctx["manifest"]["charts"] if c.get("section") == section and (ctx["run"] / "charts" / c["png"]).is_file()]


def _chart_slides(deck: Deck, ctx: dict[str, Any], section: str, chapter: str = CHAPTERS[2]) -> int:
    n = 0
    for c in _charts_for(ctx, section):
        takeaways = c.get("takeaways") or [c.get("key_message", "")]
        notes = c.get("notes") or f"Key point: {c.get('key_message', '')}. {c.get('subtitle', '')}".strip()
        tag = c.get("tag") or ("Exploratory" if "exploratory" in f"{c.get('title', '')} {c.get('subtitle', '')}".lower() else None)
        deck.chart(c["title"], ctx["run"] / "charts" / c["png"], takeaways, notes, c.get("source") or ctx["source"],
                   crop_top=c.get("title_crop", 0.0), chapter=chapter, tag=tag)
        n += 1
    return n


def _setup_rows(ctx: dict[str, Any]) -> list[list[str]]:
    st, res = ctx["state"], ctx["results"]
    rows = []
    checks = {c["check"]: c for c in (res.get("validation") or {}).get("checks", [])}
    if "variants" in checks:
        counts = checks["variants"]["data"] or {}
        rows.append(["Variants (units)", ", ".join(f"{k}: {R.fmt_num(v)}" for k, v in counts.items())])
    if ctx["period"]:
        rows.append(["Test period", f"{ctx['period']} ({checks['dates']['data']['days']} days)"])
    for m in st.get("metrics", []):
        rows.append([f"{m['role'].capitalize()} metric", f"{m['name']} ({m['type']}, goal: {m['direction'].replace('_', ' ')})"])
    s = st["settings"]
    rows.append(["Statistical settings", f"alpha {s['alpha']}, {s['sidedness']}, power {s['power']}"])
    rows.append(["Multiple-testing correction", f"secondary: {s['correction_secondary']}; segments: {s['correction_segments']}"])
    if st.get("problem_type"):
        rows.append(["Analysis type", ", ".join(p.replace("_", " ") for p in st["problem_type"])])
    return rows


def _methods_used(res: dict[str, Any]) -> list[str]:
    out = []
    for sid, step in res.get("steps", {}).items():
        methods = list(dict.fromkeys([step.get("method") or ""] + [r.get("method") or "" for r in step.get("results", [])]))
        names = ", ".join(m.split(".")[-1].replace("_", " ") for m in methods if m)
        if names:
            out.append(f"{sid.replace('_', ' ')}: {names} ({step.get('script', '')})")
    return out


def _validation_rows(res: dict[str, Any]) -> list[list[str]]:
    return [[c["check"], c["verdict"].upper(), str(c["detail"])[:110]] for c in (res.get("validation") or {}).get("checks", [])]


# --------------------------------------------------------------------------- storyline content


def _first_sentence(text: str) -> str:
    text = " ".join(str(text).split())
    m = re.match(r"(.+?[.?!])(\s|$)", text)
    return m.group(1) if m else text


def _intake(ctx: dict[str, Any], *keys: str) -> str:
    for k in keys:
        for h, body in ctx["intake"].items():
            if h.startswith(k) and body:
                return " ".join(re.sub(r"^\s*([-*]|\d+\.)\s+", "", ln).strip() for ln in body.splitlines() if ln.strip())
    return ""


def _primary(ctx: dict[str, Any]) -> dict[str, Any] | None:
    summ = ctx["results"].get("summary") or {}
    ref = summ.get("primary") or {}
    try:
        return R.get_step(ctx["results"], ref["step"])["results"][ref.get("index", 0)] if ref.get("step") else None
    except KeyError:
        return None


def _unit_word(ctx: dict[str, Any]) -> str:
    unit = str((ctx["state"].get("design") or {}).get("unit_col", "")).lower()
    for key, word in (("user", "users"), ("session", "sessions"), ("account", "accounts"), ("region", "regions"),
                      ("store", "stores"), ("device", "devices")):
        if key in unit:
            return word
    return "users" if ctx["state"].get("input_csv") else "units"


def _metric_meta(ctx: dict[str, Any], role: str = "primary") -> dict[str, Any]:
    return next((m for m in ctx["state"].get("metrics", []) if m.get("role") == role), {})


def _ask_content(ctx: dict[str, Any]) -> tuple[str, list[tuple[str, str]], list[tuple[str, str]]]:
    st, res, summ = ctx["state"], ctx["results"], ctx["results"].get("summary") or {}
    question = _intake(ctx, "business question") or ctx["title"]
    m = _metric_meta(ctx)
    metric = m.get("label") or m.get("name") or "the primary metric"
    thr = summ.get("mde_rel") if summ.get("mde_rel") is not None else m.get("practical_threshold_rel")
    direction = {"increase": "rise", "decrease": "fall", "no_decrease": "hold", "no_increase": "hold"}.get(m.get("direction"), "move")
    success = f"{metric.capitalize()} must {direction}" + (f" by at least {R.fmt_pct(thr, 0, signed=False)} (relative)" if thr else "")
    success += " without breaching a guardrail." if any(x.get("role") == "guardrail" for x in st.get("metrics", [])) else "."
    blocks = [("The decision", _first_sentence(_intake(ctx, "decision") or "Decide whether to roll out the change.")),
              ("Our hypothesis", _first_sentence(_intake(ctx, "hypothesis") or "The change improves the primary metric.")),
              ("What success looks like", success)]
    checks = {c["check"]: c for c in (res.get("validation") or {}).get("checks", [])}
    facts = []
    counts = (checks.get("variants") or {}).get("data") or {}
    if counts:
        facts.append(("Groups", ", ".join(f"{k}: {R.fmt_num(v)}" for k, v in counts.items())))
    split = (st.get("design") or {}).get("expected_split")
    if split:
        facts.append(("Intended split", " / ".join(f"{k} {R.fmt_prob(v)}" for k, v in split.items())))
    facts.append(("Unit", _unit_word(ctx)))
    facts.append(("Period", f"{ctx['period']}" if ctx["period"] else "dates not recorded"))
    facts.append(("Primary metric", metric))
    guards = [x.get("label") or x["name"] for x in st.get("metrics", []) if x.get("role") == "guardrail"]
    facts.append(("Guardrails", ", ".join(guards) if guards else "none defined"))
    if thr:
        facts.append(("Practical threshold", f"{R.fmt_pct(thr, 0)} relative"))
    title = question if question.rstrip().endswith("?") else f"The ask: {question}"
    if not title.lower().startswith("the ask"):
        title = f"The ask: {title}"
    return title, blocks, facts


def _approach_content(ctx: dict[str, Any]) -> tuple[str, list[tuple[str, str]]]:
    st, res, summ = ctx["state"], ctx["results"], ctx["results"].get("summary") or {}
    checks = {c["check"]: c for c in (res.get("validation") or {}).get("checks", [])}
    counts = (checks.get("variants") or {}).get("data") or {}
    n = sum(counts.values()) if counts else None
    units = _unit_word(ctx)
    quasi = "quasi_experiment" in st.get("problem_type", [])
    design = "non-randomised comparison" if quasi else "randomised comparison"
    data = (f"{R.fmt_num(n)} {units} in {len(counts)} groups ({', '.join(counts)})." if n else "Data as described at intake.")
    data += f" Period: {ctx['period']}." if ctx["period"] else " Test dates not recorded."
    verdict = (res.get("validation") or {}).get("verdict", "n/a").upper()
    srm = checks.get("SRM")
    srm_txt = ""
    if srm and (srm.get("data") or {}).get("p_value") is not None:
        p = srm["data"]["p_value"]
        srm_txt = (f" Traffic split as intended ({R.fmt_p_stat(p)})." if srm["verdict"] == "pass"
                   else f" Traffic split does NOT match the design ({R.fmt_p_stat(p)}).")
    quality = f"{len(checks)} data checks: overall {verdict}.{srm_txt}"
    methods = []
    for step in res.get("steps", {}).values():
        for meth in [step.get("method") or ""] + [r.get("method") or "" for r in step.get("results", [])]:
            name = METHOD_NAMES.get(meth.split(".")[-1])
            if name and name not in methods and "split" not in name:
                methods.append(name)
    thr = summ.get("mde_rel")
    analysis = (f"{methods[0].capitalize()}" + (f", plus {', '.join(methods[1:4])}" if len(methods) > 1 else "") + "."
                if methods else "No effect estimated.")
    if thr:
        analysis += f" Judged against a {R.fmt_pct(thr, 0, signed=False)} practical threshold."
    review_file = ctx["run"] / "review.md"
    rounds = len(re.findall(r"^# Review", review_file.read_text(encoding="utf-8"), re.M)) if review_file.is_file() else 0
    passed = st.get("gates", {}).get("review_passed")
    review = (f"Independent reviewer re-checked the numbers from the raw data: {rounds} round{'s' if rounds != 1 else ''}, "
              + ("passed." if passed else "still open."))
    title = (f"We answered it with a {design} of {R.fmt_num(n)} {units}, quality checks and an independent review"
             if n else f"We answered it with a {design}, quality checks and an independent review")
    return title, [("Data", data), ("Quality checks", quality), ("Analysis", analysis), ("Review", review)]


def _impact_content(ctx: dict[str, Any]) -> tuple[str, list[tuple[str, str, str]], str, str]:
    summ = ctx["results"].get("summary") or {}
    tiles = [(t["value"], t["label"], t.get("note", "")) for t in summ.get("impact", [])]
    p = _primary(ctx)
    if not tiles and p and summ.get("verdict") != "blocked":
        binary = any(k in (p.get("method") or "") for k in ("proportion", "beta_binomial"))
        level = round((1 - (p.get("alpha") or 0.05)) * 100)
        tiles.append((R.fmt_pct(p.get("rel_lift")), "Relative change in the primary metric",
                      f"{level}% CI {R.fmt_ci(p.get('rel_ci_low'), p.get('rel_ci_high'))}"))
        if binary:
            per_k = (p.get("estimate") or 0) * 1000
            tiles.append((f"{per_k:+,.1f}".replace("-", "−"), "Change per 1,000 users",
                          f"{R.fmt_value(p.get('control_value'), 'binary')} → {R.fmt_value(p.get('treatment_value'), 'binary')}"))
        else:
            tiles.append((R.fmt_num(p.get("estimate")), "Absolute change per unit",
                          f"{R.fmt_num(p.get('control_value'))} → {R.fmt_num(p.get('treatment_value'))}"))
        tiles.append((R.fmt_num(sum((p.get("n") or {}).values())), "Units analysed", " / ".join(f"{k}: {R.fmt_num(v)}" for k, v in (p.get("n") or {}).items())))
    if not tiles:
        tiles = [(k["value"], k["label"], "") for k in summ.get("key_numbers", [])[:3]]
    title = summ.get("impact_headline") or (_first_sentence(summ.get("plain_english", "")) or "What this means for the business")
    if summ.get("verdict") == "blocked":
        title = summ.get("impact_headline") or "What we can and cannot conclude from this data"
    so_what = summ.get("so_what") or summ.get("reason", "")
    caveats = summ.get("caveats", [])
    foot = f"Read with the {len(caveats)} caveats on the next slide." if caveats else ""
    return title, tiles, so_what, foot


def _parse_step(step: Any) -> tuple[str, str, str]:
    """A next step as (action, owner, timing). Accepts dicts or strings like 'Owner: action (timing)'."""
    if isinstance(step, dict):
        a = str(step.get("action", ""))
        return (a[:1].upper() + a[1:], step.get("owner") or "To agree", step.get("timing") or "To agree")
    text, owner, timing = str(step).strip(), "To agree", "To agree"
    m = re.match(r"^([A-Z][\w /&.-]{1,30}):\s+(.+)$", text)
    if m:
        owner, text = m.group(1), m.group(2)
    t = re.search(r"\(((?:within|by|next|in|before|after|this|now|ongoing|immediately|Q\d|[0-9])[^()]{0,30})\)\s*\.?$", text, re.I)
    if t:
        timing, text = t.group(1), text[: t.start()].rstrip()
    text = text.rstrip(".")
    return (text[:1].upper() + text[1:]), owner, timing


def build_standard_deck(run_dir: str | Path, out: str | Path | None = None, sections: Sequence[str] | None = None) -> Path:
    """Assemble ``deck.pptx`` for a run following the fixed consulting storyline.

    ``sections`` (default ``state.plan.deck_sections``) only selects the findings modules (results,
    secondary, guardrails, segments, time, power), whether validation evidence belongs in the main story,
    and whether there is an appendix. Older section names (exec_summary, setup, risks, next_steps) are
    accepted and ignored: those slides are always part of the storyline.
    """
    ctx = run_context(run_dir)
    st, res = ctx["state"], ctx["results"]
    summ = res.get("summary") or {}
    if not summ:
        raise ValueError("results.json has no summary; run abkit.decision.build_summary first")
    secs = list(sections or st["plan"].get("deck_sections") or DEFAULT_SECTIONS)
    blocked = summ.get("verdict") == "blocked"
    val_verdict = (res.get("validation") or {}).get("verdict")
    modules = [s for s in secs if s in FINDINGS_MODULES] or [s for s in FINDINGS_MODULES if _charts_for(ctx, s)]
    validation_in_story = blocked or val_verdict == "block"
    deck = Deck(ctx["source"])

    # Title and the answer first
    deck.title_slide(ctx["title"], summ.get("headline", "Experiment readout"), None)
    ask_title, ask_blocks, ask_facts = _ask_content(ctx)
    steps = [_parse_step(s) for s in summ.get("next_steps", [])] or [(summ.get("reason", "Decide on rollout."), "To agree", "To agree")]
    findings = [f"{k['label']}: {k['value']}" for k in summ.get("key_numbers", [])][:5]
    deck.exec_summary(
        summ["headline"], summ["verdict_label"], summ.get("verdict_color", "neutral"), summ.get("reason", ""),
        ask=_intake(ctx, "business question") or ctx["title"], findings=findings,
        meaning=summ.get("plain_english") or summ.get("reason", ""), recommendation=steps[0][0],
        caveat=(summ.get("caveats") or [""])[0],
        notes=(f"The answer first. Verdict: {summ.get('verdict_label')}. {summ.get('reason', '')} "
               f"{summ.get('plain_english', '')} Caveats: " + " ".join(summ.get("caveats", []))).strip())
    agenda = ["The ask: what we were asked to answer", "Approach: how we answered it", "Findings: what the data shows",
              "Impact: what it means for the business", "Recommendation: risks, decision and next steps"]
    deck.agenda(agenda + (["Appendix: methodology, validation and full results"] if "appendix" in secs else []))

    # 1 The ask
    deck.context(ask_title, ask_blocks, ask_facts,
                 "Restate the question and the decision before any result, so the audience judges the answer against the ask.")

    # 2 Approach
    ap_title, ap_steps = _approach_content(ctx)
    deck.approach(ap_title, ap_steps, "How the answer was produced and why it can be trusted: data, checks, method, independent review.")
    _chart_slides(deck, ctx, "setup", CHAPTERS[1])

    # 3 Findings (the only problem-specific chapter)
    if validation_in_story:
        _chart_slides(deck, ctx, "validation", CHAPTERS[2])
        if res.get("validation"):
            deck.table(f"Data validation: overall verdict {val_verdict.upper()}", ["Check", "Verdict", "Detail"], _validation_rows(res),
                       "Anything flagged here limits how far the data can be trusted.", col_widths=[1.2, 0.8, 5], font_size=10,
                       status_col=1, chapter=CHAPTERS[2])
    for mod in modules:
        n = _chart_slides(deck, ctx, mod, CHAPTERS[2])
        if mod == "guardrails":
            g = R.all_results(res, role="guardrail")
            if g:
                header, rows = results_table(g)
                header, rows = header + ["Status"], [r + [str((x.get("extra") or {}).get("status", "n/a")).upper()] for r, x in zip(rows, g)]
                deck.table("Guardrail checks: each tested for non-inferiority against its margin", header, rows,
                           "Guardrails protect against wins on the primary metric that cost something elsewhere.",
                           font_size=11, status_col=len(header) - 1, chapter=CHAPTERS[2])
        elif mod == "results" and not n and not blocked:
            header, rows = results_table(R.all_results(res, role="primary") or R.all_results(res))
            deck.table(summ.get("headline", "Results"), header, rows, "Primary results.", font_size=11, chapter=CHAPTERS[2])

    # 4 Impact
    im_title, tiles, so_what, foot = _impact_content(ctx)
    deck.impact(im_title, tiles, so_what, "Translate the statistics into business terms: what the change is worth.", footnote=foot)

    # 5 Recommendation: risks, then the decision
    risks = list(summ.get("caveats", []))
    for r in R.all_results(res):
        for a in r.get("assumptions", []):
            if a.get("passed") is False:
                risks.append(f"Assumption not met ({r.get('metric')}): {a['check']}")
    risks = risks[:6] or ["No material risks identified by the analysis or the review."]
    deck.bullets(f"{len(risks)} caveat{'s' if len(risks) != 1 else ''} could change or qualify this conclusion"
                 if summ.get("caveats") else "No material risks identified", risks, "Be explicit about what could make the conclusion wrong.",
                 kind="risks", chapter=CHAPTERS[4])
    n_steps = f"{len(steps[:6])} next step{'s' if len(steps[:6]) != 1 else ''}"
    rec_title = (f"Recommendation: fix the data before any decision, with {n_steps}" if blocked
                 else f"Recommendation: {summ.get('verdict_label', 'n/a')}, with {n_steps} to act on")
    deck.recommendation(rec_title, summ.get("verdict_label", "n/a"),
                        summ.get("verdict_color", "neutral"), summ.get("reason", ""), steps,
                        "Close with the decision, then who does what by when.")

    # Appendix
    if "appendix" in secs:
        deck.section("Appendix", "Methodology, validation and full results")
        s = st["settings"]
        methods = _methods_used(res) + [f"Settings: alpha {s['alpha']} ({s['sidedness']}), power {s['power']}, "
                                        f"SRM threshold {s['srm_threshold']}"]
        deck.bullets("Methodology: tests used and the scripts that produced each number", methods[:8],
                     "Tests used per analysis step and the scripts that produced each number.", kind="appendix")
        if not validation_in_story:
            _chart_slides(deck, ctx, "validation", "")
            if res.get("validation"):
                deck.table(f"Data validation: overall verdict {(val_verdict or 'n/a').upper()}", ["Check", "Verdict", "Detail"],
                           _validation_rows(res), "Full list of validation checks.", col_widths=[1.2, 0.8, 5], font_size=10,
                           status_col=1)
        comp = [r for r in R.all_results(res) if r.get("rel_lift") is not None]
        if comp:
            header, rows = results_table(comp, include_segment=any(r.get("segment") for r in comp))
            for i in range(0, len(rows), 12):
                deck.table("Full results" + (" (cont.)" if i else ""), header, rows[i:i + 12], "Complete table of estimates.",
                           font_size=9)
        _chart_slides(deck, ctx, "appendix", "")

    path = Path(out) if out else ctx["run"] / "deck.pptx"
    deck.save(path)
    story = ["# Deck storyline (ghost deck)", "", "Read the titles alone: they must tell the whole story.", "",
             "| # | Chapter | Slide title |", "|---|---|---|"]
    story += [f"| {i + 1} | {ch or '-'} | {t} |" for i, (ch, t) in enumerate(deck.storyline)]
    (path.parent / "deck_storyline.md").write_text("\n".join(story) + "\n", encoding="utf-8")
    warn = path.parent / "deck_warnings.txt"
    if deck.warnings:
        warn.write_text("\n".join(deck.warnings) + "\n", encoding="utf-8")
    elif warn.is_file():
        warn.unlink()
    return path
