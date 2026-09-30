"""Revenue sensitivity: Welch vs percentile bootstrap for revenue per user, plus distribution data. Step: revenue_sensitivity."""

from pathlib import Path

from abkit import frequentist, io, results, state
from abkit.viz.charts import histogram_data

RUN = Path(__file__).resolve().parents[1]
s = state.load_state(RUN)["settings"]
df = io.load_run_csv(RUN)

c = df.loc[df.variant == "control", "revenue"]
t = df.loc[df.variant == "treatment", "revenue"]
welch = frequentist.welch_ttest(c, t, s["alpha"], metric="revenue")
welch.role = "sensitivity"
boot = frequentist.bootstrap_diff(c, t, "mean", s["bootstrap_n_resamples"], s["bootstrap_seed"], s["alpha"], metric="revenue")
boot.role = "sensitivity"
hist = histogram_data(df, "revenue", "variant", bins=40, clip_quantile=0.99, drop_zeros=True)
agree = abs((boot.ci_high - boot.ci_low) / (welch.ci_high - welch.ci_low) - 1)
results.add_result(RUN, "revenue_sensitivity", [welch, boot], __file__,
                   data={"histogram_buyers": hist, "ci_width_ratio_minus_1": agree})
state.set_step_status(RUN, "revenue_sensitivity", "done")
print(results.describe(welch.to_dict()))
print(results.describe(boot.to_dict()))
