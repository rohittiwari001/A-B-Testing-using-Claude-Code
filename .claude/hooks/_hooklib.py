"""Shared helpers for the workflow hooks (standard library only, so hooks start fast).

Contract for every hook:
- read the JSON payload from stdin;
- do nothing and exit 0 when there is no active run (runs/.active missing or empty);
- never crash the session: internal errors go to stderr and the hook exits 0;
- exit 2 with a message on stderr to block (PreToolUse, Stop) or to feed back to Claude (PostToolUse).
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

PALETTE_HEX = {"#1A1A1A", "#0B2545", "#2251FF", "#9DB4FF", "#8C8C8C", "#E3E3E3", "#1B7F5A", "#C0392B", "#B08900", "#FFFFFF"}


def read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def project_dir(payload: dict[str, Any]) -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else Path(payload.get("cwd") or os.getcwd())


def active_run(project: Path) -> tuple[str, Path] | None:
    """(run_id, run_dir) of the active run, or None."""
    marker = project / "runs" / ".active"
    try:
        run_id = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not run_id:
        return None
    run = project / "runs" / run_id
    return (run_id, run) if run.is_dir() else None


def load_state(run: Path) -> dict[str, Any] | None:
    try:
        return json.loads((run / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def posix(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def run_code_file(path: str) -> re.Match | None:
    """Match .../runs/<id>/code/<name>.py; groups: run id, file name."""
    return re.search(r"(?:^|/)runs/([^/]+)/code/([^/]+\.py)$", posix(path))


def block(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(2)


def safe_main(fn: Callable[[dict[str, Any]], None]) -> None:
    """Run a hook body; any internal error is logged to stderr and the hook exits 0."""
    try:
        fn(read_payload())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - hooks must never crash the session
        print(f"[hook {Path(sys.argv[0]).name}] internal error (ignored):\n{traceback.format_exc()}", file=sys.stderr)
        sys.exit(0)
    sys.exit(0)
