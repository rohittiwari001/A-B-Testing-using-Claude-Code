"""PostToolUse (Write|Edit): plotting code must use the house style.

For .py files under runs/*/code/ or abkit/viz/:
- importing matplotlib requires apply_style() (or new_figure(), or consulting.mplstyle);
- hex colours must be palette tokens.
Feedback goes back to Claude with exit code 2 (the edit itself already happened).
"""

from __future__ import annotations

import re
from pathlib import Path

from _hooklib import PALETTE_HEX, active_run, block, posix, project_dir, run_code_file, safe_main

IMPORTS_MPL = re.compile(r"^\s*(?:import\s+matplotlib|from\s+matplotlib\b)", re.M)
STYLED = re.compile(r"apply_style\s*\(|new_figure\s*\(|consulting\.mplstyle")
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")


def main(payload):
    project = project_dir(payload)
    if not active_run(project):
        return
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    p = posix(path)
    if not p.endswith(".py") or not (run_code_file(p) or re.search(r"(?:^|/)abkit/viz/[^/]+\.py$", p)):
        return
    file = Path(path) if Path(path).is_absolute() else project / path
    try:
        text = file.read_text(encoding="utf-8")
    except OSError:
        return
    problems = []
    if IMPORTS_MPL.search(text) and not STYLED.search(text):
        problems.append("imports matplotlib but never calls abkit.viz.apply_style() - call apply_style() before plotting "
                        "(or build figures with abkit.viz.new_figure()).")
    stray = sorted({h.upper() for h in HEX.findall(text)} - PALETTE_HEX)
    if stray:
        problems.append(f"hard-codes colours outside the palette: {', '.join(stray)} - use abkit.viz.PALETTE tokens "
                        "(ink, navy, accent, accent_light, grey_mid, grey_light, positive, negative, neutral).")
    if problems:
        block(f"style_guard: {Path(path).name} " + " Also: ".join(problems) + " See the consulting-charts skill.")


if __name__ == "__main__":
    safe_main(main)
