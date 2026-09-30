"""Blocked readout summary: verdict 'Blocked: data issue' built from the validation and SRM localisation results. Step: summary."""

from pathlib import Path

from abkit import decision, results, state

RUN = Path(__file__).resolve().parents[1]
res = results.load_results(RUN)
loc = results.get_step(res, "srm_localise")
android = results.get_result(res, "srm_localise", segment="Android")
rest = results.get_result(res, "srm_localise", segment="iOS + Web")
gap = loc["data"]["android_late_gap_units"]

caveats = [
    f"iOS + Web alone show no mismatch ({results.fmt_p_stat(rest['p_value'])}), but an iOS + Web-only readout would answer a "
    "different question (it excludes a whole platform); treat it as a sensitivity check only.",
    "Activation results were not computed: with units missing non-randomly, any difference could be caused by the loss.",
]
next_steps = [
    f"Engineering: fix the Android exposure event lost since the 2026-09-05 release (about {gap:,} treatment users missing)",
    "Re-extract exposures from server-side assignment logs and rerun this workflow on the corrected data",
    "If the logs cannot be repaired, rerun the test for two full weeks after the fix",
    "Add an automated daily SRM alert (by platform) to the experiment dashboard",
]
decision.build_blocked_summary(RUN, __file__, next_steps=next_steps, caveats=caveats)
state.set_step_status(RUN, "summary", "done")
print(results.load_results(RUN)["summary"]["headline"])
print("Android-only SRM:", results.fmt_p_stat(android["p_value"]))
