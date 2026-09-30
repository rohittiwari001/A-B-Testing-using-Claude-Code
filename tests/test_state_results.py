import json

import pytest

from abkit import results, state


def test_new_run_creates_layout_and_activates(tmp_root, demo_csvs):
    run = state.new_run("Checkout Button!", "context text", demo_csvs / "checkout_ab.csv")
    assert run.name.endswith("_checkout-button")
    for sub in ("data", "code", "charts"):
        assert (run / sub).is_dir()
    assert (run / "data" / "checkout_ab.csv").is_file()
    assert (run / "context.md").read_text().startswith("context text")
    assert state.active_run_id() == run.name
    st = state.load_state()
    assert st["phase"] == "intake" and st["gates"] == {g: False for g in state.GATES}
    assert st["settings"]["alpha"] == 0.05 and st["settings"]["srm_threshold"] == 0.001


def test_duplicate_slug_gets_suffix(tmp_root):
    a = state.new_run("x", "c")
    b = state.new_run("x", "c")
    assert a != b and b.name.endswith("-2")


def test_validate_state_catches_problems(tmp_root):
    run = state.new_run("x", "c")
    st = state.load_state(run)
    assert state.validate_state(st) == []
    st["phase"] = "cooking"
    st["metrics"] = [{"name": "m", "role": "hero", "type": "binary", "direction": "increase"}]
    st["settings"]["correction_secondary"] = "magic"
    errs = state.validate_state(st)
    assert any("phase" in e for e in errs)
    assert any("role" in e for e in errs)
    assert any("correction_secondary" in e for e in errs)
    with pytest.raises(state.StateError):
        state.save_state(run, st)


def test_gates_steps_settings_and_reset(tmp_root):
    run = state.new_run("x", "c")
    st = state.load_state(run)
    st["plan"]["steps"] = [{"id": "srm", "method": "validation.srm_check", "status": "pending"}]
    state.save_state(run, st)
    state.set_gate(run, "plan_approved", True)
    state.set_gate(run, "validation_passed", True)
    state.set_step_status(run, "srm", "done")
    state.set_settings(run, alpha=0.01)
    st = state.load_state(run)
    assert st["gates"]["plan_approved"] and st["plan"]["steps"][0]["status"] == "done"
    assert st["settings"]["alpha"] == 0.01 and st["overrides"]["alpha"]["from"] == 0.05
    st = state.reset_downstream(run, "validation")
    assert st["gates"]["plan_approved"] and not st["gates"]["validation_passed"]
    with pytest.raises(state.StateError):
        state.set_gate(run, "nope", True)


def test_switch_and_clear_active(tmp_root):
    a = state.new_run("a", "c")
    b = state.new_run("b", "c")
    state.set_active(a.name)
    assert state.active_run_id() == a.name
    assert state.list_runs() == sorted([a.name, b.name])
    state.set_active(None)
    assert state.active_run_id() is None
    with pytest.raises(state.StateError):
        state.set_active("missing")


def test_results_roundtrip_and_traceability(tmp_root):
    import numpy as np

    run = state.new_run("x", "c")
    r = results.StatResult(method="welch_ttest", estimate=np.float64(0.5), p_value=float("nan"), n={"a": np.int64(3)})
    results.add_result(run, "primary", r, script=str(run / "code" / "20_analysis_primary.py"), data={"arr": np.arange(3)})
    res = json.loads((run / "results.json").read_text())
    step = res["steps"]["primary"]
    assert step["script"] == "code/20_analysis_primary.py"
    assert step["results"][0]["abs_lift"] == 0.5 and step["results"][0]["p_value"] is None
    assert step["data"]["arr"] == [0, 1, 2]
    assert results.get_result(run, "primary")["n"] == {"a": 3}
    with pytest.raises(KeyError):
        results.get_step(run, "missing")
    bad = results.load_results(run)
    bad["steps"]["x"] = {"results": []}
    with pytest.raises(ValueError):
        results.save_results(run, bad)


def test_formatting():
    assert results.fmt_pct(0.0321) == "+3.2%"
    assert results.fmt_pct(-0.004) == "\u22120.4%"
    assert results.fmt_p(0.0004) == "<0.001" and results.fmt_p(0.0456) == "0.046"
    assert results.fmt_pp(0.0042) == "+0.4 pp"
    assert results.fmt_num(12345.678) == "12,346"
    assert results.fmt_value(0.3456, "binary") == "34.56%"


def test_state_cli(tmp_root, demo_csvs, capsys):
    assert state._cli(["new", "cli-test", "--csv", str(demo_csvs / "checkout_ab.csv")]) == 0
    assert state._cli(["status"]) == 0
    out = capsys.readouterr().out
    assert "phase: intake" in out and "Next:" in out
    assert state._cli(["validate"]) == 0
    assert state._cli(["gate", "plan_approved", "true"]) == 0
    assert state.load_state()["gates"]["plan_approved"] is True
    assert state._cli(["phase", "analysis"]) == 0 and state.load_state()["phase"] == "analysis"
    assert state._cli(["reset", "planning"]) == 0 and state.load_state()["gates"]["plan_approved"] is False
    assert state._cli(["switch", "missing"]) == 2
