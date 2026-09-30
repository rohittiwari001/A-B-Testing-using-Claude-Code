"""CUPED-adjusted Welch test of minutes per user using pre_minutes. Step: cuped_test."""

from pathlib import Path

from abkit import frequentist, io, results, state, variance_reduction

RUN = Path(__file__).resolve().parents[1]
s = state.load_state(RUN)["settings"]
df = io.load_run_csv(RUN)

r = variance_reduction.cuped(df, "minutes", "pre_minutes", "variant", "control", "treatment", s["alpha"],
                             frequentist.alternative_for(s["sidedness"], "increase"), role="primary")
r.correction = s["correction_primary"]
r.notes.append("CUPED chosen after the unadjusted result was seen (not pre-registered); both are reported.")
results.add_result(RUN, "cuped_test", r, __file__)
state.set_step_status(RUN, "cuped_test", "done")
print(results.describe(r.to_dict()))
print(f"theta {r.extra['theta']:.3f} | corr {r.extra['correlation']:.3f} | variance reduction {r.extra['variance_reduction']:.1%}")
