"""Sensitivity: Lin (2013) regression adjustment with pre_minutes, HC2 robust SEs. Step: regression_check."""

from pathlib import Path

from abkit import io, results, state, variance_reduction

RUN = Path(__file__).resolve().parents[1]
s = state.load_state(RUN)["settings"]
df = io.load_run_csv(RUN)

r = variance_reduction.regression_adjustment(df, "minutes", ["pre_minutes"], "variant", "control", "treatment", s["alpha"],
                                             role="sensitivity")
results.add_result(RUN, "regression_check", r, __file__)
state.set_step_status(RUN, "regression_check", "done")
print(results.describe(r.to_dict()), f"| R^2 {r.extra['r_squared']:.3f}")
