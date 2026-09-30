# Milestone 9: end-to-end dry runs

Three runs were walked through the full workflow, with me playing the user. The orchestrator followed `CLAUDE.md`
and each agent role followed its `.claude/agents/*.md` prompt. The agent roles were executed in the main session
rather than spawned as subagents, to keep the dry run cheap; every file they are specified to write was produced.
The project hooks were **live** during the runs, and they blocked, logged and checked real tool calls.

| Run | Data | Outcome | Deliverables |
|---|---|---|---|
| `2026-10-01_checkout-button` | checkout_ab.csv | **Ship** (+3.2% conversion, 99% CI [+0.6%, +5.8%] after an alpha 0.01 follow-up) | 8 charts, 18-slide deck, 11-section report |
| `2026-10-01_onboarding-checklist` | srm_broken.csv | **Blocked at validation** (SRM p < 0.001, Android from 5 Sep) -> blocked readout | 2 charts, 6-slide deck, 6-section report |
| `2026-10-01_home-feed-redesign` | cuped_engagement.csv | **Ship** on CUPED (+1.7%, p = 0.042; unadjusted p = 0.081), after a reviewer blocker the user resolved | 4 charts, 13-slide deck, 9-section report |

`python -m abkit.tracecheck` confirms every percentage and p-value in all three decks and reports traces to
`results.json`.

---

## Run 1: checkout (post-test readout + guardrail + segments + novelty)

**Q&A asked (one batch).** Items already answered by the description or the data were not asked. Full transcript in `intake.md`.
1. Smallest conversion lift worth shipping? [2%]  2. Revenue guardrail margin? [1%]  3. Is country a decision
segment? [no]  4. Was the test checked or stopped early? [no]  5. Incidents? [none]  6. Revenue capping? [none]
7. Defaults table: keep or change? [keep]  8. Deck depth? [standard]

**Plan (approved).** validate -> srm -> z-test (primary) -> non-inferiority (revenue) -> bootstrap sensitivity ->
platform segments + interaction + Simpson's -> time trends -> summary.

**What happened**
- Before approval, `python runs/.../20_analysis_primary_test.py` was **blocked by plan_gate** with the exact CLI fix.
- Validation: PASS on all 12 checks.
- Review round 1: FIXES NEEDED. The CI lower bound (+1.2%) is below the 2% threshold and the summary didn't say so.
  It went back to the analyst automatically; round 2 passed.
- The deck builder flagged the risks slide at 80 words, so the caveats were shortened at their source (the summary script).
- **Follow-up "rerun with alpha 0.01"**: `set_settings` recorded the override, then `reset analysis` -> rerun steps -> review round 3 ->
  deliverables rebuilt. This exposed hard-coded "95% CI" subtitles in the chart scripts (fixed, and the lesson added
  to the consulting-charts skill) and a stale number in the report appendix (it now quotes only the latest review round).

**Wrap-up message (as Claude would send it):**
> **Ship the single-button checkout.** Conversion rises from 34.25% to 35.34% (+3.2%, 99% CI +0.6% to +5.8%,
> p = 0.001, 80,000 users). Revenue per user is non-inferior (+2.2%, pass). Caveats: the CI lower bound is below
> your 2% threshold, so the true lift could be smaller than needed; iOS shows the largest lift (+5.2%), but
> platforms don't differ significantly (interaction p = 0.168). Files: `runs/2026-10-01_checkout-button/deck.pptx`,
> `summary.docx`, `charts/`.

## Run 2: SRM (must block at validation)

**Q&A asked.** Practical threshold; **how exposure is logged** (client event); **app releases or incidents during
the test** (an Android release around 4-5 Sep); guardrails; segments; defaults; depth. The SRM-relevant
answers were flagged under "Risks flagged at intake".

**What happened**
- Validation verdict **BLOCK**: SRM p = 1.2e-44. The check localised it automatically to exposure_date 2026-09-05 to 09-14
  (10 of 14 days) and platform = Android. iOS and Web are balanced (p = 0.323).
- The orchestrator stopped and explained:
  > I've stopped before looking at activation. Treatment has 18,073 users where a 50/50 split implies 19,456
  > (chi-square p < 0.001). The shortfall is almost entirely Android treatment users from 5 September, which matches
  > the Android release you mentioned. The exposure event probably stopped firing for them. Any activation
  > difference could be caused by the missing users, so I won't report one. Options: (1) fix the logging and
  > re-extract; (2) a clearly labelled iOS + Web-only sensitivity analysis; (3) rerun the test after the fix;
  > (4) a short "analysis blocked" readout for the team now.
- The user chose (4). The decision was recorded in `intake.md`, the planner revised the plan to `srm_investigation`
  (primary_test `skipped`), the user re-approved, and only then was `validation_passed` opened.
- Deliverables: a 6-slide "Blocked: data issue" deck (red verdict box, SRM charts, validation table, next steps) and a
  short report. No effect estimate appears anywhere (the reviewer verified this).

## Run 3: CUPED re-analysis

**Q&A asked.** Is pre_minutes strictly pre-assignment with the same definition? Any users missing it? **Was CUPED
planned before you saw the borderline result?** (No, recorded as a risk.) Practical threshold [1%]; guardrails;
segments; defaults; depth (explain CUPED simply).

**What happened**
- Validation PASS. The pre/post correlation of 0.73 predicts about 53% variance reduction (observed: 52.6%).
- Unadjusted: +2.1%, p = 0.081. CUPED: +1.7%, CI [+0.0%, +3.3%], p = 0.042. The CI is 31% narrower, and regression adjustment agrees.
- Review round 1: **BLOCKED**. The ship decision depends on an adjustment chosen after seeing the result, which
  could change the conclusion, so the orchestrator escalated it to the user instead of looping it to the analyst. The user
  accepted CUPED as primary with the caveat first and pre-registration as a next step. The same round also raised a `fix`:
  explain why the lift shrank (a chance pre-period head start in treatment); it was fixed. Round 2 passed.
- The deck showed three problems that the fix loop addressed: the verdict reason said "no guardrail was breached" with no
  guardrails (fixed in `abkit.decision`); a chart title said "last month's minutes" for a 14-day pre-period
  (fixed, now computed); and "31.2%" was computed in a chart script rather than stored (flagged by tracecheck; now stored as
  `extra.ci_width_reduction`).

---

## What worked
- **Gates and hooks.** plan_gate blocked out-of-order scripts in the live session; run_logger wrote `run_log.jsonl`;
  completeness_check stayed silent outside the deliverables phase and passed once everything existed. The Stop hook
  never fired spuriously.
- **Dynamic plans.** The three plans differ as they should: a 4-type readout, an SRM investigation with skipped
  estimates, and a CUPED re-analysis with sensitivity steps. Deck lengths were 18, 6 and 13 slides.
- **SRM localisation** in `validation.full_profile` pointed straight at the cause (day + platform) with no extra work.
- **Review loop.** One `fix` looped automatically (run 1), and one `blocker` was escalated to the user (run 3), as specified.
- **Single source of truth.** Summaries, charts, deck and report all read results.json; tracecheck caught three
  genuine slips during the runs.

## What felt clumsy
1. **Caveat length.** Caveats had to be shortened twice to fit the deck's word limit. One text serves the report
   (which wants detail) and the deck (which wants brevity).
2. **Chart-script boilerplate.** Each run's 30_ scripts repeat the same pattern: load results, build source line,
   title, takeaways and save. That's about 60 lines per run, and it's where the hard-coded "95% CI" slipped in.
3. **Blocked-run gate semantics.** A blocked run can only continue by setting `validation_passed = true` after the
   user's decision, so the gate means "validation resolved", not "data passed".
4. **plan_gate false positive.** A command that merely *mentions* a 20_ script path while also invoking python
   (e.g. piping a JSON payload that contains the path) is blocked. It's harmless but surprising.
5. **Windows specifics.** The typographic minus crashed prints on cp1252 consoles (fixed: abkit switches stdout to
   UTF-8). Previewing decks needed PowerPoint automation, since no LibreOffice is installed.
6. **run_log noise.** Every Bash / PowerShell command while a run is active is logged, including preview tooling.

## What I would improve next
1. Add `caveats_short` (or an automatic condenser) to the summary, and use it for the deck.
2. Chart recipes: `abkit.viz.recipes.readout(run)`, `.srm(run)`, `.cuped(run)` produce the standard charts,
   titles and takeaways from results.json with alpha-aware labels. Scripts then only add run-specific charts.
3. Add an explicit `decisions` log in state.json (user decisions at gates) and a `validation_overridden` flag, rather
   than overloading `validation_passed`.
4. Let plan_gate parse the command and gate only when python *executes* the script path (first positional argument).
5. Extend tracecheck to `charts/manifest.json` titles and takeaways, and to text rendered inside chart images
   (SVG text is available because `svg.fonttype = none`).
6. Spawn the real subagents in a future dry run to measure how reliably they follow their prompts in isolation.
