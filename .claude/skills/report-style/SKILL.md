---
name: report-style
description: Structure and writing rules for the Word summary report (summary.docx) of an experiment run, built with abkit.report (python-docx). Use when building, extending or reviewing the report (report-writer agent, 50_report_*.py scripts).
---

# Report style

## Build it with abkit

```python
"""Build summary.docx for <run>."""
from pathlib import Path
from abkit.report import build_standard_report
RUN = Path(__file__).resolve().parents[1]
print(build_standard_report(RUN))     # sections from state.plan.report_sections
```

Custom content: use `abkit.report.Report` primitives (`heading`, `para`, `bullets`, `figure`, `table`,
`verdict_box`) in the same script; every number formatted from results.json with `abkit.results.fmt_*`.

## Structure (state.plan.report_sections)

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
11. `appendix` - settings and overrides, reviewer findings (from review.md), all estimates, code index.

Sections without content (e.g. no segments planned) are skipped by the builder.

## Writing rules
- First page for a non-statistician: no jargon without translation ("statistically significant - unlikely to be chance").
- Whole document complete for a data scientist: methods, assumptions, corrections, exact p-values.
- Same fonts and colours as the deck (Arial, navy headings, palette tokens); built-in Heading styles.
- Every chart and table has a numbered caption (the builder adds "Figure n:" / "Table n:").
- Numbers formatted exactly as in the deck (shared `abkit.results.fmt_*` helpers).
- Use "inconclusive" rather than "no effect"; give the CI range in words.
