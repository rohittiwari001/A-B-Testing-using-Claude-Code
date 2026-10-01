# A/B testing workflow for Claude Code

Open this folder in Claude Code, give it a CSV and a plain-English description, and it runs a rigorous
experiment analysis: clarifying questions, a plan you approve, data validation, the planned statistics,
an independent review, then consulting-style charts, a PowerPoint deck and a Word summary.

**Setup (once):** `pip install -r requirements.txt && pip install -e .` and `python demo_data/generate.py`.
Check with `python -m pytest -q`.

## Start a new experiment
Say something like: *"Here's `data/checkout.csv`: one row per user with variant, platform, converted and
revenue. We tested a one-click checkout; should we ship it?"* (or `/new-experiment path/to/file.csv`).
Claude creates `runs/<date>_<slug>/`, asks only the questions your description leaves open (plus keep-or-change
for the statistical defaults), proposes a plan and **waits for your approval**. It then validates the data,
stops and explains if something blocks the analysis (e.g. a sample ratio mismatch), runs and reviews the analysis,
and delivers `charts/`, `deck.pptx`, `summary.docx` (stakeholders) and `technical_report.docx` (methods, formulas,
decision log and reproducibility for data scientists) with a short chat summary.

## Resume a run
Just reopen the folder: the session-start hook prints the active run, its phase and the next step.
`/status` shows progress, `/switch-run <run-id>` changes the active run.

## Ask follow-ups
Ask in plain English, for example *"now split by platform"* or *"rerun with alpha 0.01"*. Claude updates the
same run: it changes the settings or the plan (asking you first if the method changes), reruns only the affected
phases and regenerates the deliverables. `/rerun <phase>` forces a rerun. General questions
(*"when should I use CUPED?"*) are answered directly, with no run created.

## Add a new method
If an analysis needs a method abkit lacks, the analyst writes it in the run's `code/` folder and flags it as a
promotion candidate. Run `/promote` to move it into `abkit/` with tests and a method page in
`.claude/skills/ab-methods/references/`. To add one by hand: write the function (returning a `StatResult`), add a
test that checks it against a known answer or a simulation, and add the method page plus an index row.

## What is where
`CLAUDE.md` holds the orchestration rules. `.claude/agents` has the 7 subagents, `.claude/skills` the methods,
chart, deck, report, intake and defaults skills, and `.claude/hooks` the gates, style checks, logging and
completeness check. `abkit/` is the Python toolkit, `config/stat_defaults.yaml` holds the defaults,
`demo_data/` has 7 synthetic experiments, and `docs/` has the chart gallery and a sample deck and report.
