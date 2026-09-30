"""SessionStart: print a short status of the active run so the session resumes with context."""

from __future__ import annotations

from _hooklib import active_run, load_state, project_dir, safe_main

NEXT = {
    "intake": "finish intake Q&A (experiment-intake skill), write intake.md, then call experiment-planner",
    "planning": "show plan.md and wait for the user's explicit approval",
    "validation": "call data-validator; resolve blocking checks with the user",
    "analysis": "call stats-analyst for the pending plan steps",
    "review": "call stats-reviewer; loop fixes to stats-analyst (max 2 rounds)",
    "deliverables": "call viz-designer, then deck-builder and report-writer; then wrap up",
    "done": "run complete - answer follow-ups or start a new experiment",
}


def main(payload):
    found = active_run(project_dir(payload))
    if not found:
        return
    run_id, run = found
    st = load_state(run)
    if not st:
        print(f"[ab-workflow] Active run {run_id} has no readable state.json.")
        return
    g = st.get("gates", {})
    steps = st.get("plan", {}).get("steps", [])
    pending = [s.get("id") for s in steps if s.get("status") != "done"]
    phase = st.get("phase", "?")
    gates = ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in g.items())
    print(f"[ab-workflow] Active run: {run_id} | phase: {phase} | gates: {gates}")
    if steps:
        print(f"[ab-workflow] Plan: {len(steps) - len(pending)}/{len(steps)} steps done" +
              (f"; pending: {', '.join(pending[:6])}" if pending else ""))
    print(f"[ab-workflow] Next: {NEXT.get(phase, 'check state with python -m abkit.state status')}")


if __name__ == "__main__":
    safe_main(main)
