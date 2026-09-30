"""Platform segments: per-platform lift (BH-corrected), interaction test, Simpson's check. Step: segments_platform."""

from pathlib import Path

from abkit import io, results, segments, state

RUN = Path(__file__).resolve().parents[1]
s = state.load_state(RUN)["settings"]
df = io.load_run_csv(RUN)

rows = segments.segment_effects(df, "converted", "binary", "platform", "variant", "control", "treatment",
                                s["alpha"], s["correction_segments"])
inter = segments.interaction_test(df, "converted", "platform", "variant", "control", "treatment", s["alpha"])
simp = segments.simpsons_check(df, "converted", "platform", "variant", "control", "treatment")
results.add_result(RUN, "segments_platform", [*rows[1:], inter, simp], __file__, method="segments.segment_effects",
                   data={"overall": rows[0].to_dict()})
state.set_step_status(RUN, "segments_platform", "done")
for r in rows[1:]:
    print(r.segment, results.describe(r.to_dict()))
print("interaction", results.fmt_p_stat(inter.p_value), "| simpson flagged:", simp.extra["flagged"])
