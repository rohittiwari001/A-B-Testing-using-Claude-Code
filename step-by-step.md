# Pipeline flow in depth: from problem statement to deliverables

What happens, step by step, when you give the pipeline a problem statement and a CSV. The marketing-ads run
(`runs/2026-10-01_marketing-ads/`) is used as the example throughout. For a shorter overview, see
[HOW_IT_WORKS.md](HOW_IT_WORKS.md).

---

## Phase 0: Kick-off

**You type:**
```
Here is my data @data/checkout.csv, described in @data/checkout.md. Should we ship the new checkout?
```
Or use the shortcut `/new-experiment data/checkout.csv`.

**What the pipeline does:**
1. If either the CSV or the description is missing, it asks for both in one message.
2. It creates the run with `python -m abkit.state new <slug> --csv ... --context-file ...`. This:
   - creates `runs/2026-10-10_checkout/`;
   - **copies** your CSV into `runs/<id>/data/`. Your original is never touched, and editing the copy is denied in
     `.claude/settings.json`;
   - saves your description word for word as `context.md`;
   - creates `state.json` with phase `intake`, all gates closed, and default settings;
   - points `runs/.active` at the new run, which every agent and hook reads.

---

## Phase 1: Intake (done in the main session, using the `experiment-intake` skill)

1. It reads `context.md` and the CSV header plus 10 rows, so it never asks something the data already shows
   (column names, variant labels, dates).
2. It goes through the question bank in `.claude/skills/experiment-intake/question_bank.md` (business question,
   decision, variants and split, randomisation unit, dates, pre-period data, primary metric, guardrails, smallest
   worthwhile lift, segments, incidents, peeking). Each topic gets marked as one of:
   - **answered**: covered by your description or the data;
   - **inferable**: it states its assumption and asks you to confirm;
   - **unknown**: it asks.
3. It sends **one batch** of numbered questions, each with a suggested default in brackets, plus the **statistical
   defaults table** (alpha 0.05, two-sided, power 0.80, Holm/BH corrections, SRM p < 0.001, and so on) with
   "keep or change?".
4. **You reply.** Something like "all defaults except 3: use 2%" is fine.
5. It writes `intake.md`: business question, decision, hypothesis, design, metrics table, segments, incidents,
   settings, and risks flagged at intake. It also updates `state.json`: metrics (role, type, direction, practical
   threshold), any setting overrides (recorded separately under `overrides`), the title, and phase -> `planning`.

Anything risky you say here, such as "we checked results daily and stopped early", is written under **Risks
flagged at intake**. The planner and reviewer both read it.

---

## Phase 2: Planning (`experiment-planner` agent)

The planner designs the analysis but doesn't run anything.

1. It reads `state.json`, `context.md`, `intake.md`, the first CSV lines, the chart catalogue, the deck style
   rules, and the method page for every method it considers.
2. It **classifies the problem** into one or more types: `post_test_readout`, `power_analysis`,
   `srm_investigation`, `bayesian_readout`, `cuped_reanalysis`, `sequential_monitoring`, `heterogeneous_effects`,
   `multi_arm`, `ratio_metric`, `novelty_check`, `guardrail_check`, `quasi_experiment`.
3. It works through these questions explicitly:
   - Are the metric rows (sessions, orders) finer than the unit that was randomised (users)? Then it plans the
     delta method, never a row-level test.
   - Is there pre-period data? Then CUPED.
   - Visible UI change? Then a novelty check. Peeking? Then sequential methods. Heavy-tailed revenue? Then
     bootstrap.
   - More than 2 arms? Then Holm or Dunnett. Several metrics or segments? Then correction families.
4. It writes the plan steps. They always start with `validate` and `srm` and end with `summary`. Each step names
   an abkit function and has a one-line "why". If abkit lacks a method, the step is named `custom.<name>` and the
   analyst must write it.
5. It picks charts (from the 15-chart catalogue), the order of findings in the deck, the report sections, and the
   standard deliverables.
6. It writes `plan.md` plus the plan in `state.json`, with `plan_approved` left **false**.

**Gate 1 (yours):** You see the plan summary and reply **"approved"** or ask for changes. The gate opens with
`python -m abkit.state gate plan_approved true`. Before this, the `plan_gate` hook **blocks any `20_`-`50_`
script from running**, so no number can be computed before you approve.

---

## Phase 3: Validation (`data-validator` agent)

1. It writes and runs `code/10_validate_profile.py`, which calls `abkit.validation.full_profile` and checks about
   a dozen things:
   - schema, data types, missing values, duplicate units;
   - contamination (units appearing in both groups);
   - date coverage and full weeks;
   - **SRM**: variant counts against the intended split (chi-square);
   - outliers, impossible values (e.g. negative revenue), pre-period availability, covariate balance.
2. It writes `data_profile.md` with a "What this means for the analysis" section, and stores the profile in
   `results.json -> validation`.
3. If needed, `code/11_validate_srm.py` breaks the SRM down by day and by segment to locate it.
4. The verdict is one of:
   - **PASS / WARN** -> the gate opens and the phase moves to analysis;
   - **BLOCK** -> the gate stays closed and it **stops**, giving you the likely causes and 2-3 options (re-extract
     the data, restrict to a clean window as a labelled sensitivity analysis, rerun the test).

Outliers are reported but never removed.

**Gate 2:** This opens automatically on a pass. On a block you decide. In the marketing run, the 95/5 split failed
SRM (p = 3e-271). The user corrected it to 96/4, the check was rerun, and it passed.

---

## Phase 4: Analysis (`stats-analyst` agent)

The analyst runs the plan exactly as written and doesn't redesign it.

1. It confirms both gates are open.
2. For each plan step in order, it writes `code/20_analysis_<step>.py`, which:
   - loads the run's CSV copy and settings from `state.json` (alpha, sidedness, corrections);
   - calls the abkit function, which returns a standard `StatResult`: estimate, absolute and relative lift, CI,
     p-value or posterior, n per variant, assumptions checked, correction;
   - stores it with `results.add_result(RUN, step, result, __file__, data={chart tables})`. The script path is
     saved as the "receipt";
   - marks the step done.
3. It applies the planned multiple-testing corrections per family, and any exclusions (e.g. contaminated users)
   in code, with the counts noted.
4. If a method is missing, it writes it in the run's script, validates it (by simulation or a known answer), and
   flags it for `/promote` into abkit.
5. If an assumption breaks badly, it **stops**, marks the step failed, and proposes an alternative instead of
   changing the plan itself.
6. The final step, `20_analysis_summary.py`, calls `abkit.decision.build_summary`. This produces:
   - a verdict (**Ship / Don't ship / Iterate / Extend**) from a fixed rule: is the result significant, and does
     the CI clear your practical threshold, given the guardrails;
   - a headline, key numbers, caveats (most important first), next steps written as "Owner: action (timing)",
     impact tiles, and a so-what sentence.

   Every number in this text is formatted from the stored results, never typed by hand. The phase then moves to
   `review`.

---

## Phase 5: Review (`stats-reviewer` agent)

The reviewer is independent. It sees **only the files**, not the analyst's reasoning, and its shell access is
read-only.

1. It reads everything: state, plan, intake, data profile, results, every script in `code/`, and any previous
   review.
2. It goes through a **13-item checklist**: SRM against the intended split, test matches metric type, unit of
   analysis, corrections, practical vs statistical significance, "inconclusive" wording (never "no effect"),
   peeking, novelty, Simpson's paradox, guardrails, whether the verdict follows from the numbers (it re-derives it
   with `decision.recommend`), traceability (it **recomputes key numbers from the raw CSV**), and failed
   assumptions.
3. It writes `review.md`, with each finding graded:
   - **blocker**: could change the recommendation, so **you decide**;
   - **fix**: goes back to the analyst, for **at most 2 rounds**;
   - **note**: added to the caveats.

**Gate 3:** This opens only when there are no blockers and no fixes left. The marketing run needed 2 rounds: 5
fixes, all leftover 95/5 wording, then a pass. Deck and report scripts (`40_`, `50_`) are blocked by the hook until
this gate opens.

---

## Phase 6: Deliverables (three agents, in order)

| Agent | Script | Output |
|---|---|---|
| `viz-designer` | `30_charts_*.py` | Each planned chart as PNG (300 dpi) and SVG, with action titles ("Ads raise conversion 43%", not "Conversion by group"), the house palette, and `charts/manifest.json` (title, key message, takeaway, deck section) |
| `deck-builder` | `40_deck_build.py` | `deck.pptx` with a fixed storyline: Title -> Exec summary (answer first) -> Agenda -> The ask -> Approach -> **Findings** (the only part that changes per problem) -> Impact -> Risks and recommendation -> Appendix. Speaker notes on every slide, plus `deck_storyline.md` (titles alone should tell the story) |
| `report-writer` | `50_report_build.py`, `50_technical_report.py` | `summary.docx` (verdict on page 1, plain language) and `technical_report.docx` (hypotheses, formulas, assumptions, robustness, decision log, commands to reproduce) |

Hooks check this phase automatically:
- `style_guard`: chart code must use the house style and palette.
- `numbers_guard`: deck and report code can't contain hand-typed result numbers.
- `run_logger`: every command is logged to `run_log.jsonl`.

---

## Phase 7: Wrap-up

1. The `completeness_check` hook **refuses to let the session finish** while any planned chart, deck or report is
   missing.
2. `python -m abkit.tracecheck <run>` fails if any percentage or p-value in the deck or reports doesn't match
   `results.json`.
3. You get a short chat summary: verdict, key numbers, caveats, and file paths.

---

## After that

Ask in plain English, for example "split by platform", "rerun with alpha 0.01" or "add revenue as a guardrail".
The same run is updated and only the affected phases rerun (`/rerun analysis`, and so on). You can also use
`/status` and `/switch-run`.

## Where you're interrupted

| When | Why |
|---|---|
| Intake | One batch of questions |
| Plan | Approval (needed every time) |
| Validation | Only if a blocking data problem is found |
| Review | Only if a finding could change the recommendation |
