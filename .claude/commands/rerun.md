---
description: Rerun a phase of the active run and everything downstream
argument-hint: "<validation|analysis|review|deliverables>"
---

Rerun phase "$ARGUMENTS" of the active run and everything after it.

!`python -m abkit.state status || echo "No active run."`

1. Valid phases: validation, analysis, review, deliverables (planning means revising the plan and needs the user's
   approval again). If the argument is missing or invalid, ask.
2. Run `python -m abkit.state reset <phase>` (re-opens that phase's gates and later ones).
3. For analysis: mark the affected plan steps `pending` (`abkit.state.set_step_status`) before calling stats-analyst.
4. Continue through the phases as in CLAUDE.md from that point: validation -> analysis -> review -> deliverables ->
   wrap-up, regenerating every affected deliverable.
