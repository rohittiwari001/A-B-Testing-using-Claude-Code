"""CSV loading and small data-shaping helpers.

Example
-------
>>> from abkit import io
>>> df = io.load_run_csv()                     # doctest: +SKIP  (active run's data/ copy)
>>> io.infer_metric_type(df["converted"])      # doctest: +SKIP
'binary'
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

DATE_HINTS = ("date", "day", "time", "timestamp", "week", "period")


def load_csv(path: str | Path, date_cols: Iterable[str] | None = None, **kwargs) -> pd.DataFrame:
    """Read a CSV and parse date columns (explicit, or guessed from column names)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    df = pd.read_csv(path, **kwargs)
    cols = list(date_cols) if date_cols is not None else [c for c in df.columns if any(h in c.lower() for h in DATE_HINTS)]
    for c in cols:
        if c in df.columns and not pd.api.types.is_numeric_dtype(df[c]):
            parsed = pd.to_datetime(df[c], errors="coerce")
            if parsed.notna().mean() > 0.95:
                df[c] = parsed
    return df


def load_run_csv(run_dir: str | Path | None = None, name: str | None = None, **kwargs) -> pd.DataFrame:
    """Load the CSV copy stored in ``<run>/data/`` (never the original)."""
    from abkit import state

    run = Path(run_dir) if run_dir else state.run_dir()
    data = run / "data"
    files = sorted(data.glob("*.csv")) if name is None else [data / name]
    if not files:
        raise FileNotFoundError(f"No CSV in {data}")
    if len(files) > 1 and name is None:
        st = state.load_state(run)
        if st.get("input_csv"):
            return load_csv(run / st["input_csv"], **kwargs)
    return load_csv(files[0], **kwargs)


def infer_metric_type(s: pd.Series) -> str:
    """Guess 'binary', 'count' or 'continuous' from values."""
    v = s.dropna()
    if v.empty:
        return "continuous"
    uniq = pd.unique(v)
    if len(uniq) <= 2 and set(np.asarray(uniq, dtype=float)) <= {0.0, 1.0}:
        return "binary"
    if pd.api.types.is_integer_dtype(v) or np.allclose(v, np.round(v)):
        return "count" if (v >= 0).all() else "continuous"
    return "continuous"


def to_unit_level(df: pd.DataFrame, unit_col: str, agg: dict[str, str], keep: Iterable[str] = ()) -> pd.DataFrame:
    """Aggregate event/session rows to one row per randomisation unit.

    ``keep`` columns (e.g. variant, segments) take the first value per unit.
    """
    spec = {**agg, **{c: "first" for c in keep}}
    return df.groupby(unit_col, as_index=False).agg(spec)


def variants(df: pd.DataFrame, variant_col: str, control: str | None = None) -> list[str]:
    """Variant labels with the control first."""
    vals = [str(v) for v in pd.unique(df[variant_col].dropna())]
    vals = sorted(vals)
    if control is not None:
        if str(control) not in vals:
            raise ValueError(f"Control {control!r} not found in {variant_col}; values: {vals}")
        vals.remove(str(control))
        vals.insert(0, str(control))
    return vals
