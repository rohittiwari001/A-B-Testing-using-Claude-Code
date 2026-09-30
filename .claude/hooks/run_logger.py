"""PostToolUse / PostToolUseFailure (Bash|PowerShell): append each command to runs/<id>/run_log.jsonl."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from _hooklib import active_run, project_dir, safe_main


def _exit_status(payload) -> tuple[str, int | None]:
    if payload.get("hook_event_name") == "PostToolUseFailure":
        return "failed", None
    resp = payload.get("tool_response")
    code = None
    if isinstance(resp, dict):
        for key in ("exit_code", "exitCode", "returncode", "code"):
            if isinstance(resp.get(key), int):
                code = resp[key]
                break
        if resp.get("interrupted"):
            return "interrupted", code
    if code is None:
        return "ok", 0          # PostToolUse fires for commands that completed; failures arrive as PostToolUseFailure
    return ("ok" if code == 0 else "failed"), code


def main(payload):
    found = active_run(project_dir(payload))
    if not found:
        return
    run_id, run = found
    tool_input = payload.get("tool_input") or {}
    status, code = _exit_status(payload)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": payload.get("tool_name"),
        "command": tool_input.get("command"),
        "description": tool_input.get("description"),
        "status": status,
        "exit_code": code,
        "agent": payload.get("agent_type"),
    }
    if status == "failed" and payload.get("error_message"):
        entry["error"] = str(payload["error_message"])[:500]
    with open(run / "run_log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    safe_main(main)
