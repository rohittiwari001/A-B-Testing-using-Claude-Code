---
description: List run-local functions flagged for promotion and help move them into abkit with tests
argument-hint: "[candidate name]"
---

Promotion candidates across all runs:

!`python -m abkit.state candidates`

Candidate requested (optional): $ARGUMENTS

For the candidate the user picks:
1. Read the function in the run's code/ file. Generalise it: type hints, docstring with a short example, clear errors
   for bad input, returns `abkit.results.StatResult` (or a dict with the standard shape).
2. Add it to the target abkit module (or a new module if nothing fits - say which and why).
3. Add tests in `tests/` that validate it against a known answer, scipy/statsmodels, or simulation
   (A/A rejection rate near alpha, coverage of CIs).
4. If it belongs in the method library, add or update the matching `.claude/skills/ab-methods/references/*.md`
   entry (same seven sections) and the index in `.claude/skills/ab-methods/SKILL.md`.
5. Run `python -m pytest -q`; all tests must pass. Then remove the candidate from that run's results.json
   `candidates_for_promotion` list and tell the user what was added.
