"""Unadjusted comparison of minutes per user: Welch t-test plus a bootstrap check. Step: naive_test."""

from pathlib import Path

from abkit import frequentist, io, results, state
from abkit.viz.charts import histogram_data

RUN = Path(__file__).resolve().parents[1]
s = state.load_state(RUN)["settings"]
df = io.load_run_csv(RUN)
c, t = df.loc[df.variant == "control", "minutes"], df.loc[df.variant == "treatment", "minutes"]

welch = frequentist.welch_ttest(c, t, s["alpha"], frequentist.alternative_for(s["sidedness"], "increase"), metric="minutes")
welch.role = "sensitivity"
boot = frequentist.bootstrap_diff(c, t, "mean", s["bootstrap_n_resamples"], s["bootstrap_seed"], s["alpha"], metric="minutes")
boot.role = "sensitivity"
results.add_result(RUN, "naive_test", [welch, boot], __file__, method="frequentist.welch_ttest",
                   data={"histogram": histogram_data(df, "minutes", "variant", bins=40, clip_quantile=0.99)})
state.set_step_status(RUN, "naive_test", "done")
print(results.describe(welch.to_dict()))
print(results.describe(boot.to_dict()))
