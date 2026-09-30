"""Run folders, the active-run pointer and the ``state.json`` schema.

The hooks in ``.claude/hooks`` read ``state.json`` directly, so the field
names below are a contract: change them only together with the hooks.

Example
-------
>>> from abkit import state
>>> run = state.new_run("checkout-button", context_text="...", csv_path="demo_data/checkout_ab.csv")
>>> st = state.load_state(run)
>>> st["phase"]
'intake'
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PHASES = ["intake", "planning", "validation", "analysis", "review", "deliverables", "done"]

PROBLEM_TYPES = [
    "power_analysis",
    "post_test_readout",
    "srm_investigation",
    "bayesian_readout",
    "cuped_reanalysis",
    "sequential_monitoring",
    "heterogeneous_effects",
    "multi_arm",
    "ratio_metric",
    "novelty_check",
    "guardrail_check",
    "quasi_experiment",
]

METRIC_ROLES = {"primary", "secondary", "guardrail"}
METRIC_TYPES = {"binary", "continuous", "count", "ratio"}
METRIC_DIRECTIONS = {"increase", "decrease", "no_decrease", "no_increase"}
STEP_STATUSES = {"pending", "running", "done", "failed", "skipped"}
CORRECTIONS = {"none", "bonferroni", "holm", "benjamini-hochberg"}
SIDEDNESS = {"two-sided", "one-sided"}
GATES = ("plan_approved", "validation_passed", "review_passed")
REQUIRED_SETTINGS = (
    "alpha",
    "sidedness",
    "power",
    "correction_primary",
    "correction_secondary",
    "correction_segments",
    "srm_threshold",
)
RUN_SUBDIRS = ("data", "code", "charts")


class StateError(ValueError):
    """Raised when state.json is missing or does not match the schema."""


# --------------------------------------------------------------------------- paths


def project_root(start: str | Path | None = None) -> Path:
    """Return the repository root (``$CLAUDE_PROJECT_DIR`` or the folder holding ``abkit/``)."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and (Path(env) / "abkit").is_dir():
        return Path(env)
    here = Path(start or Path.cwd()).resolve()
    for p in [here, *here.parents]:
        if (p / "abkit").is_dir() and (p / "config").is_dir():
            return p
    return Path(__file__).resolve().parent.parent


def runs_dir(root: str | Path | None = None) -> Path:
    return (Path(root) if root else project_root()) / "runs"


def active_run_id(root: str | Path | None = None) -> str | None:
    """Return the id in ``runs/.active`` or ``None`` when no run is active."""
    f = runs_dir(root) / ".active"
    if not f.is_file():
        return None
    run_id = f.read_text(encoding="utf-8").strip()
    return run_id or None


def run_dir(run_id: str | None = None, root: str | Path | None = None) -> Path:
    """Return the folder of ``run_id`` (default: the active run)."""
    run_id = run_id or active_run_id(root)
    if not run_id:
        raise StateError("No active run. Start one with state.new_run(...) or write runs/.active.")
    path = runs_dir(root) / run_id
    if not path.is_dir():
        raise StateError(f"Run folder not found: {path}")
    return path


def set_active(run_id: str | None, root: str | Path | None = None) -> None:
    """Point ``runs/.active`` at ``run_id`` (``None`` clears it)."""
    f = runs_dir(root) / ".active"
    if run_id is None:
        f.unlink(missing_ok=True)
        return
    if not (runs_dir(root) / run_id).is_dir():
        raise StateError(f"Unknown run id: {run_id}")
    f.write_text(run_id + "\n", encoding="utf-8")


def list_runs(root: str | Path | None = None) -> list[str]:
    d = runs_dir(root)
    return sorted(p.name for p in d.iterdir() if p.is_dir() and (p / "state.json").is_file()) if d.is_dir() else []


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "experiment"


# --------------------------------------------------------------------------- defaults


def load_defaults(root: str | Path | None = None) -> dict[str, Any]:
    """Read ``config/stat_defaults.yaml`` as a nested dict."""
    import yaml

    path = (Path(root) if root else project_root()) / "config" / "stat_defaults.yaml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def default_settings(root: str | Path | None = None) -> dict[str, Any]:
    """Flatten the YAML defaults into the ``state.json`` settings shape."""
    d = load_defaults(root)
    return {
        "alpha": d["alpha"],
        "sidedness": d["sidedness"],
        "power": d["power"],
        "confidence_level": d["confidence_level"],
        "correction_primary": d["correction"]["primary"],
        "correction_secondary": d["correction"]["secondary"],
        "correction_segments": d["correction"]["segments"],
        "srm_test": d["srm"]["test"],
        "srm_threshold": d["srm"]["threshold"],
        "min_days": d["duration"]["min_days"],
        "prefer_full_weeks": d["duration"]["prefer_full_weeks"],
        "bayes_prior": d["bayesian"]["prior"],
        "bayes_decision_threshold": d["bayesian"]["decision_threshold_prob_beat"],
        "bootstrap_n_resamples": d["bootstrap"]["n_resamples"],
        "bootstrap_seed": d["bootstrap"]["seed"],
        "noninferiority_margin_relative": d["guardrails"]["default_noninferiority_margin_relative"],
    }


# --------------------------------------------------------------------------- schema


def validate_state(st: dict[str, Any]) -> list[str]:
    """Return a list of schema problems (empty list means valid)."""
    errs: list[str] = []
    for key in ("run_id", "created_at", "phase", "problem_type", "settings", "metrics", "plan", "gates"):
        if key not in st:
            errs.append(f"missing key: {key}")
    if errs:
        return errs
    if st["phase"] not in PHASES:
        errs.append(f"phase must be one of {PHASES}, got {st['phase']!r}")
    if not isinstance(st["problem_type"], list) or not all(isinstance(p, str) for p in st["problem_type"]):
        errs.append("problem_type must be a list of strings")

    s = st["settings"]
    for key in REQUIRED_SETTINGS:
        if key not in s:
            errs.append(f"settings.{key} missing")
    if "alpha" in s and not (0 < float(s["alpha"]) < 1):
        errs.append("settings.alpha must be in (0, 1)")
    if "power" in s and not (0 < float(s["power"]) < 1):
        errs.append("settings.power must be in (0, 1)")
    if s.get("sidedness") not in SIDEDNESS | {None}:
        errs.append(f"settings.sidedness must be one of {sorted(SIDEDNESS)}")
    for key in ("correction_primary", "correction_secondary", "correction_segments"):
        if key in s and s[key] not in CORRECTIONS:
            errs.append(f"settings.{key} must be one of {sorted(CORRECTIONS)}")

    if not isinstance(st["metrics"], list):
        errs.append("metrics must be a list")
    else:
        for i, m in enumerate(st["metrics"]):
            if not m.get("name"):
                errs.append(f"metrics[{i}].name missing")
            if m.get("role") not in METRIC_ROLES:
                errs.append(f"metrics[{i}].role must be one of {sorted(METRIC_ROLES)}")
            if m.get("type") not in METRIC_TYPES:
                errs.append(f"metrics[{i}].type must be one of {sorted(METRIC_TYPES)}")
            if m.get("direction") not in METRIC_DIRECTIONS:
                errs.append(f"metrics[{i}].direction must be one of {sorted(METRIC_DIRECTIONS)}")

    plan = st["plan"]
    for key in ("steps", "charts", "deck_sections", "report_sections", "deliverables"):
        if not isinstance(plan.get(key), list):
            errs.append(f"plan.{key} must be a list")
    ids = set()
    for i, step in enumerate(plan.get("steps") or []):
        if not step.get("id") or not step.get("method"):
            errs.append(f"plan.steps[{i}] needs id and method")
        if step.get("id") in ids:
            errs.append(f"plan.steps[{i}] duplicate id {step.get('id')!r}")
        ids.add(step.get("id"))
        if step.get("status", "pending") not in STEP_STATUSES:
            errs.append(f"plan.steps[{i}].status must be one of {sorted(STEP_STATUSES)}")

    for g in GATES:
        if not isinstance(st["gates"].get(g), bool):
            errs.append(f"gates.{g} must be true/false")
    return errs


def empty_state(run_id: str, root: str | Path | None = None) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": _now(),
        "phase": "intake",
        "problem_type": [],
        "settings": default_settings(root),
        "overrides": {},
        "metrics": [],
        "plan": {"steps": [], "charts": [], "deck_sections": [], "report_sections": [], "deliverables": []},
        "gates": {g: False for g in GATES},
        "history": [{"at": _now(), "event": "run created"}],
    }


# --------------------------------------------------------------------------- read / write


def load_state(run: str | Path | None = None) -> dict[str, Any]:
    """Load ``state.json`` from a run folder (default: active run)."""
    path = _run_path(run) / "state.json"
    if not path.is_file():
        raise StateError(f"state.json not found in {path.parent}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(run: str | Path | None, st: dict[str, Any]) -> Path:
    """Validate and write ``state.json``. Raises StateError on schema problems."""
    errs = validate_state(st)
    if errs:
        raise StateError("state.json invalid:\n  - " + "\n  - ".join(errs))
    path = _run_path(run) / "state.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)
    return path


def update_state(run: str | Path | None = None, **changes: Any) -> dict[str, Any]:
    """Shallow-merge top-level keys into state.json and save.

    >>> update_state(problem_type=["post_test_readout"])  # doctest: +SKIP
    """
    st = load_state(run)
    for k, v in changes.items():
        if isinstance(v, dict) and isinstance(st.get(k), dict):
            st[k].update(v)
        else:
            st[k] = v
    save_state(run, st)
    return st


def set_phase(run: str | Path | None, phase: str) -> dict[str, Any]:
    if phase not in PHASES:
        raise StateError(f"Unknown phase {phase!r}")
    st = load_state(run)
    st["phase"] = phase
    _log(st, f"phase -> {phase}")
    save_state(run, st)
    return st


def set_gate(run: str | Path | None, gate: str, value: bool) -> dict[str, Any]:
    if gate not in GATES:
        raise StateError(f"Unknown gate {gate!r}; expected one of {GATES}")
    st = load_state(run)
    st["gates"][gate] = bool(value)
    _log(st, f"gate {gate} = {bool(value)}")
    save_state(run, st)
    return st


def set_step_status(run: str | Path | None, step_id: str, status: str, note: str | None = None) -> dict[str, Any]:
    if status not in STEP_STATUSES:
        raise StateError(f"Unknown status {status!r}")
    st = load_state(run)
    for step in st["plan"]["steps"]:
        if step["id"] == step_id:
            step["status"] = status
            if note:
                step["note"] = note
            break
    else:
        raise StateError(f"No plan step with id {step_id!r}")
    save_state(run, st)
    return st


def set_settings(run: str | Path | None, **overrides: Any) -> dict[str, Any]:
    """Override statistical settings and record them under ``overrides``."""
    st = load_state(run)
    for k, v in overrides.items():
        old = st["settings"].get(k)
        st["settings"][k] = v
        st.setdefault("overrides", {})[k] = {"from": old, "to": v, "at": _now()}
        _log(st, f"setting {k}: {old} -> {v}")
    save_state(run, st)
    return st


def reset_downstream(run: str | Path | None, phase: str) -> dict[str, Any]:
    """Re-open ``phase`` and everything after it (used by follow-ups and /rerun)."""
    st = load_state(run)
    idx = PHASES.index(phase)
    if idx <= PHASES.index("planning"):
        st["gates"]["plan_approved"] = False
    if idx <= PHASES.index("validation"):
        st["gates"]["validation_passed"] = False
    if idx <= PHASES.index("review"):
        st["gates"]["review_passed"] = False
    st["phase"] = phase
    _log(st, f"reset to {phase}")
    save_state(run, st)
    return st


def next_step_hint(st: dict[str, Any]) -> str:
    """One-line suggestion for what the orchestrator should do next."""
    g, phase = st["gates"], st["phase"]
    if phase == "intake":
        return "Finish intake Q&A, write intake.md, then call experiment-planner."
    if phase == "planning" or not g["plan_approved"]:
        return "Show plan.md to the user and wait for explicit approval (set gates.plan_approved)."
    if phase == "validation" or not g["validation_passed"]:
        return "Call data-validator; resolve any blocking checks with the user."
    if phase == "analysis":
        pending = [s["id"] for s in st["plan"]["steps"] if s.get("status") != "done"]
        return f"Call stats-analyst for pending steps: {', '.join(pending) or 'none'}."
    if phase == "review" or not g["review_passed"]:
        return "Call stats-reviewer; loop fixable issues back to stats-analyst (max 2)."
    if phase == "deliverables":
        return "Call viz-designer, then deck-builder and report-writer; then wrap up."
    return "Run complete. Answer follow-ups or start a new experiment."


# --------------------------------------------------------------------------- run creation


def new_run(
    slug: str,
    context_text: str,
    csv_path: str | Path | None = None,
    run_date: date | None = None,
    root: str | Path | None = None,
    activate: bool = True,
) -> Path:
    """Create ``runs/<date>_<slug>/`` with subfolders, context.md, state.json and a CSV copy.

    The original CSV is copied, never moved or modified.
    """
    root_path = Path(root) if root else project_root()
    run_id = f"{(run_date or date.today()).isoformat()}_{slugify(slug)}"
    base = runs_dir(root_path) / run_id
    suffix = 2
    while base.exists():
        base = runs_dir(root_path) / f"{run_id}-{suffix}"
        suffix += 1
    run_id = base.name
    for sub in RUN_SUBDIRS:
        (base / sub).mkdir(parents=True, exist_ok=True)
    (base / "context.md").write_text(context_text.strip() + "\n", encoding="utf-8")
    if csv_path:
        src = Path(csv_path)
        if not src.is_file():
            raise StateError(f"CSV not found: {src}")
        shutil.copy2(src, base / "data" / src.name)
    st = empty_state(run_id, root_path)
    if csv_path:
        st["input_csv"] = f"data/{Path(csv_path).name}"
        st["source_csv"] = str(Path(csv_path).resolve())
    save_state(base, st)
    if activate:
        set_active(run_id, root_path)
    return base


# --------------------------------------------------------------------------- internals


def _run_path(run: str | Path | None) -> Path:
    if run is None:
        return run_dir()
    p = Path(run)
    if p.is_dir():
        return p
    return run_dir(str(run))


def _log(st: dict[str, Any], event: str) -> None:
    st.setdefault("history", []).append({"at": _now(), "event": event})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
