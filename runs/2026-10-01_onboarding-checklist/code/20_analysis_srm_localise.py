"""SRM localisation: split counts by platform and by period (before / from 2026-09-05). Step: srm_localise."""

from pathlib import Path

import pandas as pd

from abkit import io, results, state, validation

RUN = Path(__file__).resolve().parents[1]
s = state.load_state(RUN)["settings"]
df = io.load_run_csv(RUN)
exp = {"control": 0.5, "treatment": 0.5}
release = pd.Timestamp("2026-09-05")          # Android release date given at intake
df["period"] = (pd.to_datetime(df["exposure_date"]) >= release).map({False: "before 2026-09-05", True: "from 2026-09-05"})
df["cell"] = df["platform"] + " / " + df["period"]

rows = []
for col in ("platform", "period", "cell"):
    rows.extend(validation.srm_by(df, "variant", col, exp, s["srm_threshold"]).rename(columns={col: "level"}).assign(by=col).to_dict("records"))
android = df[df.platform == "Android"]
srm_android = validation.srm_check(android, "variant", exp, s["srm_threshold"])
srm_android.segment = "Android"
rest = validation.srm_check(df[df.platform != "Android"], "variant", exp, s["srm_threshold"])
rest.segment = "iOS + Web"
android_late = android[android.period == "from 2026-09-05"]
missing_late = int(round(android_late[android_late.variant == "control"].shape[0] - android_late[android_late.variant == "treatment"].shape[0]))
results.add_result(RUN, "srm_localise", [srm_android, rest], __file__, method="validation.srm_by",
                   data={"table": rows, "android_late_gap_units": missing_late})
state.set_step_status(RUN, "srm_localise", "done")
print("Android", results.fmt_p_stat(srm_android.p_value), "| iOS+Web", results.fmt_p_stat(rest.p_value), "| Android late gap:", missing_late)
