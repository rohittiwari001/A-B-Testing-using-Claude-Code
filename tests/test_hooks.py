"""Hook scripts exercised as subprocesses with sample payloads, as Claude Code runs them."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".claude" / "hooks"
RUN_ID = "2026-10-01_test-run"


def run_hook(name, payload, project, raw=None):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, str(HOOKS / f"{name}.py")], input=raw if raw is not None else json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=30)
    p.elapsed = time.perf_counter() - t0
    return p


@pytest.fixture
def project(tmp_path):
    (tmp_path / "runs").mkdir()
    return tmp_path


def make_run(project, phase="analysis", gates=(False, False, False), charts=(), deliverables=()):
    run = project / "runs" / RUN_ID
    (run / "code").mkdir(parents=True, exist_ok=True)
    (run / "charts").mkdir(exist_ok=True)
    st = {"run_id": RUN_ID, "phase": phase,
          "gates": dict(zip(["plan_approved", "validation_passed", "review_passed"], gates)),
          "plan": {"steps": [{"id": "primary_test", "method": "frequentist.compare", "status": "pending"}],
                   "charts": list(charts), "deliverables": list(deliverables)}}
    (run / "state.json").write_text(json.dumps(st))
    (project / "runs" / ".active").write_text(RUN_ID + "\n")
    return run


def bash(cmd, tool="Bash"):
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": cmd}}


def write(path, content=None):
    return {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": str(path)}}


# --------------------------------------------------------------------------- silence without an active run


@pytest.mark.parametrize("name,payload", [
    ("session_start", {"source": "startup"}),
    ("plan_gate", bash("python runs/x/code/40_deck_build.py")),
    ("style_guard", write("runs/x/code/30_charts_a.py")),
    ("numbers_guard", write("runs/x/code/40_deck_build.py")),
    ("run_logger", {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}}),
    ("completeness_check", {"hook_event_name": "Stop", "stop_hook_active": False}),
])
def test_no_active_run_is_silent(project, name, payload):
    p = run_hook(name, payload, project)
    assert p.returncode == 0 and p.stdout == "" and p.stderr == ""
    assert p.elapsed < 2.0


@pytest.mark.parametrize("name", ["session_start", "plan_gate", "style_guard", "numbers_guard", "run_logger", "completeness_check"])
def test_garbage_payload_never_crashes(project, name):
    make_run(project, phase="deliverables", deliverables=["deck.pptx"])
    (project / "runs" / RUN_ID / "state.json").write_text("{not json")
    p = run_hook(name, None, project, raw="this is not json")
    assert p.returncode == 0


# --------------------------------------------------------------------------- session_start


def test_session_start_prints_status(project):
    make_run(project, phase="review", gates=(True, True, False))
    p = run_hook("session_start", {"source": "resume"}, project)
    assert p.returncode == 0
    assert RUN_ID in p.stdout and "phase: review" in p.stdout and "review_passed=no" in p.stdout and "Next:" in p.stdout


# --------------------------------------------------------------------------- plan_gate


def test_plan_gate_blocks_analysis_before_approval(project):
    make_run(project)
    p = run_hook("plan_gate", bash(f"python runs/{RUN_ID}/code/20_analysis_primary.py"), project)
    assert p.returncode == 2
    assert "plan_approved" in p.stderr and "validation_passed" in p.stderr and "python -m abkit.state gate" in p.stderr


def test_plan_gate_allows_validation_and_reading(project):
    make_run(project)
    assert run_hook("plan_gate", bash(f"python runs/{RUN_ID}/code/10_validate_profile.py"), project).returncode == 0
    assert run_hook("plan_gate", bash(f"cat runs/{RUN_ID}/code/20_analysis_primary.py"), project).returncode == 0
    assert run_hook("plan_gate", bash("python -m abkit.state status"), project).returncode == 0


def test_plan_gate_review_gate_for_deck_and_report(project):
    make_run(project, gates=(True, True, False))
    assert run_hook("plan_gate", bash(f"python runs/{RUN_ID}/code/20_analysis_primary.py"), project).returncode == 0
    assert run_hook("plan_gate", bash(f"python runs/{RUN_ID}/code/30_charts_main.py"), project).returncode == 0
    for s in ("40_deck_build.py", "50_report_build.py"):
        p = run_hook("plan_gate", bash(f"python runs/{RUN_ID}/code/{s}"), project)
        assert p.returncode == 2 and "review_passed" in p.stderr
    make_run(project, gates=(True, True, True))
    assert run_hook("plan_gate", bash(f"python runs/{RUN_ID}/code/40_deck_build.py"), project).returncode == 0


def test_plan_gate_powershell_windows_paths(project):
    make_run(project)
    cmd = f"& python D:\\proj\\runs\\{RUN_ID}\\code\\30_charts_main.py"
    p = run_hook("plan_gate", bash(cmd, tool="PowerShell"), project)
    assert p.returncode == 2 and "30_" in p.stderr


# --------------------------------------------------------------------------- style_guard


def test_style_guard(project):
    run = make_run(project)
    f = run / "code" / "30_charts_main.py"
    f.write_text("import matplotlib.pyplot as plt\nplt.plot([1, 2])\n")
    p = run_hook("style_guard", write(f), project)
    assert p.returncode == 2 and "apply_style" in p.stderr
    f.write_text("import matplotlib.pyplot as plt\nfrom abkit.viz import apply_style\napply_style()\nplt.plot([1], color='#2251FF')\n")
    assert run_hook("style_guard", write(f), project).returncode == 0
    f.write_text("from abkit.viz import apply_style\napply_style()\nimport matplotlib.pyplot as plt\nplt.plot([1], color='#FF0000')\n")
    p = run_hook("style_guard", write(f), project)
    assert p.returncode == 2 and "#FF0000" in p.stderr
    other = project / "notes.py"
    other.write_text("import matplotlib\n")
    assert run_hook("style_guard", write(other), project).returncode == 0


def test_style_guard_passes_real_viz_modules(project):
    make_run(project)
    for name in ("charts.py", "style.py"):
        p = run_hook("style_guard", write(ROOT / "abkit" / "viz" / name), project)
        assert p.returncode == 0, p.stderr


# --------------------------------------------------------------------------- run_logger


def test_run_logger_appends(project):
    run = make_run(project)
    ok = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "python x.py", "description": "d"},
          "tool_response": {"stdout": "hi", "interrupted": False}}
    bad = {"hook_event_name": "PostToolUseFailure", "tool_name": "PowerShell", "tool_input": {"command": "python y.py"},
           "error_message": "Exit code 1"}
    assert run_hook("run_logger", ok, project).returncode == 0
    assert run_hook("run_logger", bad, project).returncode == 0
    lines = [json.loads(x) for x in (run / "run_log.jsonl").read_text().splitlines()]
    assert [x["status"] for x in lines] == ["ok", "failed"]
    assert lines[0]["command"] == "python x.py" and lines[0]["exit_code"] == 0 and lines[1]["error"] == "Exit code 1"


# --------------------------------------------------------------------------- numbers_guard

GOOD_DECK = '''"""Build deck. Lift of +3.2% in docstrings is fine."""
from pptx.util import Inches, Pt
from abkit import results as R
res = R.load_results(RUN)
p = R.get_result(res, "primary_test")
title = f"Treatment lifts conversion by {R.fmt_pct(p['rel_lift'])} ({R.fmt_p(p['p_value'])})"
share = f"{p['rel_lift']:.1%}"
box = (Inches(0.5), Pt(14), 0.65)
width_frac = 0.65
'''


def test_numbers_guard_accepts_sourced_numbers(project):
    run = make_run(project)
    f = run / "code" / "40_deck_build.py"
    f.write_text(GOOD_DECK)
    p = run_hook("numbers_guard", write(f), project)
    assert p.returncode == 0, p.stderr


@pytest.mark.parametrize("line", [
    'title = "Treatment lifts conversion by +3.2%"',
    'note = f"Significant (p = 0.004) for {metric}"',
    'lift = 0.032',
    'row = {"p_value": 0.01}',
])
def test_numbers_guard_flags_hard_coded_results(project, line):
    run = make_run(project)
    f = run / "code" / "50_report_build.py"
    f.write_text(f"metric = 'x'\n{line}\n")
    p = run_hook("numbers_guard", write(f), project)
    assert p.returncode == 2 and "results.json" in p.stderr


def test_numbers_guard_escape_hatch_and_scope(project):
    run = make_run(project)
    f = run / "code" / "40_deck_extra.py"
    f.write_text('label = "Roll out to 100% of users"  # numbers-ok\n')
    assert run_hook("numbers_guard", write(f), project).returncode == 0
    g = run / "code" / "20_analysis_primary.py"
    g.write_text('lift = 0.032\n')
    assert run_hook("numbers_guard", write(g), project).returncode == 0


# --------------------------------------------------------------------------- completeness_check


def stop(active=False):
    return {"hook_event_name": "Stop", "stop_hook_active": active}


def test_completeness_only_in_deliverables_phase(project):
    make_run(project, phase="analysis", charts=["lift_ci"], deliverables=["deck.pptx"])
    assert run_hook("completeness_check", stop(), project).returncode == 0


def test_completeness_blocks_missing_and_respects_stop_hook_active(project):
    run = make_run(project, phase="deliverables", charts=["lift_ci", "segment_forest"],
                   deliverables=["charts/", "deck.pptx", "summary.docx"])
    p = run_hook("completeness_check", stop(), project)
    assert p.returncode == 2
    for item in ("charts/", "deck.pptx", "summary.docx", "lift_ci", "segment_forest"):
        assert item in p.stderr
    assert run_hook("completeness_check", stop(active=True), project).returncode == 0
    (run / "deck.pptx").write_bytes(b"x")
    (run / "summary.docx").write_bytes(b"x")
    (run / "charts" / "manifest.json").write_text(json.dumps({"charts": [{"id": "lift_ci"}, {"id": "segment_forest"}]}))
    assert run_hook("completeness_check", stop(), project).returncode == 0


# --------------------------------------------------------------------------- settings wiring


def test_settings_wire_every_hook():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text())
    hooks = s["hooks"]
    wired = {}
    for event, groups in hooks.items():
        for g in groups:
            for h in g["hooks"]:
                script = h["command"].split("/.claude/hooks/")[1].rstrip('"')
                assert (HOOKS / script).is_file()
                wired.setdefault(script, set()).add((event, g.get("matcher")))
    assert ("PreToolUse", "Bash|PowerShell") in wired["plan_gate.py"]
    assert ("PostToolUse", "Write|Edit") in wired["style_guard.py"]
    assert ("PostToolUse", "Write|Edit") in wired["numbers_guard.py"]
    assert ("PostToolUse", "Bash|PowerShell") in wired["run_logger.py"]
    assert ("Stop", None) in wired["completeness_check.py"] and ("SessionStart", None) in wired["session_start.py"]
