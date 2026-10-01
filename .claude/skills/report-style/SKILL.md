---
name: report-style
description: Structure and writing rules for the two Word documents of an experiment run, built with abkit.report (python-docx) - summary.docx for stakeholders and technical_report.docx for data scientists (methods and formulas, decision log, robustness, reproducibility). Use when building, extending or reviewing either document (report-writer agent, 50_report_*.py and 50_technical_report.py scripts), or when a data scientist asks how a run's result was obtained.
---

# Report style

Every run produces two documents for two readers:

| Document | Reader | Question it answers | Builder |
|---|---|---|---|
| `summary.docx` | stakeholders | What did we find and what should we do? | `abkit.report.build_standard_report` |
| `technical_report.docx` | data scientists | How exactly was this obtained, and can I trust / reproduce it? | `abkit.report.build_technical_report` |

Both use the same house style (Arial, navy headings, palette tokens, numbered captions) and read every number
from results.json.

## Build them with abkit

```python
"""Build summary.docx for <run>."""                       # code/50_report_build.py
from pathlib import Path
from abkit.report import build_standard_report
RUN = Path(__file__).resolve().parents[1]
print(build_standard_report(RUN))     # sections from state.plan.report_sections
```

```python
"""Build technical_report.docx for <run>."""              # code/50_technical_report.py
from pathlib import Path
from abkit.report import build_technical_report
RUN = Path(__file__).resolve().parents[1]
print(build_technical_report(RUN))    # fixed structure, below
```

Custom content: use `abkit.report.Report` primitives (`heading`, `para`, `bullets`, `figure`, `table`,
`verdict_box`) in the same script; every number formatted from results.json with `abkit.results.fmt_*`.

## summary.docx structure (state.plan.report_sections)

1. `exec_summary` - half a page, verdict first: coloured verdict box with headline and reason, the
   plain-English sentence, 3-5 key numbers, caveats, next step. Readable by a non-statistician.
2. `business_question` - business question, decision, hypothesis (from intake.md) and the context as described.
3. `design` - variants and split, units, dates, metrics with roles, settings.
4. `data_validation` - verdict per check; what was flagged and what was done about it.
5. `methodology` - tests per step and why; settings and corrections.
6. `results` - charts with captions, then tables of primary and secondary metrics.
7. `guardrails` - scorecard and non-inferiority table.
8. `segments` - forest plot, table, interaction test, exploratory warning.
9. `risks` - limitations, failed assumptions, caveats.
10. `recommendation` - decision and numbered next steps.
11. `appendix` - settings and overrides, reviewer findings (latest round), all estimates, code index.

Sections without content (e.g. no segments planned) are skipped by the builder.

## technical_report.docx structure (fixed)

| # | Section | Content | Sources |
|---|---|---|---|
| 1 | Technical summary | verdict and reason, headline, the decision rule, primary estimate table, caveats | results.json summary |
| 2 | Problem framing and design | business question, formal H0 / H1, design (variant column, unit, intended split, period), metrics with thresholds / margins, every statistical setting and override | intake.md, state.json |
| 3 | Data and validation | lineage (original file, analysed copy, SHA-256, shape), validation verdict, every check, validation charts | state.json, results.json validation |
| 4 | Methods, step by step | per plan step: why (from plan.md), script, the method's estimator / formula / inference / assumptions / reference, settings applied (alpha, sidedness, correction), assumptions checked (PASS / FAIL / NOT CHECKED), method notes | plan.md, results.json, `abkit.report.technical.METHOD_DOCS` |
| 5 | Results | every effect estimate (absolute and relative with CIs, evidence, n), Bayesian outputs (P(beat), expected loss, prior), diagnostic tests (SRM, interaction, Simpson's, trend), result charts | results.json, charts |
| 6 | Robustness and sensitivity | the same metric across methods side by side, distance to the decision boundaries (CI vs threshold, p vs alpha), what could change the conclusion | results.json |
| 7 | Decision log | intake Q&A, user decisions at gates, plan changes, state history, every review round with its findings | intake.md, plan.md, state.json history, review.md |
| 8 | Reproducibility | Python, platform and package versions, seeds, code index (script, purpose, results written), rerun commands in order, tracecheck command, run-log summary, artefacts, promotion candidates | environment, code/, run_log.jsonl |

Rules specific to the technical report:
- **Formulas:** standard methods are documented from `METHOD_DOCS` in `abkit/report/technical.py`. When a method is
  promoted into abkit, add its entry there (name, what, formula lines, inference, assumptions, reference). A custom
  run-local method is documented by its script's docstring: write the estimator, formula and CI construction there.
- **Verbatim records** (intake answers, user decisions, plan notes, review findings) use Word's "Quote" style. They may
  mention values that were later superseded; `abkit.tracecheck` skips Quote paragraphs. Everything else must trace to
  results.json.
- **Completeness over brevity:** exact p-values, absolute and relative effects, every assumption with its status,
  corrections named. No plain-language softening: that is summary.docx's job.

## Writing rules (both documents)
- summary.docx page one is for a non-statistician: no jargon without translation ("statistically significant - unlikely to be chance").
- Same fonts and colours as the deck (Arial, navy headings, palette tokens); built-in Heading styles.
- Every chart and table has a numbered caption (the builder adds "Figure n:" / "Table n:").
- Numbers formatted exactly as in the deck (shared `abkit.results.fmt_*` helpers).
- Use "inconclusive" rather than "no effect"; give the CI range.
