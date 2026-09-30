"""Stop: in the deliverables / done phase, refuse to stop while planned deliverables or charts are missing."""

from __future__ import annotations

import json

from _hooklib import active_run, block, load_state, project_dir, safe_main


def missing_items(run, st) -> list[str]:
    plan = st.get("plan", {})
    missing = []
    for item in plan.get("deliverables", []):
        path = run / item
        if item.endswith("/"):
            if not path.is_dir() or not any(path.iterdir()):
                missing.append(f"{item} (missing or empty)")
        elif not path.is_file():
            missing.append(item)
    charts = plan.get("charts", [])
    if charts:
        try:
            manifest = json.loads((run / "charts" / "manifest.json").read_text(encoding="utf-8"))
            listed = {c.get("id") for c in manifest.get("charts", [])}
        except (OSError, json.JSONDecodeError):
            listed = set()
        missing += [f"chart '{c}' not in charts/manifest.json" for c in charts if c not in listed]
    return missing


def main(payload):
    if payload.get("stop_hook_active"):
        return
    found = active_run(project_dir(payload))
    if not found:
        return
    run_id, run = found
    st = load_state(run)
    if not st or st.get("phase") not in ("deliverables", "done"):
        return
    missing = missing_items(run, st)
    if missing:
        block(f"completeness_check: run {run_id} is in phase '{st.get('phase')}' but planned deliverables are missing:\n  - "
              + "\n  - ".join(missing) + "\nProduce them (viz-designer, deck-builder, report-writer) before finishing, "
              "or tell the user why one cannot be produced and update plan.deliverables / plan.charts with their agreement.")


if __name__ == "__main__":
    safe_main(main)
