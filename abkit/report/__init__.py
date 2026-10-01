"""python-docx reports: ``build_standard_report`` (summary.docx, stakeholders) and
``build_technical_report`` (technical_report.docx, data scientists)."""

from abkit.report.builder import Report, build_standard_report
from abkit.report.technical import build_technical_report

__all__ = ["Report", "build_standard_report", "build_technical_report"]
