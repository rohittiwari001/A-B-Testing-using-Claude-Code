"""Build summary.docx for the blocked readout."""

from pathlib import Path

from abkit.report import build_standard_report

RUN = Path(__file__).resolve().parents[1]
print(build_standard_report(RUN))
