"""Render a sample deck and report (checkout demo) into docs/sample/ for review.

Run:  python docs/make_samples.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo_data"))
sys.path.insert(0, str(ROOT))

from abkit.deck import build_standard_deck  # noqa: E402
from abkit.report import build_standard_report, build_technical_report  # noqa: E402
from sample_run import build_checkout_sample  # noqa: E402

if __name__ == "__main__":
    out = ROOT / "docs" / "sample"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(ROOT / "config", Path(tmp) / "config")
        (Path(tmp) / "runs").mkdir()
        run = build_checkout_sample(root=tmp)
        print(build_standard_deck(run, out / "sample_deck.pptx"))
        print(build_standard_report(run, out / "sample_summary.docx"))
        print(build_technical_report(run, out / "sample_technical_report.docx"))
        shutil.copy(run / "results.json", out / "sample_results.json")
