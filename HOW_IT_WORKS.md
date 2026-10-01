# How the A/B testing pipeline works

A guide for anyone who wants to use this pipeline: what it does, how a run flows from your data to the final deck,
what you are asked to decide, and (in Part 2) how it works under the hood and how to extend it.

---

# Part 1: Using the pipeline

## 1. What it does

You give it **a CSV file** and **a plain-English description** of your experiment. It behaves like an experienced
product data scientist:

- asks only the questions your description leaves open;
- proposes an analysis plan and **waits for your approval**;
- checks the data and **stops to ask you** if something is wrong (e.g. the traffic split doesn't match the design);
- runs the statistics your problem needs (not a fixed recipe);
- has an independent reviewer check the work;
- delivers **charts, a PowerPoint deck, a stakeholder report and a technical report**, with every number traceable
  to one results file.

It handles many kinds of problems: a standard test readout, sample-size / power planning, broken traffic splits,
Bayesian readouts, variance reduction with pre-period data (CUPED), sequential monitoring, segment deep-dives,
multi-arm tests, ratio metrics (e.g. click-through rate per session), novelty effects, guardrail checks, and
non-randomised launches (difference-in-differences).

## 2. Quick start

**One-time setup** (from the project folder):
```
pip install -r requirements.txt
pip install -e .
python demo_data/generate.py        # optional: 7 demo experiments to practise on
python -m pytest -q                 # optional: check everything works
```

**Start an analysis.** Open this folder in Claude Code and write, in plain English:
```
Here is my experiment data @data/my_test.csv described in @data/my_test.md.
Should we ship the new version?
```
`@` attaches a file. The last line is your question; change it to whatever you need answered. You can also use the
shortcut `/new-experiment data/my_test.csv`.

**What to put in the description** (the more you cover, the fewer questions you get):
what was tested, what each column means, which group is the control, the intended traffic split, the main metric,
anything that must not get worse (guardrails), the smallest lift worth acting on, the test dates, and anything
unusual that happened during the test.

## 3. The flow at a glance

```
   YOU: CSV + description
            |
            v
  +-------------------+     asks only the open questions, shows the statistical defaults
  | 1. INTAKE         |     -> you answer (one batch, with suggested defaults)
  +-------------------+
            |
            v
  +-------------------+     picks methods, charts, deck sections for YOUR problem
  | 2. PLANNING       |     -> you approve  ................................ [GATE: plan approved]
  +-------------------+
            |
            v
  +-------------------+     duplicates, traffic split, outliers, impossible values ...
  | 3. VALIDATION     |     -> if something blocks: it STOPS and you decide . [GATE: validation passed]
  +-------------------+
            |
            v
  +-------------------+     runs each planned step; every number saved to results.json
  | 4. ANALYSIS       |
  +-------------------+
            |
            v
  +-------------------+     independent check; small fixes loop back (max 2),
  | 5. REVIEW         |     anything that could change the conclusion comes to you  [GATE: review passed]
  +-------------------+
            |
            v
  +-------------------+     charts -> deck -> stakeholder report + technical report
  | 6. DELIVERABLES   |
  +-------------------+
            |
            v
  +-------------------+     checks every deliverable exists and every number traces back,
  | 7. WRAP-UP        |     then gives you a short chat summary
  +-------------------+
```

## 4. What happens in each phase, and what you do

| Phase | What the pipeline does | What you do |
|---|---|---|
| 1. Intake | Creates a run folder, copies your CSV (the original is never changed), reads the data, asks the open questions in one batch, shows the default statistical settings | Answer; "all defaults except 2: use 3%" is fine |
| 2. Planning | Classifies the problem, chooses methods with a one-line reason each, picks charts and deck sections | Reply **"approved"** or ask for changes. Nothing is calculated before this |
| 3. Validation | Runs about a dozen data checks. A blocking problem (e.g. sample ratio mismatch, missing groups) stops the run with an explanation and options | Choose an option when asked |
| 4. Analysis | Runs only the planned steps, one small script each; saves every number with the script that produced it | Nothing |
| 5. Review | A separate reviewer re-checks the work from the files alone, including recomputing key numbers from your data | Decide only if a finding could change the conclusion |
| 6. Deliverables | Builds the charts, the deck and both reports from the saved numbers | Nothing |
| 7. Wrap-up | Confirms completeness and number traceability; summarises the verdict, key numbers, caveats and file paths | Read; ask follow-ups |

**You are only interrupted for decisions that are genuinely yours:** plan approval, blocking data problems, and
review findings that could change the recommendation.

## 5. What you get

Every analysis lives in its own folder, `runs/<date>_<name>/`:

```
runs/<date>_<name>/
|-- deck.pptx               the stakeholder deck
|-- summary.docx            plain-language report (verdict on page one)
|-- technical_report.docx   for data scientists: methods, formulas, decision log, how to reproduce
|-- charts/                 every chart as PNG (300 dpi) and SVG
|-- results.json            the single source of truth for every number
|-- context.md, intake.md   your description, the questions and your answers and decisions
|-- plan.md                 the approved plan
|-- data_profile.md         the data checks
|-- review.md               the reviewer's findings, round by round
|-- code/                   every script that produced a number
|-- data/                   a copy of your CSV
|-- state.json              phase, approvals and settings (drives the automation)
`-- run_log.jsonl           every command that was run
```

**The deck** always follows the same consulting-style storyline, whatever the problem:

```
 Title -> Executive summary (the answer first) -> Agenda
   1 The ask          question, decision, hypothesis, what was tested
   2 Approach         data -> quality checks -> analysis -> independent review
   3 Findings         one message per slide, headline result first   <- only this part changes per problem
   4 Impact           a few big numbers in business terms
   5 Recommendation   risks, then the decision and next steps (owner, timing)
 Appendix             methodology, validation, full results
```

The slide titles alone tell the story; they are listed in `deck_storyline.md`.

**The two reports:** `summary.docx` is for stakeholders (plain language first). `technical_report.docx` is for data
scientists: formal hypotheses, every method with its formula and assumptions, all estimates, robustness checks, the
full decision log, and the exact commands to reproduce the run.

## 6. After the first answer

| You want to... | Do this |
|---|---|
| Change something | Ask in plain English: *"split by platform"*, *"rerun with alpha 0.01"*, *"add revenue as a guardrail"*. The same run is updated; only affected phases rerun |
| Come back later | Reopen the folder. The pipeline tells you the active run, its phase and the next step |
| See progress | `/status` |
| Switch between experiments | `/switch-run <run-id>` |
| Force a phase to rerun | `/rerun analysis` (or validation, review, deliverables) |
| Ask a general question | *"When should I use CUPED?"* is answered directly; no run is created |

## 7. A very short example

> **You:** "Here's `data/checkout.csv`, one row per user: variant, converted, revenue. We tested a one-click
> checkout, 50/50 split. Should we ship it?"
> **Pipeline:** asks 3 questions (smallest lift worth shipping? any revenue drop we must avoid? did anyone stop the
> test early?), then proposes: data checks -> z-test on conversion -> non-inferiority test on revenue -> decision.
> **You:** "approved".
> **Pipeline:** checks pass -> conversion +3.2% (p = 0.001), revenue holds -> reviewer passes -> delivers
> `deck.pptx`, `summary.docx`, `technical_report.docx` and charts, with the verdict **Ship**.

---

# Part 2: Under the hood

## 8. Architecture

```
                         +--------------------------------+
   you  <-------------->|  ORCHESTRATOR                   |   the main Claude Code session
                         |  rules: CLAUDE.md               |   runs the phases, talks to you, holds the gates
                         +---------------+----------------+
                                         | calls, in order
     +--------------+--------------+-----+--------+--------------+--------------+--------------+
     v              v              v              v              v              v              v
 experiment-    data-          stats-         stats-         viz-           deck-          report-
 planner        validator      analyst        reviewer       designer       builder        writer
     |              |              |              |              |              |              |
     +--------------+--------------+------+-------+--------------+--------------+--------------+
                                          | read / write
                                          v
                        +----------------------------------+
                        |  RUN FOLDER  runs/<date>_<name>/  |  state.json, results.json, code/, charts/ ...
                        +----------------------------------+
                                          ^
       uses                               | every number via
  +-------------------+         +-------------------+
  | SKILLS            |         | abkit             |  tested Python toolkit: statistics,
  | .claude/skills/   |         | (Python package)  |  checks, charts, deck & report builders
  +-------------------+         +-------------------+

  HOOKS (.claude/hooks/) watch every action automatically and block mistakes.
```

## 9. The agents (`.claude/agents/`)

Each agent is a specialist with one job and only the tools it needs. They always read `runs/.active` (the active
run) and `state.json` first, and write their outputs to the run folder.

| Agent | Phase | Job | Writes |
|---|---|---|---|
| experiment-planner | 2 | Classifies the problem, picks methods / charts / deck sections with reasons | `plan.md`, plan in `state.json` |
| data-validator | 3 | Profiles the data; stops on blocking problems | `data_profile.md`, validation in `results.json`, `code/10_*` |
| stats-analyst | 4 | Executes the plan exactly, abkit first; writes new methods if needed and flags them | `code/20_*`, `results.json` |
| stats-reviewer | 5 | Independent skeptic; checklist of 13 items; recomputes numbers | `review.md`, review gate |
| viz-designer | 6 | Charts in the house style with action titles and takeaways | `code/30_*`, `charts/` |
| deck-builder | 6 | Deck in the fixed storyline; ghost-deck test | `code/40_*`, `deck.pptx`, `deck_storyline.md` |
| report-writer | 6 | Stakeholder report and technical report | `code/50_*`, `summary.docx`, `technical_report.docx` |

## 10. The skills (`.claude/skills/`)

Reference knowledge the agents load when relevant:

| Skill | Contents |
|---|---|
| experiment-intake | The question bank and how to ask only what is unknown |
| ab-methods | Index from problem type and metric type to method, plus 14 method pages (when to use, assumptions, steps, abkit functions, interpretation, pitfalls, how to present) |
| stat-defaults | The default settings, when to deviate, how overrides are recorded |
| consulting-charts | Palette, typography, action-title rules, the 15-chart catalogue, pre-save checklist |
| deck-style | The fixed deck storyline, slide anatomy, wording and visual rules |
| report-style | Structure of `summary.docx` and `technical_report.docx` |

## 11. The gates and hooks

**Gates** are approvals stored in `state.json`: `plan_approved`, `validation_passed`, `review_passed`.

**Hooks** are small Python scripts that Claude Code runs automatically (wired in `.claude/settings.json`). If
there is no active run they do nothing, and they never crash the session.

| Hook | Runs when | Rule |
|---|---|---|
| `session_start.py` | A session starts | Prints the active run, its phase, gates and next step |
| `plan_gate.py` | Before any shell command | Blocks analysis / chart / deck / report scripts (`20_`-`50_`) until plan and validation gates are open, and deck / report scripts (`40_`, `50_`) until the review passes |
| `style_guard.py` | After a file is written | Plotting code must call the house style and use only palette colours |
| `numbers_guard.py` | After a file is written | Deck and report scripts must not type result numbers by hand |
| `run_logger.py` | After any shell command | Appends the command and its status to `run_log.jsonl` |
| `completeness_check.py` | When Claude tries to finish | In the deliverables phase, refuses to finish while planned files or charts are missing |

**Script naming** (the hooks rely on it): `10_validate_*`, `20_analysis_*`, `30_charts_*`, `40_deck_*`,
`50_report_*`, `90_adhoc_*`.

## 12. The toolkit: `abkit/`

| Module | Purpose |
|---|---|
| `state` | Run folders, the active run, the `state.json` schema; command line `python -m abkit.state ...` |
| `results` | The `results.json` schema, the standard result shape (`StatResult`), number formatting |
| `io` | Loading CSVs, aggregating to one row per unit |
| `validation` | Data checks, sample ratio mismatch test and localisation |
| `power` | Sample size, minimum detectable effect, power curves, runtime |
| `frequentist` | z-test, Welch t-test, bootstrap, Mann-Whitney, chi-square, non-inferiority, multi-arm |
| `bayesian` | Beta-binomial and normal models, probability to beat control, expected loss |
| `variance_reduction` | CUPED and regression adjustment |
| `sequential` | Group-sequential boundaries and always-valid tests |
| `ratio_metrics` | Delta method and cluster-robust tests |
| `multiple_testing` | Bonferroni, Holm, Benjamini-Hochberg |
| `segments` | Segment effects, interaction test, Simpson's paradox check |
| `time_effects` | Daily / cumulative effects, novelty trend test |
| `quasi` | Difference-in-differences, interrupted time series, synthetic control |
| `decision` | Ship / don't ship / iterate / extend rule and the run summary |
| `viz` | House style and the 15-chart catalogue |
| `deck`, `report` | The deck builder and the two report builders |
| `tracecheck` | Checks every printed number traces to `results.json` |

Every statistical function returns the same result shape (estimate, CI, p-value or probability, relative lift and CI,
sample sizes, assumptions checked, notes), so it can be stored directly in `results.json`.

## 13. Why the numbers can be trusted

1. **One source of truth.** All numbers are in `results.json`. Charts, deck and reports only read it.
2. **Receipts.** Each result records the script that produced it; scripts are kept in `code/` and can be rerun.
3. **Independent review.** The reviewer re-derives key numbers from the raw data.
4. **Automated traceability.** `python -m abkit.tracecheck <run-id>` fails if any percentage or p-value in the deck or
   reports doesn't match `results.json`.
5. **Honest wording.** Inconclusive is never called "no effect"; exploratory results are labelled; outliers are reported, not removed.
6. **Tested toolkit.** The statistics are validated against scipy / statsmodels, known answers and simulations
   (about 170 automated tests).

## 14. Useful commands

```
python -m abkit.state status                 # active run: phase, gates, plan progress, next step
python -m abkit.state list                   # all runs (* marks the active one)
python -m abkit.state switch <run-id>        # change the active run
python -m abkit.state validate               # check state.json against the schema
python -m abkit.state reset <phase>          # reopen a phase and everything after it
python -m abkit.state candidates             # functions flagged for promotion into abkit
python -m abkit.tracecheck [<run-id>]        # every printed number traces to results.json
python runs/<run>/code/<script>.py           # rerun any step
python -m pytest -q                          # run the test suite
```

Default statistical settings live in `config/stat_defaults.yaml` (alpha 0.05, two-sided, power 0.80, Holm for
secondary metrics, Benjamini-Hochberg for segments, SRM threshold p < 0.001, 1% guardrail margin). Changes for one
run are recorded as overrides in that run's `state.json`.

## 15. Extending the pipeline

| To... | Do this |
|---|---|
| Add a statistical method | If a run needed it, `/promote` moves it from the run's `code/` into abkit with tests. By hand: add a function returning a `StatResult` to the right abkit module, add a test against a known answer or a simulation, add a method page under `.claude/skills/ab-methods/references/`, and add its formula entry in `abkit/report/technical.py` (`METHOD_DOCS`) |
| Add a chart type | Add a function to `abkit/viz/charts.py` using the palette and `finalize()`, list it in `CATALOGUE` and the consulting-charts skill, add it to the viz tests |
| Change the deck or report design | `abkit/deck/builder.py`, `abkit/report/builder.py`, `abkit/report/technical.py`; the rules are in the deck-style and report-style skills |
| Change colours or fonts | `abkit/viz/style.py` (shared by charts, deck and reports) |
| Change default settings | `config/stat_defaults.yaml` |
| Change how a phase runs | `CLAUDE.md` (orchestration) and the agent's file in `.claude/agents/` |
| Add an automatic check | A Python script in `.claude/hooks/`, wired in `.claude/settings.json`, with a test in `tests/test_hooks.py` |

Run `python -m pytest -q` after any change.

## 16. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "plan_gate: blocked ..." | A script ran before its gate opened. Approve the plan / resolve validation / finish the review first |
| "completeness_check: ... deliverables are missing" | Claude tried to finish while charts, deck or reports were still missing (or still being built). Let it finish |
| "Permission denied: ...deck.pptx" (or .docx) | The file is open in PowerPoint / Word. Close it and rerun the build script |
| The run stops at validation | A blocking data problem (often a traffic split mismatch). Read `data_profile.md` and choose an option |
| Garbled minus signs in the console | abkit switches console output to UTF-8 automatically; update if you see this |
| A slide or report says "To agree" for an owner | The next steps had no owner; write them as "Owner: action (timing)" |

## 17. Glossary

| Term | Meaning |
|---|---|
| A/B test | Randomly splitting users into groups that see different versions, then comparing outcomes |
| Control / treatment | The existing version / the new version |
| Lift | How much higher the treatment's metric is than the control's, usually as a % |
| Confidence interval (CI) | The range of effects compatible with the data |
| p-value | How surprising the difference would be if the change did nothing; below 0.05 is usually called significant |
| Practical threshold (MDE) | The smallest effect worth acting on; significance alone isn't enough |
| Sample ratio mismatch (SRM) | Group sizes don't match the planned split: a sign of broken assignment or logging |
| Guardrail | A metric that must not get worse (e.g. revenue, errors) |
| Bayesian P(beat) | The probability, given the data, that the treatment is truly better |
| CUPED | Using pre-experiment data to make estimates more precise |
| Exploratory | A pattern worth investigating, not proof |
| Gate | An approval checkpoint the pipeline cannot pass without |
| Hook | An automatic check that runs on every action |
| Run | One experiment's analysis, in its own folder under `runs/` |
