# Build Prompt: Dynamic A/B Testing Workflow for Claude Code

## 0. Your role and how to work

You are building a Claude Code project repository that turns Claude Code into an expert product data scientist for experimentation (A/B testing). You are building the *workflow itself*: agents, skills, hooks, orchestration instructions, a reusable Python toolkit, tests, and demo data. You are not analysing a real experiment right now.

Before writing any files:

1. Read this entire document.
2. Check the current Claude Code documentation for the exact file formats of subagents (`.claude/agents/*.md`), skills (`.claude/skills/<name>/SKILL.md`), slash commands (`.claude/commands/*.md`), and hooks (`.claude/settings.json`, hook events, stdin JSON payload, exit codes). Use the current formats even where this document's examples differ.
3. Reply with a short build plan (milestones from Section 12) and any questions. Wait for my approval before building.

While building:

- Work milestone by milestone. After each milestone, run the relevant tests, show me a short summary, and make a git commit.
- Keep things simple and readable. Prefer a small number of well-written files over many thin ones.
- If something in this document is technically impossible in Claude Code, tell me and propose the closest alternative. Do not silently skip it.

---

## 1. What the finished workflow must do

I am an individual product data scientist. In future sessions I will open this repo in Claude Code, provide a CSV plus a plain-English description of the data and the problem, and the workflow must:

1. **Ask before deciding.** Run a clarifying Q&A with me about the problem, data, metrics, and statistical settings before choosing an approach.
2. **Plan dynamically.** The path through the analysis depends entirely on the problem statement. A power analysis, a post-experiment readout, an SRM investigation, a Bayesian readout, a CUPED re-analysis, a sequential monitoring check, and a heterogeneous-effects deep dive all need different steps. The workflow must assemble the right steps each time from reusable parts, not follow one fixed pipeline.
3. **Follow rigorous, in-depth A/B testing methodology**, including validation, assumption checks, and interpretation pitfalls.
4. **Produce three deliverables every run**, sized to the problem:
   - Consulting-style (McKinsey-like) charts with consistent fonts and colours.
   - A well-styled PowerPoint deck.
   - A Word document summarising the problem, method, results, and recommendation.
5. **Handle ad-hoc follow-ups.** If I later ask "now split by platform" or "rerun with alpha 0.01", it updates the same run.
6. **Grow over time.** New methods or helper functions written during a run can be promoted into the reusable toolkit.

### Fixed facts about my setup

- Data is always CSV, stored locally, and small enough to fit in memory with pandas.
- I will always describe the data's columns and context in chat (the workflow should save this as `context.md` in the run folder).
- Language: Python only (pandas, numpy, scipy, statsmodels, matplotlib, python-pptx, python-docx, pyyaml, pytest). No R. Add other libraries only if clearly justified, and tell me.
- Every experiment has its own metrics. There is no fixed metric catalogue.
- I have no brand guidelines. The workflow defines its own consulting-style visual system (Section 7).
- Interaction is plain English. Slash commands are optional shortcuts only.
- No PII or compliance constraints.

---

## 2. Repository structure

Build this structure. Adjust only if Claude Code's current conventions require it.

```
ab-workflow/
├── CLAUDE.md                        # Orchestration rules (Section 3)
├── README.md                        # How to use the workflow, for me
├── requirements.txt
├── pyproject.toml                   # So abkit is importable (pip install -e .)
├── config/
│   └── stat_defaults.yaml           # Standard statistical settings (Section 8)
├── .claude/
│   ├── settings.json                # Hook wiring + permissions
│   ├── agents/                      # 7 reusable subagents (Section 5)
│   ├── skills/                      # Knowledge skills (Section 6)
│   ├── hooks/                       # Hook scripts in Python (Section 9)
│   └── commands/                    # Optional shortcuts (Section 10)
├── abkit/                           # Reusable Python toolkit (Section 11)
│   ├── __init__.py
│   ├── io.py
│   ├── validation.py
│   ├── power.py
│   ├── frequentist.py
│   ├── bayesian.py
│   ├── variance_reduction.py
│   ├── sequential.py
│   ├── ratio_metrics.py
│   ├── multiple_testing.py
│   ├── segments.py
│   ├── time_effects.py
│   ├── quasi.py
│   ├── results.py                   # results.json schema + read/write helpers
│   ├── viz/
│   │   ├── __init__.py
│   │   ├── style.py                 # apply_style(), palette, fonts
│   │   ├── consulting.mplstyle
│   │   └── charts.py                # Standard chart functions
│   ├── deck/
│   │   ├── __init__.py
│   │   └── builder.py               # python-pptx deck builder
│   ├── report/
│   │   ├── __init__.py
│   │   └── builder.py               # python-docx report builder
│   └── state.py                     # Run state read/write helpers
├── tests/                           # pytest suite
├── demo_data/                       # Synthetic CSVs + context files (Section 12)
│   └── generate.py
└── runs/                            # One folder per experiment run
    └── .gitkeep
```

### Run folder layout (created by the workflow for each run)

```
runs/<YYYY-MM-DD>_<short-slug>/
├── context.md          # My description of data + problem, as given in chat
├── intake.md           # Q&A transcript summary: decisions and settings agreed
├── plan.md             # Human-readable approved plan
├── state.json          # Machine-readable run state (drives the hooks)
├── data/               # Copy of the input CSV (never modify the original)
├── data_profile.md     # Validation findings
├── code/               # Every script executed, numbered by phase
├── results.json        # Single source of truth for all numbers
├── review.md           # Reviewer's findings and how they were resolved
├── charts/             # PNG (300 dpi) + SVG
├── deck.pptx
├── summary.docx
└── run_log.jsonl       # Written by the logging hook
```

The active run's id is stored in `runs/.active` (one line). Hooks and agents use it to locate the current run.

---

## 3. CLAUDE.md: orchestration rules

The main Claude Code session is the orchestrator. Subagents cannot spawn other subagents, so the main session calls each agent in turn based on the plan. Write `CLAUDE.md` so that the main session reliably follows these phases:

### Phase 1: Intake (always)

- Triggered when I describe an experiment problem or provide a CSV, in plain English.
- Create the run folder, write `runs/.active`, copy the CSV into `data/`, and save my description as `context.md`.
- Load the `experiment-intake` skill and ask only the questions that my description has not already answered. Ask in one or two batches, not one at a time.
- Always show the standard statistical defaults from `config/stat_defaults.yaml` in a compact table and ask whether to keep or change them for this run.
- Save the agreed answers to `intake.md` and update `state.json`.

### Phase 2: Planning (always)

- Call the `experiment-planner` agent.
- The planner classifies the problem, selects methods from the `ab-methods` skill, and writes both `plan.md` and the plan section of `state.json` (Section 4).
- Show me the plan summary. I must approve it or request edits. Set `plan_approved: true` only after my explicit approval.

### Phase 3: Data validation (always)

- Call the `data-validator` agent. Results go to `data_profile.md` and `state.json`.
- If a blocking issue is found (for example SRM with p < threshold, a missing variant column, or an empty variant), stop and explain it to me with options. Do not continue analysis on broken data without my decision.

### Phase 4: Analysis (as planned)

- Call the `stats-analyst` agent to execute only the planned methods, in order. All numbers go to `results.json`.

### Phase 5: Review (always)

- Call the `stats-reviewer` agent. It writes `review.md`.
- If it raises issues that are fixable without changing the conclusion, send them back to the analyst automatically (maximum two loops).
- If an issue could change the conclusion or recommendation, stop and ask me.

### Phase 6: Deliverables (always)

- Call `viz-designer`, then `deck-builder` and `report-writer`.
- Deck and report length scale with the problem (a power analysis gets a short deck; a full multi-metric readout gets a longer one plus appendix).

### Phase 7: Wrap-up (always)

- Confirm every deliverable listed in the plan exists.
- Give me a short chat summary: the verdict, three to five key numbers, caveats, and file paths.

### Follow-ups and general rules

- If I ask a follow-up about the active run, update the plan (with my approval if the method changes), rerun only the affected phases, and regenerate affected deliverables.
- If I ask a general A/B testing question with no data, answer directly using the `ab-methods` skill. Do not start a run.
- Never invent data or numbers. Every number in charts, deck, and report must come from `results.json`.
- Never modify the original CSV.
- Prefer existing `abkit` functions. If a planned method is missing from `abkit`, the analyst writes it inside the run's `code/` folder and flags it in `results.json` as a candidate for promotion. At wrap-up, ask me whether to promote it into `abkit` with tests.

---

## 4. state.json schema

Define and validate this schema in `abkit/state.py`. Hooks depend on it.

```json
{
  "run_id": "2026-10-01_checkout-button",
  "created_at": "ISO-8601",
  "phase": "intake | planning | validation | analysis | review | deliverables | done",
  "problem_type": ["post_test_readout", "power_analysis", "..."],
  "settings": {
    "alpha": 0.05,
    "sidedness": "two-sided",
    "power": 0.8,
    "correction_primary": "none",
    "correction_secondary": "holm",
    "correction_segments": "benjamini-hochberg",
    "srm_threshold": 0.001
  },
  "metrics": [
    {"name": "conversion", "role": "primary", "type": "binary", "direction": "increase"},
    {"name": "revenue_per_user", "role": "guardrail", "type": "continuous", "direction": "no_decrease"}
  ],
  "plan": {
    "steps": [
      {"id": "validate", "method": "validation.full_profile", "status": "pending"},
      {"id": "srm", "method": "validation.srm_check", "status": "pending"},
      {"id": "primary_test", "method": "frequentist.two_proportion_ztest", "status": "pending"}
    ],
    "charts": ["lift_ci", "cumulative_daily", "segment_forest"],
    "deck_sections": ["exec_summary", "setup", "results", "guardrails", "risks", "next_steps", "appendix"],
    "report_sections": ["..."],
    "deliverables": ["charts/", "deck.pptx", "summary.docx"]
  },
  "gates": {
    "plan_approved": false,
    "validation_passed": false,
    "review_passed": false
  }
}
```

---

## 5. Subagents (.claude/agents/)

Create one file per agent with a clear `description` so the orchestrator knows when to use it, a minimal `tools` list, and a detailed system prompt. Each agent must read `runs/.active` and `state.json` first, and must write its outputs to the run folder, not just reply in chat.

### 5.1 experiment-planner
- **Purpose:** Turn `context.md` + `intake.md` into a concrete plan.
- **Must:** Classify the problem type (one or more), pick methods from `ab-methods` with a one-line justification each, choose charts from the chart catalogue (Section 7), choose deck and report sections, and list assumptions to check.
- **Must consider:** randomisation unit vs analysis unit (flag when a ratio metric or cluster effect needs the delta method or clustered errors), metric types, pre-period data availability (for CUPED), test duration and weekly cycles, number of variants, and number of metrics and segments (for multiple-testing correction).
- **Outputs:** `plan.md`, plan section of `state.json`.
- **Tools:** Read, Write, Glob.

### 5.2 data-validator
- **Purpose:** Profile and sanity-check the CSV against `context.md`.
- **Checks:** schema matches description; dtypes; missing values; duplicate units; units appearing in more than one variant (contamination); date range and daily coverage; variant counts and SRM (chi-square against the intended split); outliers in continuous metrics (report, do not auto-remove); pre-period availability; metric value ranges that are impossible (for example negative revenue, conversion > 1 at user level).
- **Outputs:** `data_profile.md` with a pass / warn / block verdict per check, validation section of `results.json`, `gates.validation_passed` in `state.json`.
- **Tools:** Read, Write, Bash.

### 5.3 stats-analyst
- **Purpose:** Execute the planned methods exactly, using `abkit` first.
- **Must:** write each step as a numbered script in `code/` (Section 9 naming), run it, and write results to `results.json` via `abkit.results`. For every test, record: estimate, absolute and relative lift, CI, p-value or posterior probability, test used, assumptions checked, sample sizes, and any correction applied.
- **Must not:** change the plan on its own. If a planned method turns out inappropriate (for example assumptions badly violated), stop and report back to the orchestrator with a proposed alternative.
- **Tools:** Read, Write, Edit, Bash.

### 5.4 stats-reviewer
- **Purpose:** Independent skeptic. It has not seen the analyst's reasoning, only files.
- **Checklist:** SRM handled; correct test for metric type; correct unit of analysis; multiple-testing correction applied as planned; practical vs statistical significance (compare lift to MDE); underpowered null results described correctly ("inconclusive", not "no effect"); peeking or early stopping without sequential correction; novelty or primacy effects visible in time trends; Simpson's paradox across segments; guardrail breaches; conclusion actually follows from the numbers; every number in `results.json` traceable to a script in `code/`.
- **Outputs:** `review.md` with each finding labelled `blocker`, `fix`, or `note`; `gates.review_passed`.
- **Tools:** Read, Glob, Grep, Bash (read-only checks only).

### 5.5 viz-designer
- **Purpose:** Produce all planned charts using `abkit.viz` and the `consulting-charts` skill.
- **Must:** use `apply_style()` in every plotting script, write action titles that state the takeaway, save PNG (300 dpi) and SVG to `charts/`, and write a `charts/manifest.json` listing each chart with its title, subtitle, and the key message.
- **Tools:** Read, Write, Edit, Bash.

### 5.6 deck-builder
- **Purpose:** Build `deck.pptx` using `abkit.deck` and the `deck-style` skill.
- **Must:** open with the verdict, pull every number from `results.json`, use charts from `charts/manifest.json`, and include speaker notes explaining each slide's key point.
- **Tools:** Read, Write, Edit, Bash.

### 5.7 report-writer
- **Purpose:** Build `summary.docx` using `abkit.report` and the `report-style` skill.
- **Must:** be readable by a non-statistician in the first page and complete for a data scientist overall; pull every number from `results.json`.
- **Tools:** Read, Write, Edit, Bash.

---

## 6. Skills (.claude/skills/)

Each skill is a folder with a `SKILL.md` (frontmatter with a precise `description` so it triggers correctly) and supporting reference files that load only when needed.

### 6.1 experiment-intake
A question bank grouped by topic, with guidance to ask only what is unknown. Topics: business question and decision to be made; hypothesis; variants and intended traffic split; randomisation unit; analysis unit; test start and end dates; metrics with role (primary / secondary / guardrail), type (binary / continuous / count / ratio), and desired direction; pre-period data; segments of interest; known incidents during the test; stat settings (show defaults, ask keep or change); desired depth of deck.

### 6.2 ab-methods (the core library)
`SKILL.md` is an index that maps problem types and metric types to methods. One reference file per concept, each with the same sections: **When to use**, **Assumptions**, **Step-by-step procedure**, **abkit function(s)**, **How to interpret**, **Common pitfalls**, **How to present it** (chart and one-sentence wording).

Required files:
1. `power_and_mde.md`: sample size, MDE, runtime estimation, power curves, variance from historical data.
2. `frequentist_tests.md`: two-proportion z-test, Welch's t-test, Mann-Whitney, chi-square, bootstrap CIs; choosing by metric type and distribution.
3. `bayesian.md`: beta-binomial for conversion, normal models for continuous metrics, probability to beat control, expected loss, credible intervals, prior choice.
4. `srm.md`: chi-square test, likely causes, what to do when it fails.
5. `cuped.md`: CUPED and regression adjustment with pre-period covariates, variance-reduction reporting.
6. `sequential_testing.md`: peeking problem, alpha spending (O'Brien-Fleming, Pocock), always-valid inference (mSPRT) at a conceptual level with a practical implementation.
7. `ratio_metrics_delta_method.md`: when analysis unit differs from randomisation unit; delta method and clustered errors.
8. `multiple_testing.md`: Bonferroni, Holm, Benjamini-Hochberg; when to use each.
9. `multi_arm.md`: multiple variants, comparisons against control, Dunnett-style thinking, correction.
10. `heterogeneous_effects.md`: pre-specified segments, interaction tests, forest plots, Simpson's paradox, and warnings about post-hoc fishing.
11. `novelty_primacy.md`: daily lift trends, cohort-by-exposure-day analysis.
12. `guardrails.md`: non-inferiority tests and margins.
13. `quasi_experiments.md`: difference-in-differences, synthetic control (basic), interrupted time series, and when randomisation was not possible.
14. `interpretation_and_decisions.md`: ship / don't ship / iterate / extend logic, practical significance, communicating inconclusive results.

### 6.3 consulting-charts
The full visual system from Section 7, the chart catalogue, action-title rules with good and bad examples, and a pre-save checklist.

### 6.4 deck-style
Deck structure, slide types, layout rules, and wording rules from Section 7.3.

### 6.5 report-style
Report structure and writing rules from Section 7.4.

### 6.6 stat-defaults
Explains `config/stat_defaults.yaml`, when deviating is reasonable, and how to record overrides in `state.json`.

---

## 7. Visual and document style system

### 7.1 Palette and typography

Define these once in `abkit/viz/style.py` and reuse in charts, deck, and report.

| Token | Hex | Use |
|---|---|---|
| ink | `#1A1A1A` | Titles, primary text |
| navy | `#0B2545` | Control / baseline series, headers |
| accent | `#2251FF` | The one thing to look at (treatment, key bar) |
| accent_light | `#9DB4FF` | Secondary treatment arms |
| grey_mid | `#8C8C8C` | Context series, axis labels, notes |
| grey_light | `#E3E3E3` | Gridlines, dividers, CI bands |
| positive | `#1B7F5A` | Significant positive result |
| negative | `#C0392B` | Significant negative result / guardrail breach |
| neutral | `#B08900` | Inconclusive |

- Font: Arial throughout, with fallback `Helvetica, Liberation Sans, DejaVu Sans` for charts.
- Chart sizes: title 14 pt bold, subtitle 11 pt grey_mid, axis labels 10 pt, annotations 10 pt, source note 8 pt.

### 7.2 Chart rules and catalogue

Rules:
- Every chart has an **action title** stating the takeaway (for example "Variant B lifts checkout conversion by 3.2%, statistically significant"), a subtitle with the metric and units, and a source/notes line (data file, dates, test used, n).
- Mostly greys; only the key element uses accent. Maximum four colours per chart.
- No chart borders, no top/right spines, light horizontal gridlines only, no 3-D, no pie charts.
- Direct labels on bars and line ends instead of legends where possible.
- Confidence intervals always shown for estimates.
- Consistent variant colour mapping across all charts in a run.

Catalogue (implement each in `abkit/viz/charts.py`):
`lift_ci` (dot-and-whisker of relative lift with CI, zero line), `metric_by_variant` (bar with CI), `cumulative_daily` (cumulative metric per variant over time), `daily_lift` (daily lift with CI band, novelty check), `segment_forest` (forest plot of lift by segment), `power_curve`, `sample_size_vs_mde`, `posterior_distributions`, `prob_to_beat_control`, `srm_bar` (observed vs expected split), `distribution_compare` (histogram/ECDF by variant), `cuped_variance_reduction`, `sequential_boundaries`, `guardrail_scorecard` (table-like chart with pass/fail colours), `did_trends` (treated vs control over time with intervention line).

### 7.3 Deck (python-pptx)

- 16:9. Build the template programmatically in `abkit/deck/builder.py` (no external template file needed).
- Every slide: action title (max two lines), content, footer with source note and slide number.
- Slide types: title, executive summary (verdict box coloured positive/negative/neutral + three to five key bullets with numbers), section divider, chart + takeaways (chart ~65% width, three takeaways on the right), two charts side by side, table, methodology, risks and caveats, next steps, appendix.
- Default section order: title → executive summary → experiment setup → results (primary) → secondary and guardrails → segments (if planned) → risks and caveats → recommendation and next steps → appendix (methodology, validation, full tables).
- Text: max about 40 words of body text per slide; numbers formatted consistently (percentages to one decimal, p-values to three decimals or "<0.001").
- Speaker notes on every content slide.

### 7.4 Report (python-docx)

Sections: executive summary (half page, verdict first) → business question and hypothesis → experiment design → data and validation → methodology → results (with embedded charts and tables) → guardrails → segments → risks, limitations, and assumptions → recommendation and next steps → appendix (settings, reviewer findings, code index). Use the same fonts and colours as the deck, heading styles from the document's built-in styles, and captions on every chart and table.

---

## 8. config/stat_defaults.yaml

```yaml
alpha: 0.05
sidedness: two-sided
power: 0.80
confidence_level: 0.95
correction:
  primary: none          # single pre-registered primary metric
  secondary: holm
  segments: benjamini-hochberg
srm:
  test: chi-square
  threshold: 0.001
duration:
  min_days: 7
  prefer_full_weeks: true
bayesian:
  prior: weakly_informative
  decision_threshold_prob_beat: 0.95
bootstrap:
  n_resamples: 10000
  seed: 42
guardrails:
  default_noninferiority_margin_relative: 0.01
```

Every run shows these at intake and records any overrides in `state.json.settings`.

---

## 9. Hooks (.claude/hooks/, wired in .claude/settings.json)

Write hooks in Python, reading the hook JSON payload from stdin. Use `$CLAUDE_PROJECT_DIR` for paths. Hooks are deterministic; they become "dynamic" by reading the active run's `state.json`. If there is no active run, every hook must exit 0 silently. Every hook must be fast (under a second or two) and must never crash the session; on internal error, log to stderr and exit 0.

### Script naming convention (hooks rely on it)
Scripts in `runs/<id>/code/` are prefixed by phase: `10_validate_*.py`, `20_analysis_*.py`, `30_charts_*.py`, `40_deck_*.py`, `50_report_*.py`, `90_adhoc_*.py`.

### 9.1 session_start.py (SessionStart)
Prints a short status of the active run (id, phase, gates, next step) so the session resumes with context.

### 9.2 plan_gate.py (PreToolUse, matcher: Bash)
If the command runs a script with prefix `20_`–`50_` and `plan_approved` or `validation_passed` is false, block (exit code 2) with a clear stderr message telling Claude which gate is missing and what to do. If the command runs `40_` or `50_` and `review_passed` is false, block likewise.

### 9.3 style_guard.py (PostToolUse, matcher: Write|Edit)
If a `.py` file under `runs/*/code/` or `abkit/viz/` imports matplotlib and does not call `abkit.viz.apply_style()` (or use `consulting.mplstyle`), or hard-codes hex colours not in the palette, return feedback (exit code 2) asking Claude to fix it.

### 9.4 run_logger.py (PostToolUse, matcher: Bash)
Append a JSON line to `runs/<id>/run_log.jsonl`: timestamp, command, and exit status if available.

### 9.5 numbers_guard.py (PostToolUse, matcher: Write|Edit)
If a `40_` or `50_` script contains hard-coded numeric results (for example literal lift or p-value values in text strings) instead of reading from `results.json`, return feedback asking Claude to source numbers from `results.json`. Keep the heuristic simple and avoid false positives on layout numbers (sizes, positions, font sizes).

### 9.6 completeness_check.py (Stop)
If the active run's phase is `deliverables` or `done`, check that every item in `plan.deliverables` exists and that `charts/manifest.json` lists every planned chart. If anything is missing, block stopping (exit code 2) with a message listing what is missing. Respect the `stop_hook_active` field in the payload to avoid infinite loops.

Write unit tests for every hook using sample payloads.

---

## 10. Optional slash commands (.claude/commands/)

Plain English is the main interface; these are shortcuts only:
- `/new-experiment` starts intake for a new run.
- `/status` shows the active run's phase, gates, and plan progress.
- `/switch-run <run-id>` changes the active run.
- `/rerun <phase>` reruns a phase and everything downstream.
- `/promote` lists candidate functions from runs and helps promote them into `abkit` with tests.

---

## 11. abkit: the reusable toolkit

- Pure functions where possible, type hints, docstrings with a short example, and clear errors for bad input.
- Each statistical function returns a small dataclass or dict with a consistent shape (estimate, ci_low, ci_high, p_value or probability, method, n per variant, notes), so `abkit.results` can store it directly.
- Cover at minimum: everything referenced in the `ab-methods` reference files (Section 6.2).
- Validate statistical functions against known results: compare to statsmodels/scipy outputs, closed-form answers, or simulation (for example, A/A simulations should reject at about alpha; power simulations should match analytic power within tolerance).
- `abkit.results` defines the `results.json` schema and helpers to add and read entries by step id.
- `abkit.viz`, `abkit.deck`, and `abkit.report` read from `results.json` and `charts/manifest.json`.

---

## 12. Demo data, testing, and milestones

### Demo data (`demo_data/generate.py`)
Generate synthetic CSVs with known ground truth, each with a matching `*_context.md` written the way I would describe it:
1. `checkout_ab.csv`: user-level, binary conversion + revenue, two variants, 14 days, true lift about +3%, with platform and country segments.
2. `pricing_multiarm.csv`: three variants, continuous revenue, heavy-tailed.
3. `srm_broken.csv`: SRM present (should be blocked at validation).
4. `cuped_engagement.csv`: with pre-period metric strongly correlated with outcome.
5. `novelty_feature.csv`: treatment effect that decays over time.
6. `sessions_ratio.csv`: session-level rows, user-level randomisation (needs delta method).
7. `geo_rollout.csv`: non-randomised regional launch (needs diff-in-diff).

### Tests
- Unit tests for `abkit` (statistics, validation, results schema, style tokens).
- Hook tests with sample payloads.
- Smoke tests that build a deck and report from a sample `results.json` and check that the files open and contain the expected slide and section counts.

### Milestones (commit after each)
1. Repo skeleton, `requirements.txt`, `pyproject.toml`, `abkit/state.py`, `abkit/results.py`, stat defaults, demo data generator.
2. `abkit` statistics modules + tests.
3. `abkit.viz` (style + chart catalogue) + a gallery script that renders every chart from demo data into `docs/chart_gallery/` for my visual review.
4. `abkit.deck` and `abkit.report` + smoke tests. Render a sample deck and report for my review.
5. Skills (all of Section 6).
6. Agents (all of Section 5).
7. Hooks + `settings.json` + hook tests.
8. `CLAUDE.md`, slash commands, and `README.md`.
9. End-to-end dry runs: walk through the full workflow on `checkout_ab.csv`, `srm_broken.csv`, and `cuped_engagement.csv` as if I were the user, show me the Q&A you would ask, and produce all deliverables. Report what worked, what felt clumsy, and what you would improve.

### Acceptance criteria
- Starting from plain English plus a CSV, the workflow asks sensible clarifying questions, proposes a plan that differs appropriately by problem type, and waits for approval.
- The SRM demo is blocked at validation with a clear explanation.
- Charts from different runs look like they came from the same team: same fonts, palette, title style, and layout.
- Deck and report numbers match `results.json` exactly.
- Hooks block out-of-order execution and missing deliverables, and stay silent when no run is active.
- All tests pass.
- `README.md` explains, in under a page, how I start a new experiment, resume one, ask follow-ups, and add a new method.