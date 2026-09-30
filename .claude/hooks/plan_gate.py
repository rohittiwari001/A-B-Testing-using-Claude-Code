"""PreToolUse (Bash|PowerShell): block phase scripts that run before their gates are open.

- 20_-50_ scripts need gates.plan_approved and gates.validation_passed.
- 40_ (deck) and 50_ (report) scripts also need gates.review_passed.
Only commands that *run* a script (python / py) are gated; reading or editing a script is not.
"""

from __future__ import annotations

import re

from _hooklib import active_run, block, load_state, posix, project_dir, safe_main

SCRIPT = re.compile(r"(?:^|[\s\"'/])(?:runs/(?P<run>[^/\s\"']+)/code/)?(?P<phase>[1-9]0)_[\w\-]*\.py\b")
RUNS_PYTHON = re.compile(r"(?:^|[\s;&|(])(?:python3?|py)(?:\.exe)?\b", re.I)

FIX = {
    "plan_approved": "Show plan.md to the user and get explicit approval, then run: python -m abkit.state gate plan_approved true",
    "validation_passed": "Run data-validator (10_validate_*.py) and resolve blocking checks with the user; the validator "
                         "sets the gate, or after the user's explicit decision: python -m abkit.state gate validation_passed true",
    "review_passed": "Run stats-reviewer and resolve its findings; the reviewer sets: python -m abkit.state gate review_passed true",
}


def main(payload):
    cmd = posix((payload.get("tool_input") or {}).get("command") or "")
    if not cmd or not RUNS_PYTHON.search(cmd):
        return
    project = project_dir(payload)
    found = active_run(project)
    if not found:
        return
    for m in SCRIPT.finditer(cmd):
        phase = int(m.group("phase"))
        if not 20 <= phase <= 50:
            continue
        run = project / "runs" / m.group("run") if m.group("run") else found[1]
        st = load_state(run) or load_state(found[1])
        if not st:
            return
        g = st.get("gates", {})
        needed = ["plan_approved", "validation_passed"] + (["review_passed"] if phase >= 40 else [])
        missing = [k for k in needed if not g.get(k)]
        if missing:
            script = m.group(0).strip(" \"'/")
            block(f"plan_gate: blocked {script} (phase {phase}_) for run {st.get('run_id')}: "
                  f"gate(s) not open: {', '.join(missing)}.\n" + "\n".join(f"- {k}: {FIX[k]}" for k in missing))


if __name__ == "__main__":
    safe_main(main)
