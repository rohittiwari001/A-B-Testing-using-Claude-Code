"""Check that every percentage and p-value printed in a run's deck.pptx and summary.docx traces to results.json.

Run:  python -m abkit.tracecheck [run-id ...]      (default: every run in runs/ with a deck)

A printed number is "traced" when it equals a value from results.json formatted with the shared
abkit.results formatters (several precisions), or appears verbatim in a text field of results.json
(summary headline, caveats, validation details), which were themselves generated from results.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from docx import Document
from pptx import Presentation

from abkit import results as R
from abkit.state import project_root

ROOT = project_root()

TOKEN = re.compile(r"[+−-]?\d+(?:\.\d+)?%|p\s*[=<]\s*0?\.\d+")


def formatted_values(obj, out: set[str], text: list[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            formatted_values(v, out, text)
    elif isinstance(obj, list):
        for v in obj:
            formatted_values(v, out, text)
    elif isinstance(obj, bool) or obj is None:
        return
    elif isinstance(obj, (int, float)):
        x = float(obj)
        for d in (0, 1, 2):
            out |= {R.fmt_pct(x, d), R.fmt_pct(x, d, signed=False), R.fmt_pct(abs(x), d, signed=False), R.fmt_pct(-x, d)}
        out |= {R.fmt_prob(x), f"{x:.0%}", f"{x:.1%}", f"p = {R.fmt_p(x)}", f"p < 0.001" if x < 0.001 else f"p = {x:.3f}", f"p = {x:.4f}"}
        out.add(f"{round((1 - x) * 100)}%")      # confidence level from alpha
    elif isinstance(obj, str):
        text.append(obj)


def printed_tokens(run: Path) -> dict[str, set[str]]:
    deck = Presentation(str(run / "deck.pptx"))
    parts = [sh.text_frame.text for s in deck.slides for sh in s.shapes if sh.has_text_frame]
    parts += [c.text for s in deck.slides for sh in s.shapes if sh.has_table for row in sh.table.rows for c in row.cells]
    doc = Document(str(run / "summary.docx"))
    rparts = [p.text for p in doc.paragraphs] + [c.text for t in doc.tables for row in t.rows for c in row.cells]
    return {"deck": set(TOKEN.findall("\n".join(parts))), "report": set(TOKEN.findall("\n".join(rparts)))}


def check(run: Path) -> list[str]:
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    st = json.loads((run / "state.json").read_text(encoding="utf-8"))
    allowed: set[str] = set()
    text: list[str] = []
    formatted_values(res, allowed, text)
    formatted_values(st.get("settings", {}), allowed, text)
    formatted_values([m for m in st.get("metrics", [])], allowed, text)
    blob = "\n".join(text)
    problems = []
    for where, toks in printed_tokens(run).items():
        for tok in sorted(toks):
            norm = tok.replace("-", "−") if tok.startswith("-") else tok
            if tok in allowed or norm in allowed or tok.lstrip("+") in allowed or tok in blob:
                continue
            problems.append(f"{where}: {tok}")
    return problems


def main(argv: list[str]) -> int:
    ids = argv or sorted(p.name for p in (ROOT / "runs").iterdir() if (p / "deck.pptx").is_file())
    bad = 0
    for rid in ids:
        run = ROOT / "runs" / rid
        probs = check(run)
        toks = printed_tokens(run)
        print(f"{rid}: {len(toks['deck'])} distinct numbers in deck, {len(toks['report'])} in report -> "
              + ("all traced to results.json" if not probs else f"{len(probs)} untraced: {probs}"))
        bad += bool(probs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
