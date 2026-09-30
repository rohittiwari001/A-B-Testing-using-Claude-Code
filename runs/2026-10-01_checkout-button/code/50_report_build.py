"""Build summary.docx from results.json, intake.md, review.md and charts/manifest.json."""

from pathlib import Path

from abkit.report import build_standard_report

RUN = Path(__file__).resolve().parents[1]
print(build_standard_report(RUN))
