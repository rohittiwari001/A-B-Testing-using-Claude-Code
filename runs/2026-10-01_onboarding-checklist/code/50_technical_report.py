"""Build technical_report.docx: methods, formulas, decision log, robustness and reproducibility for data scientists."""

from pathlib import Path

from abkit.report import build_technical_report

RUN = Path(__file__).resolve().parents[1]
print(build_technical_report(RUN))
