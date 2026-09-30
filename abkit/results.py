"""``results.json``: the single source of truth for every number in a run.

Layout::

    {
      "schema_version": 1,
      "run_id": "...",
      "updated_at": "ISO-8601",
      "validation": {"verdict": "pass|warn|block", "checks": [...], "script": "code/10_..."},
      "steps": {
        "<step_id>": {
          "step_id": "...", "method": "frequentist.two_proportion_ztest",
          "script": "code/20_analysis_primary.py", "recorded_at": "...",
          "results": [<StatResult dict>, ...],     # tests / estimates
          "data": {...}                            # tables & series for charts
        }
      },
      "summary": {"verdict": "...", "headline": "...", "key_numbers": [...], "caveats": [...], "next_steps": [...]},
      "candidates_for_promotion": [{"name": "...", "file": "code/...", "description": "..."}]
    }

Every statistical function in abkit returns a :class:`StatResult` so that it can
be stored with :func:`add_result` without reshaping.

Example
-------
>>> from abkit import results
>>> r = results.StatResult(method="welch_ttest", estimate=0.12, ci_low=0.02, ci_high=0.22, p_value=0.02)
>>> results.fmt_pct(0.0321)
'+3.2%'
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1


@dataclass
class StatResult:
    """Consistent shape returned by every abkit statistical function.

    ``estimate`` is the headline quantity: usually the absolute difference
    treatment - control (``abs_lift``); for power functions it is the required
    sample size per variant, and so on (see ``method``).
    """

    method: str
    estimate: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    p_value: float | None = None
    probability: float | None = None
    n: dict[str, int] = field(default_factory=dict)
    metric: str | None = None
    role: str | None = None
    control: str | None = None
    treatment: str | None = None
    control_value: float | None = None
    treatment_value: float | None = None
    rel_lift: float | None = None
    rel_ci_low: float | None = None
    rel_ci_high: float | None = None
    alpha: float | None = None
    sidedness: str | None = None
    significant: bool | None = None
    correction: str = "none"
    p_value_adjusted: float | None = None
    segment: str | None = None
    assumptions: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def abs_lift(self) -> float | None:
        return self.estimate

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["abs_lift"] = self.estimate
        return clean(d)


# --------------------------------------------------------------------------- JSON helpers


def clean(obj: Any) -> Any:
    """Convert numpy/pandas objects into plain JSON types (NaN/inf -> None)."""
    try:
        import numpy as np
        import pandas as pd
    except ImportError:  # pragma: no cover
        np = pd = None  # type: ignore
    if isinstance(obj, StatResult):
        return obj.to_dict()
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [clean(v) for v in obj]
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if np is not None:
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            obj = float(obj)
        elif isinstance(obj, np.ndarray):
            return [clean(v) for v in obj.tolist()]
    if pd is not None:
        if isinstance(obj, pd.DataFrame):
            return clean(obj.to_dict(orient="records"))
        if isinstance(obj, pd.Series):
            return clean(obj.to_dict())
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, int):
        return obj
    return str(obj)


def results_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / "results.json"


def empty_results(run_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "updated_at": _now(),
        "validation": {},
        "steps": {},
        "summary": {},
        "candidates_for_promotion": [],
    }


def load_results(run_dir: str | Path) -> dict[str, Any]:
    """Load results.json (an empty skeleton if it does not exist yet)."""
    path = results_path(run_dir)
    if not path.is_file():
        return empty_results(Path(run_dir).name)
    return json.loads(path.read_text(encoding="utf-8"))


def save_results(run_dir: str | Path, res: dict[str, Any]) -> Path:
    errs = validate_results(res)
    if errs:
        raise ValueError("results.json invalid:\n  - " + "\n  - ".join(errs))
    res["updated_at"] = _now()
    path = results_path(run_dir)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean(res), indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def validate_results(res: dict[str, Any]) -> list[str]:
    errs = []
    for key in ("schema_version", "run_id", "steps"):
        if key not in res:
            errs.append(f"missing key: {key}")
    for sid, step in (res.get("steps") or {}).items():
        if not isinstance(step, dict):
            errs.append(f"steps.{sid} must be an object")
            continue
        if not step.get("script"):
            errs.append(f"steps.{sid}.script missing (every number must be traceable to code/)")
        for i, r in enumerate(step.get("results", [])):
            if "method" not in r:
                errs.append(f"steps.{sid}.results[{i}].method missing")
    return errs


# --------------------------------------------------------------------------- add / read


def add_result(
    run_dir: str | Path,
    step_id: str,
    results: StatResult | dict | Iterable[StatResult | dict] | None,
    script: str,
    method: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Store (replace) a step's results and supporting data.

    ``script`` is the path of the code file that produced the numbers, relative
    to the run folder (e.g. ``"code/20_analysis_primary.py"``); pass ``__file__``
    and it is made relative automatically.
    """
    res = load_results(run_dir)
    if results is None:
        items: list[Any] = []
    elif isinstance(results, (StatResult, dict)):
        items = [results]
    else:
        items = list(results)
    entry = {
        "step_id": step_id,
        "method": method or (items[0].method if items and isinstance(items[0], StatResult) else (items[0].get("method") if items else None)),
        "script": _rel_script(run_dir, script),
        "recorded_at": _now(),
        "results": [clean(r) for r in items],
        "data": clean(data or {}),
    }
    res["steps"][step_id] = entry
    save_results(run_dir, res)
    return entry


def get_step(run_dir_or_res: str | Path | dict, step_id: str) -> dict[str, Any]:
    res = run_dir_or_res if isinstance(run_dir_or_res, dict) else load_results(run_dir_or_res)
    try:
        return res["steps"][step_id]
    except KeyError as exc:
        raise KeyError(f"No step {step_id!r} in results.json; have {sorted(res['steps'])}") from exc


def get_result(run_dir_or_res: str | Path | dict, step_id: str, index: int = 0, **match: Any) -> dict[str, Any]:
    """Return one result dict from a step, optionally filtered by fields.

    >>> get_result(run, "segments", segment="iOS")  # doctest: +SKIP
    """
    rows = get_step(run_dir_or_res, step_id)["results"]
    if match:
        rows = [r for r in rows if all(r.get(k) == v for k, v in match.items())]
    if not rows:
        raise KeyError(f"No result in step {step_id!r} matching {match}")
    return rows[index]


def all_results(run_dir_or_res: str | Path | dict, role: str | None = None) -> list[dict[str, Any]]:
    """Flatten results across steps (optionally only one metric role)."""
    res = run_dir_or_res if isinstance(run_dir_or_res, dict) else load_results(run_dir_or_res)
    out = []
    for sid, step in res["steps"].items():
        for r in step.get("results", []):
            if role is None or r.get("role") == role:
                out.append({**r, "step_id": sid})
    return out


def set_validation(run_dir: str | Path, profile: dict[str, Any], script: str) -> None:
    res = load_results(run_dir)
    res["validation"] = {**clean(profile), "script": _rel_script(run_dir, script), "recorded_at": _now()}
    save_results(run_dir, res)


def set_summary(run_dir: str | Path, summary: dict[str, Any], script: str) -> None:
    res = load_results(run_dir)
    res["summary"] = {**clean(summary), "script": _rel_script(run_dir, script), "recorded_at": _now()}
    save_results(run_dir, res)


def add_candidate(run_dir: str | Path, name: str, file: str, description: str, target_module: str | None = None) -> None:
    """Flag a run-local function as a candidate for promotion into abkit."""
    res = load_results(run_dir)
    cands = [c for c in res.get("candidates_for_promotion", []) if c.get("name") != name]
    cands.append({"name": name, "file": _rel_script(run_dir, file), "description": description, "target_module": target_module})
    res["candidates_for_promotion"] = cands
    save_results(run_dir, res)


# --------------------------------------------------------------------------- formatting (shared by charts, deck, report)


def fmt_pct(x: float | None, decimals: int = 1, signed: bool = True) -> str:
    """0.0321 -> '+3.2%'. None -> 'n/a'."""
    if x is None:
        return "n/a"
    s = f"{x * 100:+.{decimals}f}%" if signed else f"{x * 100:.{decimals}f}%"
    return s.replace("-", "−") if s.startswith("-") else s


def fmt_pp(x: float | None, decimals: int = 1) -> str:
    """Absolute difference of proportions in percentage points: 0.0042 -> '+0.4 pp'."""
    if x is None:
        return "n/a"
    s = f"{x * 100:+.{decimals}f} pp"
    return s.replace("-", "−") if s.startswith("-") else s


def fmt_p(p: float | None) -> str:
    """p-values to three decimals or '<0.001'."""
    if p is None:
        return "n/a"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def fmt_prob(p: float | None) -> str:
    return "n/a" if p is None else f"{p * 100:.1f}%"


def fmt_num(x: float | None, decimals: int | None = None) -> str:
    """Thousands separators; sensible decimals for small numbers."""
    if x is None:
        return "n/a"
    if decimals is None:
        decimals = 0 if abs(x) >= 100 or float(x).is_integer() else (2 if abs(x) >= 1 else 4)
    s = f"{x:,.{decimals}f}"
    return s.replace("-", "−") if s.startswith("-") else s


def fmt_ci(lo: float | None, hi: float | None, kind: str = "pct") -> str:
    """Format an interval: kind 'pct' (relative), 'pp' or 'num'."""
    f = {"pct": fmt_pct, "pp": fmt_pp, "num": fmt_num}[kind]
    return f"[{f(lo)}, {f(hi)}]"


def fmt_value(x: float | None, metric_type: str | None) -> str:
    """A metric level: binary as a %, else a number."""
    if metric_type == "binary":
        return fmt_pct(x, signed=False, decimals=2)
    return fmt_num(x)


def describe(r: dict[str, Any]) -> str:
    """One-line human description of a comparison result, built only from its numbers."""
    parts = [f"{r.get('treatment', 'treatment')} vs {r.get('control', 'control')} on {r.get('metric', 'metric')}:"]
    if r.get("rel_lift") is not None:
        parts.append(f"{fmt_pct(r['rel_lift'])} relative")
        if r.get("rel_ci_low") is not None:
            level = round((1 - (r.get("alpha") or 0.05)) * 100)
            parts.append(f"({level}% CI {fmt_ci(r['rel_ci_low'], r['rel_ci_high'])})")
    if r.get("p_value_adjusted") is not None:
        parts.append(f"adj. p = {fmt_p(r['p_value_adjusted'])}")
    elif r.get("p_value") is not None:
        parts.append(f"p = {fmt_p(r['p_value'])}")
    if r.get("probability") is not None:
        parts.append(f"P(beat control) = {fmt_prob(r['probability'])}")
    return " ".join(parts)


def _rel_script(run_dir: str | Path, script: str) -> str:
    p = Path(script)
    try:
        return p.resolve().relative_to(Path(run_dir).resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
