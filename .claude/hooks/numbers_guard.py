"""PostToolUse (Write|Edit): deck (40_) and report (50_) scripts must not hard-code result numbers.

Flags, in runs/*/code/40_*.py and 50_*.py:
- percentages or p-values written inside string literals ("lift of +3.2%", "p = 0.004");
- numeric literals assigned to result-like names (lift = 0.032, "p_value": 0.01).
Layout numbers (Inches(0.5), Pt(14), width=...) are never flagged. Add "# numbers-ok" to a line to allow it.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

from _hooklib import active_run, block, project_dir, run_code_file, safe_main

PCT = re.compile(r"(?<![\w.{%])[+\-−]?\d+(?:\.\d+)?\s?%")
PVAL = re.compile(r"\bp\s*(?:=|<|>|<=|≤)\s*0?\.\d+", re.I)
RESULT_ASSIGN = re.compile(
    r"""["']?\b\w*(?:lift|p_?val(?:ue)?|estimate|ci_low|ci_high|prob(?:ability)?|effect|uplift)\w*["']?\s*[:=]\s*[-+]?\d*\.\d+""",
    re.I)
STRING_TOKENS = {tokenize.STRING} | ({tokenize.FSTRING_MIDDLE} if hasattr(tokenize, "FSTRING_MIDDLE") else set())


def find_problems(text: str) -> list[str]:
    lines = text.splitlines()
    allowed = {i + 1 for i, ln in enumerate(lines) if "numbers-ok" in ln}
    problems = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        tokens = []
    in_docstring_lines = set()
    for tok in tokens:
        if tok.type == tokenize.STRING and tok.string.startswith(('"""', "'''")):
            in_docstring_lines.update(range(tok.start[0], tok.end[0] + 1))
    for tok in tokens:
        if tok.type not in STRING_TOKENS or tok.start[0] in allowed or tok.start[0] in in_docstring_lines:
            continue
        s = tok.string
        for rx, what in ((PCT, "percentage"), (PVAL, "p-value")):
            m = rx.search(s)
            if m:
                problems.append(f"line {tok.start[0]}: {what} '{m.group(0)}' written into a string")
    for i, ln in enumerate(lines, 1):
        code = ln.split("#", 1)[0]
        if i in allowed or i in in_docstring_lines:
            continue
        m = RESULT_ASSIGN.search(code)
        if m:
            problems.append(f"line {i}: result-like literal '{m.group(0).strip()}'")
    return problems


def main(payload):
    project = project_dir(payload)
    if not active_run(project):
        return
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    m = run_code_file(path)
    if not m or not re.match(r"[45]0_", m.group(2)):
        return
    file = Path(path) if Path(path).is_absolute() else project / path
    try:
        text = file.read_text(encoding="utf-8")
    except OSError:
        return
    problems = find_problems(text)
    if problems:
        block(f"numbers_guard: {m.group(2)} appears to hard-code results:\n  - " + "\n  - ".join(problems[:8]) +
              "\nRead every number from results.json (abkit.results.load_results / get_result) and format it with "
              "abkit.results.fmt_pct / fmt_p / fmt_ci. Mark a genuine non-result number with '# numbers-ok'.")


if __name__ == "__main__":
    safe_main(main)
