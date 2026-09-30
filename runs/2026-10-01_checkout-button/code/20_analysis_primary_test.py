"""Primary metric: two-proportion z-test on checkout conversion (user level). Step: primary_test."""

from pathlib import Path

from abkit import frequentist, io, results, state

RUN = Path(__file__).resolve().parents[1]
s = state.load_state(RUN)["settings"]
df = io.load_run_csv(RUN)

alt = frequentist.alternative_for(s["sidedness"], "increase")
r = frequentist.compare(df, "converted", "binary", "variant", "control", "treatment", s["alpha"], alt, role="primary")
r.correction = s["correction_primary"]
results.add_result(RUN, "primary_test", r, __file__)
state.set_step_status(RUN, "primary_test", "done")
print(results.describe(r.to_dict()))
