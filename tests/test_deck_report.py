"""Smoke tests: build a deck and a report from a sample run and check structure and numbers."""

import json
import re
import sys

import pytest
from docx import Document
from pptx import Presentation

from abkit import results as R
from abkit.deck import Deck, build_standard_deck
from abkit.report import build_standard_report


@pytest.fixture(scope="module")
def sample_run(tmp_path_factory, demo_csvs):
    import shutil

    from conftest import ROOT

    root = tmp_path_factory.mktemp("proj")
    shutil.copytree(ROOT / "config", root / "config")
    (root / "runs").mkdir()
    sys.path.insert(0, str(demo_csvs))
    from sample_run import build_checkout_sample

    return build_checkout_sample(root=root)


def deck_text(prs):
    return "\n".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame) + "\n" + "\n".join(
        c.text for s in prs.slides for sh in s.shapes if sh.has_table for row in sh.table.rows for c in row.cells)


def test_deck_structure_and_numbers(sample_run):
    path = build_standard_deck(sample_run)
    prs = Presentation(str(path))
    assert prs.slide_width / prs.slide_height == pytest.approx(16 / 9, rel=0.01)
    # title + exec + setup + 3 results charts + guardrail chart + guardrail table + segments chart + risks + next steps
    # + appendix divider + methodology + validation + full results (1 page)
    assert len(prs.slides) == 15
    res = json.loads((sample_run / "results.json").read_text())
    text = deck_text(prs)
    assert res["summary"]["headline"] in text
    for k in res["summary"]["key_numbers"]:
        assert k["value"] in text
    p = res["steps"]["primary_test"]["results"][0]
    assert R.fmt_pct(p["rel_lift"]) in text and R.fmt_ci(p["rel_ci_low"], p["rel_ci_high"]) in text
    content = [s for s in list(prs.slides)[1:] if not all(sh.shape_type == 1 or not sh.has_text_frame or sh.text_frame.text in ("Appendix", "Methodology, validation and full results") for sh in s.shapes)]
    for s in content:
        assert s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip()


def test_deck_numbers_all_trace_to_results(sample_run):
    """Every percentage printed in the deck appears among values formatted from results.json."""
    prs = Presentation(str(build_standard_deck(sample_run)))
    res = R.load_results(sample_run)
    allowed = set()
    for r in R.all_results(res) + [res["steps"]["segments"]["data"]["overall"]]:
        for k in ("rel_lift", "rel_ci_low", "rel_ci_high", "control_value", "treatment_value"):
            if r.get(k) is not None:
                allowed |= {R.fmt_pct(r[k]), R.fmt_pct(r[k], signed=False, decimals=2), R.fmt_pct(r[k], 0),
                            R.fmt_pct(abs(r[k]), signed=False)}
        if r.get("alpha"):
            allowed.add(f"{round((1 - r['alpha']) * 100)}%")
        m = (r.get("extra") or {}).get("margin_rel")
        if m is not None:
            allowed |= {f"{m:.0%}", f"{m:.1%}"}
    for c in res["validation"]["checks"]:
        allowed |= set(re.findall(r"[\d.]+%", str(c["detail"])))
    printed = set(re.findall(r"[+\u2212-]?\d+(?:\.\d+)?%", deck_text(prs)))
    allowed |= {f"{res['summary']['mde_rel']:.0%}", "100%"}          # practical threshold; rollout wording in next steps
    unknown = {x for x in printed if x not in allowed and x.lstrip("+") not in allowed}
    assert not unknown, f"numbers in deck not traceable to results.json: {unknown}"


def test_report_sections_and_captions(sample_run):
    path = build_standard_report(sample_run)
    doc = Document(str(path))
    h1 = [p.text for p in doc.paragraphs if p.style.name == "Heading 1"]
    assert h1 == ["Executive summary", "Business question and hypothesis", "Experiment design", "Data and validation",
                  "Methodology", "Results", "Guardrails", "Segments", "Risks, limitations and assumptions",
                  "Recommendation and next steps", "Appendix"]
    captions = [p.text for p in doc.paragraphs if p.style.name == "Caption"]
    assert sum(c.startswith("Figure") for c in captions) == 5
    assert sum(c.startswith("Table") for c in captions) == len(doc.tables) - 1       # verdict box is a 1-cell table
    body = "\n".join(p.text for p in doc.paragraphs) + "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    res = R.load_results(sample_run)
    assert res["summary"]["headline"] in body
    for k in res["summary"]["key_numbers"]:
        assert k["value"] in body
    assert doc.styles["Normal"].font.name == "Arial"


def test_deck_sizes_with_plan():
    """A power-analysis style deck with few sections stays short; word-count warnings fire on long text."""
    d = Deck("src")
    d.title_slide("Power analysis", "How long to run")
    d.bullets("Too many words", ["word " * 80], "notes")
    assert len(d.prs.slides) == 2 and d.warnings


def test_missing_summary_raises(sample_run):
    res = R.load_results(sample_run)
    saved = res["summary"]
    res["summary"] = {}
    R.save_results(sample_run, res)
    try:
        with pytest.raises(ValueError):
            build_standard_deck(sample_run)
    finally:
        res["summary"] = saved
        R.save_results(sample_run, res)
