"""Word summary report built with python-docx, sharing fonts and colours with the deck.

- :class:`Report` - primitives: title block, verdict box, headings (built-in Heading styles),
  paragraphs, bullets, figures and tables with numbered captions.
- :func:`build_standard_report` - assembles ``summary.docx`` for a run: a first page a
  non-statistician can read (verdict first), then the full method and results for a data scientist.

Example
-------
>>> from abkit.report import build_standard_report
>>> path = build_standard_report("runs/2026-10-01_checkout-button")      # doctest: +SKIP
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from abkit import results as R
from abkit.deck.builder import _methods_used, _setup_rows, _validation_rows, results_table, run_context
from abkit.viz.style import PALETTE

FONT = "Arial"
DEFAULT_SECTIONS = ["exec_summary", "business_question", "design", "data_validation", "methodology", "results",
                    "guardrails", "segments", "risks", "recommendation", "appendix"]


def _rgb(token: str) -> RGBColor:
    return RGBColor.from_string(PALETTE.get(token, token).lstrip("#").upper())


def _shade(cell, token: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), PALETTE.get(token, token).lstrip("#"))
    tc_pr.append(shd)


def _set_font(style, size: float, bold: bool = False, color: str = "ink") -> None:
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = _rgb(color)
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), FONT)


class Report:
    """Document with the house style applied to the built-in styles."""

    def __init__(self) -> None:
        self.doc = Document()
        sec = self.doc.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        for side in ("left_margin", "right_margin"):
            setattr(sec, side, Cm(2.2))
        sec.top_margin = sec.bottom_margin = Cm(2.0)
        st = self.doc.styles
        _set_font(st["Normal"], 10.5)
        st["Normal"].paragraph_format.space_after = Pt(6)
        _set_font(st["Title"], 24, True, "ink")
        _set_font(st["Heading 1"], 15, True, "navy")
        _set_font(st["Heading 2"], 12, True, "navy")
        _set_font(st["Heading 3"], 11, True, "ink")
        _set_font(st["Caption"], 9, False, "grey_mid")
        st["Caption"].font.italic = False
        for name in ("List Bullet", "List Number"):
            _set_font(st[name], 10.5)
        self.n_fig = 0
        self.n_tab = 0
        self.headings: list[str] = []
        self.width = sec.page_width - sec.left_margin - sec.right_margin
        footer = sec.footer.paragraphs[0]
        footer.text = ""

    def title(self, title: str, subtitle: str = "", meta: str = "") -> None:
        self.doc.add_paragraph(title, style="Title")
        if subtitle:
            p = self.doc.add_paragraph()
            r = p.add_run(subtitle)
            r.font.size, r.font.color.rgb = Pt(13), _rgb("grey_mid")
        if meta:
            p = self.doc.add_paragraph()
            r = p.add_run(meta)
            r.font.size, r.font.color.rgb = Pt(9), _rgb("grey_mid")

    def footer(self, text: str) -> None:
        p = self.doc.sections[0].footer.paragraphs[0]
        p.text = text
        for r in p.runs:
            r.font.size, r.font.color.rgb, r.font.name = Pt(8), _rgb("grey_mid"), FONT

    def verdict_box(self, label: str, color: str, headline: str, reason: str = "") -> None:
        t = self.doc.add_table(rows=1, cols=1)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = t.cell(0, 0)
        _shade(cell, color)
        p = cell.paragraphs[0]
        r = p.add_run(f"Recommendation: {label.upper()}")
        r.font.bold, r.font.size, r.font.color.rgb = True, Pt(14), _rgb("white")
        p2 = cell.add_paragraph()
        r2 = p2.add_run(headline)
        r2.font.size, r2.font.color.rgb, r2.font.bold = Pt(11), _rgb("white"), True
        if reason:
            p3 = cell.add_paragraph()
            r3 = p3.add_run(reason)
            r3.font.size, r3.font.color.rgb = Pt(10), _rgb("white")
        self.doc.add_paragraph()

    def heading(self, text: str, level: int = 1) -> None:
        self.doc.add_heading(text, level=level)
        if level == 1:
            self.headings.append(text)

    def para(self, text: str, bold_lead: str | None = None) -> None:
        p = self.doc.add_paragraph()
        if bold_lead:
            p.add_run(bold_lead).bold = True
        p.add_run(text)

    def bullets(self, items: Sequence[str], numbered: bool = False) -> None:
        for it in items:
            p = self.doc.add_paragraph(style="List Number" if numbered else "List Bullet")
            if ": " in it and len(it.split(": ", 1)[0]) < 60:
                head, tail = it.split(": ", 1)
                p.add_run(head + ": ").bold = True
                p.add_run(tail)
            else:
                p.add_run(it)

    def figure(self, image: str | Path, caption: str, width_frac: float = 1.0) -> None:
        self.n_fig += 1
        self.doc.add_picture(str(image), width=int(self.width * width_frac))
        self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.doc.add_paragraph(f"Figure {self.n_fig}: {caption}", style="Caption")

    def table(self, header: Sequence[str], rows: Sequence[Sequence[Any]], caption: str, font_size: float = 8.5,
              col_widths: Sequence[float] | None = None, status_col: int | None = None) -> None:
        self.n_tab += 1
        self.doc.add_paragraph(f"Table {self.n_tab}: {caption}", style="Caption")
        t = self.doc.add_table(rows=len(rows) + 1, cols=len(header))
        t.style = self.doc.styles["Table Grid"]
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        colors = {"PASS": "positive", "BREACH": "negative", "BLOCK": "negative", "WARN": "neutral", "INCONCLUSIVE": "neutral"}
        for r, vals in enumerate([header, *rows]):
            for c, v in enumerate(vals):
                cell = t.cell(r, c)
                cell.text = ""
                run = cell.paragraphs[0].add_run("" if v is None else str(v))
                run.font.size = Pt(font_size)
                if r == 0:
                    _shade(cell, "navy")
                    run.font.bold, run.font.color.rgb = True, _rgb("white")
                elif status_col is not None and c == status_col:
                    run.font.bold, run.font.color.rgb = True, _rgb(colors.get(str(v).upper(), "ink"))
        if col_widths:
            tot = sum(col_widths)
            for row in t.rows:
                for i, cw in enumerate(col_widths):
                    row.cells[i].width = int(self.width * cw / tot)
        self.doc.add_paragraph()

    def page_break(self) -> None:
        self.doc.add_page_break()

    def save(self, path: str | Path) -> Path:
        self.doc.save(str(path))
        return Path(path)


# --------------------------------------------------------------------------- run-level assembly


def _md_sections(text: str) -> dict[str, str]:
    """Split markdown into {heading (lowercase): body}."""
    out, cur, buf = {}, "_top", []
    for line in text.splitlines():
        m = re.match(r"^#{1,4}\s+(.*)", line)
        if m:
            out[cur] = "\n".join(buf).strip()
            cur, buf = m.group(1).strip().lower(), []
        else:
            buf.append(line)
    out[cur] = "\n".join(buf).strip()
    return out


def _md_to_items(body: str) -> list[str]:
    items = [re.sub(r"^\s*([-*]|\d+\.)\s+", "", ln).strip() for ln in body.splitlines()]
    return [re.sub(r"\*\*(.+?)\*\*", r"\1", i) for i in items if i]


def _figures(rep: Report, ctx: dict[str, Any], sections: Sequence[str]) -> int:
    n = 0
    for c in ctx["manifest"]["charts"]:
        if c.get("section") in sections and (ctx["run"] / "charts" / c["png"]).is_file():
            rep.figure(ctx["run"] / "charts" / c["png"], f"{c['title']}. {c.get('subtitle', '')}".strip())
            n += 1
    return n


def build_standard_report(run_dir: str | Path, out: str | Path | None = None, sections: Sequence[str] | None = None) -> Path:
    """Assemble ``summary.docx`` for a run. Sections come from ``state.plan.report_sections`` unless given."""
    ctx = run_context(run_dir)
    st, res, run = ctx["state"], ctx["results"], ctx["run"]
    summ = res.get("summary") or {}
    secs = list(sections or st["plan"].get("report_sections") or DEFAULT_SECTIONS)
    intake = _md_sections((run / "intake.md").read_text(encoding="utf-8")) if (run / "intake.md").is_file() else {}
    rep = Report()
    rep.title(ctx["title"], summ.get("headline", "Experiment summary"), f"{ctx['source']}")
    rep.footer(f"{ctx['title']} | {run.name} | every number is sourced from results.json")

    for sec in secs:
        if sec == "exec_summary":
            if not summ:
                raise ValueError("results.json has no summary; run abkit.decision.build_summary first")
            rep.heading("Executive summary")
            rep.verdict_box(summ["verdict_label"], summ.get("verdict_color", "neutral"), summ["headline"], summ.get("reason", ""))
            if summ.get("plain_english"):
                rep.para(summ["plain_english"], bold_lead="In plain terms: ")
            rep.bullets([f"{k['label']}: {k['value']}" for k in summ.get("key_numbers", [])])
            if summ.get("caveats"):
                rep.para(" ".join(summ["caveats"]), bold_lead="Caveats: ")
            if summ.get("next_steps"):
                rep.para(summ["next_steps"][0], bold_lead="Next step: ")
            rep.page_break()
        elif sec == "business_question":
            rep.heading("Business question and hypothesis")
            found = False
            for key in ("business question", "decision", "hypothesis"):
                for h, body in intake.items():
                    if key in h and body:
                        rep.heading(h.capitalize(), 2)
                        rep.para(" ".join(_md_to_items(body)))
                        found = True
                        break
            ctx_text = (run / "context.md").read_text(encoding="utf-8").strip() if (run / "context.md").is_file() else ""
            if ctx_text:
                rep.heading("Context as described", 2)
                for para in ctx_text.split("\n\n"):
                    rep.para(para.replace("\n", " "))
            elif not found:
                rep.para("No context recorded.")
        elif sec == "design":
            rep.heading("Experiment design")
            rep.table(["Item", "Detail"], _setup_rows(ctx), "Experiment setup", 9.5, [1, 3])
            _figures(rep, ctx, ["setup"])
        elif sec == "data_validation":
            rep.heading("Data and validation")
            v = res.get("validation") or {}
            if v:
                rep.para(f"Overall validation verdict: {v.get('verdict', 'n/a').upper()}. "
                         "Checks follow; outliers are reported, never removed automatically.")
                rep.table(["Check", "Verdict", "Detail"], _validation_rows(res), "Validation checks", 8.5, [1.2, 0.8, 5], 1)
            _figures(rep, ctx, ["validation"])
        elif sec == "methodology":
            rep.heading("Methodology")
            rep.bullets(_methods_used(res))
            s = st["settings"]
            rep.para(f"Significance level {s['alpha']} ({s['sidedness']}), target power {s['power']}; corrections: primary "
                     f"{s['correction_primary']}, secondary {s['correction_secondary']}, segments {s['correction_segments']}. "
                     f"SRM threshold p < {s['srm_threshold']}.")
            if "results" not in secs:
                _figures(rep, ctx, ["power", "time"])
        elif sec == "results":
            rep.heading("Results")
            _figures(rep, ctx, ["results", "secondary", "power", "time"])
            rows = [r for r in R.all_results(res) if r.get("role") in ("primary", "secondary") and r.get("rel_lift") is not None]
            if rows:
                h, t = results_table(rows)
                rep.table(h, t, "Primary and secondary metrics")
        elif sec == "guardrails":
            g = R.all_results(res, role="guardrail")
            if g or any(c.get("section") == "guardrails" for c in ctx["manifest"]["charts"]):
                rep.heading("Guardrails")
                _figures(rep, ctx, ["guardrails"])
                if g:
                    h, t = results_table(g)
                    h, t = h + ["Status"], [r + [str((x.get("extra") or {}).get("status", "n/a")).upper()] for r, x in zip(t, g)]
                    rep.table(h, t, "Guardrail non-inferiority tests", status_col=len(h) - 1)
        elif sec == "segments":
            seg = [r for r in R.all_results(res, role="segment") if r.get("rel_lift") is not None]
            if seg or any(c.get("section") == "segments" for c in ctx["manifest"]["charts"]):
                rep.heading("Segments")
                rep.para("Segments were pre-specified; p-values are corrected across segments. A difference between segments "
                         "is only claimed when the interaction test supports it.")
                _figures(rep, ctx, ["segments"])
                if seg:
                    h, t = results_table(seg, include_segment=True)
                    rep.table(h, t, "Effect by segment")
                inter = [r for r in R.all_results(res) if r.get("method") == "segments.interaction_test"]
                for r in inter:
                    rep.para(f"Interaction test for {r.get('segment')}: {R.fmt_p_stat(r.get('p_value'))}. " + " ".join(r.get("notes", [])))
        elif sec == "risks":
            rep.heading("Risks, limitations and assumptions")
            items = list(summ.get("caveats", []))
            for r in R.all_results(res):
                for a in r.get("assumptions", []):
                    if a.get("passed") is False:
                        items.append(f"Assumption not met for {r.get('metric')}: {a['check']} ({a.get('detail', '')})")
            rep.bullets(items or ["No material risks identified by the analysis or the review."])
        elif sec == "recommendation":
            rep.heading("Recommendation and next steps")
            rep.para(summ.get("reason", ""), bold_lead=f"{summ.get('verdict_label', 'n/a')}. ")
            if summ.get("next_steps"):
                rep.bullets(summ["next_steps"], numbered=True)
        elif sec == "appendix":
            rep.page_break()
            rep.heading("Appendix")
            rep.heading("Settings", 2)
            s = st["settings"]
            rep.table(["Setting", "Value"], [[k, str(v)] for k, v in s.items()], "Statistical settings used", 8.5, [2, 2])
            if st.get("overrides"):
                rep.para(", ".join(f"{k}: {v['from']} -> {v['to']}" for k, v in st["overrides"].items()), bold_lead="Overrides: ")
            rep.heading("Reviewer findings", 2)
            review = run / "review.md"
            if review.is_file():
                rounds = re.split(r"^(?=# Review)", review.read_text(encoding="utf-8"), flags=re.M)
                latest = [r for r in rounds if r.strip()][-1]            # earlier rounds may quote superseded numbers
                title = latest.splitlines()[0].lstrip("# ").strip()
                rep.para(f"{title}. Earlier rounds are in review.md.")
                rep.bullets(_md_to_items(re.sub(r"^#.*$", "", latest, flags=re.M))[:25])
            else:
                rep.bullets(["No review.md found."])
            allr = [r for r in R.all_results(res) if r.get("rel_lift") is not None]
            if allr:
                h, t = results_table(allr, include_segment=any(r.get("segment") for r in allr))
                rep.table(h, t, "All estimates", 7.5)
            _figures(rep, ctx, ["appendix"])
            rep.heading("Code index", 2)
            scripts = sorted((run / "code").glob("*.py"))
            rep.bullets([f"{p.name}: {_first_doc_line(p)}" for p in scripts] or ["No scripts."])
        else:
            raise ValueError(f"Unknown report section {sec!r}")

    return rep.save(Path(out) if out else run / "summary.docx")


def _first_doc_line(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'^\s*(?:"""|\'\'\')\s*(.+)', text, re.M)
    return m.group(1).strip().rstrip('"') if m else "(no docstring)"
