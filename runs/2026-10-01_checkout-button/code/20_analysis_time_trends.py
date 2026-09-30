"""Stability over time: cumulative conversion by day, daily lift, and a trend test for novelty. Step: time_trends."""

from pathlib import Path

from abkit import io, results, state, time_effects

RUN = Path(__file__).resolve().parents[1]
s = state.load_state(RUN)["settings"]
df = io.load_run_csv(RUN)

cum = time_effects.cumulative_effects(df, "converted", "binary", "exposure_date", "variant", "control", "treatment", s["alpha"])
daily = time_effects.daily_effects(df, "converted", "binary", "exposure_date", "variant", "control", "treatment", s["alpha"])
trend = time_effects.trend_test(daily, alpha=s["alpha"])
trend.metric = "converted"
results.add_result(RUN, "time_trends", trend, __file__, method="time_effects.cumulative_effects",
                   data={"cumulative": cum, "daily": daily})
state.set_step_status(RUN, "time_trends", "done")
print(trend.extra["pattern"], "| slope p:", results.fmt_p(trend.p_value))
