"""16:9 consulting-style deck built programmatically with python-pptx (no template file).

Two levels:

- :class:`Deck` - slide primitives (title, executive summary, section divider, chart + takeaways,
  two charts, table, bullet slides for methodology / risks / next steps). Every content slide gets
  an action title, a footer (source note + slide number) and speaker notes.
- :func:`build_standard_deck` - assembles a full deck for a run from ``state.json`` (plan
  deck_sections), ``results.json`` (every number) and ``charts/manifest.json`` (charts + takeaways).

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
CONTENT_TOP = Inches(1.45)
FOOTER_Y = Inches(7.0)
MAX_BODY_WORDS = 40

DEFAULT_SECTIONS = ["exec_summary", "setup", "results", "guardrails", "segments", "risks", "next_steps", "appendix"]
SECTION_TITLES = {"results": "Results", "secondary": "Secondary metrics", "guardrails": "Guardrails", "segments": "Segments",
                  "time": "Effect over time", "power": "Power and sample size", "validation": "Data validation",
                  "appendix": "Appendix"}


def _rgb(token_or_hex: str) -> RGBColor:
    hexv = PALETTE.get(token_or_hex, token_or_hex)
    return RGBColor.from_string(hexv.lstrip("#").upper())


def _words(text: str) -> int:
    return len(re.findall(r"\S+", text))


class Deck:
    """Slide builder with the consulting layout baked in."""

    def __init__(self, source_note: str = "") -> None:
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.blank = self.prs.slide_layouts[6]
        self.source_note = source_note
        self.warnings: list[str] = []
        self.kinds: list[str] = []

    # ------------------------------------------------------------------ primitives

    def _new(self, kind: str):
        slide = self.prs.slides.add_slide(self.blank)
        self.kinds.append(kind)
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

    def _title(self, slide, text: str) -> None:
        if len(text) > 130:
            self.warnings.append(f"Slide {len(self.kinds)}: title may exceed two lines ({len(text)} chars)")
        self._text(slide, MARGIN, Inches(0.35), W - 2 * MARGIN, Inches(0.95), text, size=24, bold=True, anchor=MSO_ANCHOR.TOP)
        self._rect(slide, MARGIN, Inches(1.28), Inches(0.9), Emu(38100), "accent")

    def _footer(self, slide, source: str | None = None) -> None:
        self._rect(slide, MARGIN, FOOTER_Y - Inches(0.08), W - 2 * MARGIN, Emu(6350), "grey_light")
        self._text(slide, MARGIN, FOOTER_Y, Inches(10.8), Inches(0.35), source or self.source_note, size=9, color="grey_mid")
        self._text(slide, W - MARGIN - Inches(0.8), FOOTER_Y, Inches(0.8), Inches(0.35), str(len(self.prs.slides)), size=9,
                   color="grey_mid", align=PP_ALIGN.RIGHT)

    def _notes(self, slide, notes: str | None) -> None:
        if notes:
            slide.notes_slide.notes_text_frame.text = notes

    def _bullets(self, slide, x, y, w, h, items: Sequence[str], size: int = 16, numbered: bool = False, color: str = "ink",
                 bold_prefix: bool = True):
        box = slide.shapes.add_textbox(x, y, w, h)
        tf = box.text_frame
        tf.word_wrap = True
        for i, item in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(10)
            marker = f"{i + 1}.  " if numbered else "•  "
            r = p.add_run()
            r.text = marker
            r.font.name, r.font.size, r.font.bold = FONT, Pt(size), True
            r.font.color.rgb = _rgb("accent")
            if bold_prefix and ": " in item:
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

    def _check_words(self, texts: Iterable[str], limit: int = MAX_BODY_WORDS) -> None:
        n = sum(_words(t) for t in texts)
        if n > limit:
            self.warnings.append(f"Slide {len(self.kinds)}: {n} words of body text (limit ~{limit})")

    # ------------------------------------------------------------------ slide types

    def title_slide(self, title: str, subtitle: str = "", date_text: str | None = None) -> None:
        s = self._new("title")
        self._rect(s, 0, 0, Inches(0.35), H, "navy")
        self._rect(s, Inches(0.9), Inches(3.55), Inches(1.2), Emu(50800), "accent")
        self._text(s, Inches(0.9), Inches(1.6), Inches(11), Inches(1.9), title, size=36, bold=True, anchor=MSO_ANCHOR.BOTTOM)
        self._text(s, Inches(0.9), Inches(3.8), Inches(11), Inches(0.8), subtitle, size=18, color="grey_mid")
        self._text(s, Inches(0.9), Inches(6.6), Inches(6), Inches(0.4), date_text or date.today().strftime("%d %B %Y"), size=12,
                   color="grey_mid")

    def exec_summary(self, verdict_label: str, verdict_color: str, headline: str, bullets: Sequence[str], notes: str,
                     source: str | None = None, reason: str = "") -> None:
        s = self._new("exec_summary")
        self._title(s, headline)
        box = self._rect(s, MARGIN, CONTENT_TOP + Inches(0.1), W - 2 * MARGIN, Inches(1.0), verdict_color)
        tf = box.text_frame
        tf.margin_left = Inches(0.3)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        r = p.add_run()
        r.text = f"Recommendation: {verdict_label.upper()}"
        r.font.name, r.font.size, r.font.bold = FONT, Pt(22), True
        r.font.color.rgb = _rgb("white")
        if reason:
            r2 = p.add_run()
            r2.text = f"   {reason}"
            r2.font.name, r2.font.size = FONT, Pt(13)
            r2.font.color.rgb = _rgb("white")
        items = list(bullets)[:5]
        self._check_words(items, limit=60)
        self._bullets(s, MARGIN, CONTENT_TOP + Inches(1.45), W - 2 * MARGIN, Inches(4.0), items, size=17)
        self._footer(s, source)
        self._notes(s, notes)

    def section(self, title: str, subtitle: str = "") -> None:
        s = self._new("section")
        self._rect(s, 0, 0, W, H, "navy")
        self._rect(s, Inches(0.9), Inches(3.9), Inches(1.2), Emu(50800), "accent")
        self._text(s, Inches(0.9), Inches(2.3), Inches(11), Inches(1.5), title, size=34, bold=True, color="white", anchor=MSO_ANCHOR.BOTTOM)
        if subtitle:
            self._text(s, Inches(0.9), Inches(4.1), Inches(11), Inches(0.8), subtitle, size=16, color="accent_light")

    def chart(self, title: str, image: str | Path, takeaways: Sequence[str], notes: str, source: str | None = None,
              crop_top: float = 0.0) -> None:
        """Chart at ~65% width with up to three takeaways. ``crop_top`` hides the chart's own title band
        (the slide title already states it)."""
        s = self._new("chart")
        self._title(s, title)
        cw = Inches(8.3)                      # ~65% of the usable width
        ch = int(cw * 9 / 16 * (1 - crop_top))
        pic = s.shapes.add_picture(str(image), MARGIN, CONTENT_TOP + Inches(0.1), cw, ch)
        pic.crop_top = crop_top
        x = MARGIN + cw + Inches(0.35)
        w = W - MARGIN - x
        self._text(s, x, CONTENT_TOP + Inches(0.15), w, Inches(0.4), "KEY TAKEAWAYS", size=11, bold=True, color="grey_mid")
        items = list(takeaways)[:3]
        self._check_words(items)
        self._bullets(s, x, CONTENT_TOP + Inches(0.6), w, Inches(4.5), items, size=14, numbered=True)
        self._footer(s, source)
        self._notes(s, notes)

    def two_charts(self, title: str, left: str | Path, right: str | Path, left_caption: str, right_caption: str, notes: str,
                   source: str | None = None) -> None:
        s = self._new("two_charts")
        self._title(s, title)
        cw = (W - 2 * MARGIN - Inches(0.3)) / 2
        ch = cw * 9 / 16
        for i, (img, cap) in enumerate(((left, left_caption), (right, right_caption))):
            x = MARGIN + i * (cw + Inches(0.3))
            s.shapes.add_picture(str(img), x, CONTENT_TOP + Inches(0.2), cw, ch)
            self._text(s, x, CONTENT_TOP + Inches(0.35) + ch, cw, Inches(0.8), cap, size=13)
        self._check_words([left_caption, right_caption])
        self._footer(s, source)
        self._notes(s, notes)

    def table(self, title: str, header: Sequence[str], rows: Sequence[Sequence[Any]], notes: str, source: str | None = None,
              col_widths: Sequence[float] | None = None, font_size: int = 12, status_col: int | None = None) -> None:
        s = self._new("table")
        self._title(s, title)
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
        self._footer(s, source)
        self._notes(s, notes)

    def bullets(self, title: str, items: Sequence[str], notes: str, source: str | None = None, numbered: bool = False,
                kind: str = "bullets", label: str | None = None) -> None:
        s = self._new(kind)
        self._title(s, title)
        y = CONTENT_TOP + Inches(0.2)
        if label:
            self._text(s, MARGIN, y, Inches(6), Inches(0.4), label.upper(), size=11, bold=True, color="grey_mid")
            y += Inches(0.45)
        self._check_words(items, limit=MAX_BODY_WORDS * 2 if kind == "appendix" else MAX_BODY_WORDS + 20)
        self._bullets(s, MARGIN, y, W - 2 * MARGIN, Inches(5), items, size=16, numbered=numbered)
        self._footer(s, source)
        self._notes(s, notes)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        self.prs.save(path)
        return path


# --------------------------------------------------------------------------- run-level assembly


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
    return {"run": run, "state": st, "results": res, "manifest": man, "title": title, "source": source, "period": period}


def _charts_for(ctx: dict[str, Any], section: str) -> list[dict[str, Any]]:
    return [c for c in ctx["manifest"]["charts"] if c.get("section") == section and (ctx["run"] / "charts" / c["png"]).is_file()]


def _chart_slides(deck: Deck, ctx: dict[str, Any], section: str) -> int:
    n = 0
    for c in _charts_for(ctx, section):
        takeaways = c.get("takeaways") or [c.get("key_message", "")]
        notes = c.get("notes") or f"Key point: {c.get('key_message', '')}. {c.get('subtitle', '')}".strip()
        deck.chart(c["title"], ctx["run"] / "charts" / c["png"], takeaways, notes, c.get("source") or ctx["source"],
                   crop_top=c.get("title_crop", 0.0))
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


def build_standard_deck(run_dir: str | Path, out: str | Path | None = None, sections: Sequence[str] | None = None) -> Path:
    """Assemble ``deck.pptx`` for a run. Sections come from ``state.plan.deck_sections`` unless given.

    Recognised sections: exec_summary, setup, results, secondary, guardrails, segments, time, power,
    validation, risks, next_steps, appendix. Chart slides use ``charts/manifest.json`` entries whose
    ``section`` matches; tables and bullets are formatted from ``results.json``.
    """
    ctx = run_context(run_dir)
    st, res = ctx["state"], ctx["results"]
    summ = res.get("summary") or {}
    secs = list(sections or st["plan"].get("deck_sections") or DEFAULT_SECTIONS)
    deck = Deck(ctx["source"])
    deck.title_slide(ctx["title"], summ.get("headline", "Experiment readout"), None)

    for sec in secs:
        if sec == "exec_summary":
            if not summ:
                raise ValueError("results.json has no summary; run abkit.decision.build_summary first")
            bullets = [f"{k['label']}: {k['value']}" for k in summ.get("key_numbers", [])][:5]
            notes = (f"Verdict: {summ.get('verdict_label')}. {summ.get('reason', '')} {summ.get('plain_english', '')} "
                     + " ".join(summ.get("caveats", [])))
            deck.exec_summary(summ["verdict_label"], summ.get("verdict_color", "neutral"), summ["headline"], bullets, notes.strip(),
                              reason=summ.get("reason", ""))
        elif sec == "setup":
            rows = _setup_rows(ctx)
            deck.table("How the experiment was set up", ["Item", "Detail"], rows,
                       "Walk through what was tested, on whom, for how long, and how success was defined before looking at results.",
                       col_widths=[1, 3])
            _chart_slides(deck, ctx, "setup")
        elif sec in ("results", "secondary", "guardrails", "segments", "time", "power", "validation"):
            n = _chart_slides(deck, ctx, sec)
            if sec == "guardrails":
                g = R.all_results(res, role="guardrail")
                if g:
                    header, rows = results_table(g)
                    header, rows = header + ["Status"], [r + [str((x.get("extra") or {}).get("status", "n/a")).upper()] for r, x in zip(rows, g)]
                    deck.table("Guardrail checks", header, rows, "Each guardrail is tested for non-inferiority against its margin.",
                               font_size=11, status_col=len(header) - 1)
            elif sec == "validation" and res.get("validation"):
                v = res["validation"]
                deck.table(f"Data validation: overall verdict {v.get('verdict', 'n/a').upper()}", ["Check", "Verdict", "Detail"],
                           _validation_rows(res), "Summarise data quality: anything flagged here limits how far the results "
                           "can be trusted.", col_widths=[1.2, 0.8, 5], font_size=10, status_col=1)
            elif sec == "results" and not n:
                header, rows = results_table(R.all_results(res, role="primary") or R.all_results(res))
                deck.table("Results", header, rows, "Primary results.", font_size=11)
        elif sec == "risks":
            items = list(summ.get("caveats", []))
            for r in R.all_results(res):
                for a in r.get("assumptions", []):
                    if a.get("passed") is False:
                        items.append(f"Assumption not met ({r.get('metric')}): {a['check']}")
            items = items[:5] or ["No material risks identified by the analysis or the review."]
            deck.bullets("Risks and caveats to keep in mind", items, "Be explicit about what could make this conclusion wrong.",
                         kind="risks")
        elif sec == "next_steps":
            steps = list(summ.get("next_steps", [])) or [summ.get("reason", "Decide on rollout.")]
            deck.bullets(f"Recommendation: {summ.get('verdict_label', 'n/a')}", steps[:5],
                         f"Close with the decision and owners. {summ.get('reason', '')}", numbered=True, kind="next_steps",
                         label="Next steps")
        elif sec == "appendix":
            deck.section("Appendix", "Methodology, validation and full results")
            s = st["settings"]
            methods = _methods_used(res) + [f"Settings: alpha {s['alpha']} ({s['sidedness']}), power {s['power']}, "
                                            f"SRM threshold {s['srm_threshold']}"]
            deck.bullets("Methodology", methods[:8], "Tests used per analysis step and the scripts that produced each number.",
                         kind="appendix")
            if res.get("validation") and "validation" not in secs:
                deck.table("Data validation checks", ["Check", "Verdict", "Detail"], _validation_rows(res),
                           "Full list of validation checks.", col_widths=[1.2, 0.8, 5], font_size=10, status_col=1)
            allr = R.all_results(res)
            comp = [r for r in allr if r.get("rel_lift") is not None]
            if comp:
                header, rows = results_table(comp, include_segment=any(r.get("segment") for r in comp))
                for i in range(0, len(rows), 12):
                    deck.table("Full results" + (" (cont.)" if i else ""), header, rows[i:i + 12], "Complete table of estimates.",
                               font_size=9)
            _chart_slides(deck, ctx, "appendix")
        else:
            raise ValueError(f"Unknown deck section {sec!r}")

    path = Path(out) if out else ctx["run"] / "deck.pptx"
    deck.save(path)
    if deck.warnings:
        (ctx["run"] / "deck_warnings.txt").write_text("\n".join(deck.warnings) + "\n", encoding="utf-8")
    return path
