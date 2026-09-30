"""Shared fixtures: a temporary project root with config/ so runs never touch the real runs/ folder."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DEMO = ROOT / "demo_data"


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    """A throwaway project root (config + empty runs/) used as CLAUDE_PROJECT_DIR."""
    shutil.copytree(ROOT / "config", tmp_path / "config")
    (tmp_path / "abkit").mkdir()
    (tmp_path / "runs").mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture(scope="session")
def demo_csvs():
    """Make sure the demo CSVs exist (generated deterministically)."""
    if not (DEMO / "checkout_ab.csv").is_file():
        sys.path.insert(0, str(DEMO))
        import generate

        generate.generate()
    return DEMO


@pytest.fixture(scope="session")
def checkout_df(demo_csvs):
    return pd.read_csv(demo_csvs / "checkout_ab.csv")


@pytest.fixture
def rng():
    return np.random.default_rng(123)
