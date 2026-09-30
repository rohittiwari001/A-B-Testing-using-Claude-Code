"""Decision summary for the ads-vs-PSA test: verdict vs the practical threshold, key numbers, caveats and next steps.
Step: summary.

Run from the project root:  python runs/2026-10-01_marketing-ads/code/20_analysis_summary.py
Every number in the caveats, next steps and extra key numbers is read from results.json and formatted with abkit.results.fmt_*.
Caveats are kept to about 60 words in total (deck risk slide limit); the assignment caveat stays first.
"""

from __future__ import annotations

import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN.parents[1]))

from abkit import decision, results as R, state  # noqa: E402

st = state.load_state(RUN)
s, design = st["settings"], st["design"]
CONTROL, TREATMENT = design["control"], design["treatment"]
m = next(x for x in st["metrics"] if x["role"] == "primary")
MDE = m["practical_threshold_rel"]
LABEL = m.get("label", m["name"])

res = R.load_results(RUN)
prim = R.get_result(res, "primary_test")
bayes = R.get_result(res, "bayesian")
impact = R.get_step(res, "impact")["results"]
per_k, total, share = impact[0], impact[1], impact[2]
ids = R.get_step(res, "srm")["data"]["user_id_structure"]
inter = R.get_result(res, "exposure_explore", method="segments.interaction_test")

# P(beat) is estimated from posterior draws; show it as "> 99.9%" rather than a misleading "100.0%".
PROB_DISPLAY_CAP = 0.999
prob = bayes["probability"]
prob_txt = f"> {R.fmt_prob(PROB_DISPLAY_CAP)}" if prob > PROB_DISPLAY_CAP else R.fmt_prob(prob)


def rng(r: dict, d: int = 1) -> str:
    return f"{R.fmt_num(r['ci_low'], d)} to {R.fmt_num(r['ci_high'], d)}"


psa_ids = f"{R.fmt_num(ids[CONTROL]['min'])} to {R.fmt_num(ids[CONTROL]['max'])}"
split = R.get_result(res, "srm")["extra"]
split_now = split["intended_split"]
split_orig = (split.get("originally_stated_split") or {}).get("split")
bucket_rows = [r for r in R.get_step(res, "exposure_explore")["results"]
               if (r.get("extra") or {}).get("segment_col") == "total ads bucket"]
n_inconclusive = sum(not r["significant"] for r in bucket_rows)
guardrails = [x for x in st["metrics"] if x["role"] == "guardrail"]

caveats = [f"{CONTROL.upper()} ids form a separate block ({psa_ids}); assignment unconfirmed."]
if split_orig:
    caveats.append(f"Split confirmed as {split_now} only after a {split_orig} check failed.")
caveats += [
    f"Exposure breakdowns are exploratory, non-causal; {n_inconclusive} of {len(bucket_rows)} buckets inconclusive.",
    "No dates: novelty or wear-off cannot be checked.",
]
if not guardrails:
    caveats.append(f"No guardrail metrics defined; verdict rests on {LABEL} alone.")
caveats.append("Money impact needs a value per conversion.")
if prim["rel_ci_low"] < MDE:  # only relevant if the CI reaches below the practical threshold
    caveats.append(f"The lift range ({R.fmt_ci(prim['rel_ci_low'], prim['rel_ci_high'])}) includes values below "
                   f"the {R.fmt_pct(MDE)} threshold.")

next_steps = [
    f"Keep ads running: about {R.fmt_num(per_k['estimate'], 1)} extra conversions per 1,000 users "
    f"({rng(per_k)}).",
    "Data owner: confirm random assignment to ads vs PSA before scaling spend.",
    f"Agree a value per conversion to price the {R.fmt_num(total['estimate'])} extra conversions.",
    "Test ad frequency in a new randomised test before changing it.",
    "Keep a small PSA holdout when scaling to track the lift.",
]

extra = [
    {"label": "Incremental conversions per 1,000 users", "value": f"{R.fmt_num(per_k['estimate'], 1)} (95% CI {rng(per_k)})"},
    {"label": f"P({TREATMENT}s beat {CONTROL.upper()})", "value": prob_txt},
]

summary = decision.build_summary(
    RUN, "primary_test", __file__, mde_rel=MDE, direction=m["direction"], metric_label=LABEL,
    caveats=caveats, next_steps=next_steps, extra_key_numbers=extra, prob_threshold=s["bayes_decision_threshold"],
    treatment_label="the ad campaign", control_label="the PSA",   # display names for stakeholders
)
state.set_step_status(RUN, "summary", "done")

print(f"verdict: {summary['verdict_label']} - {summary['reason']}")
print("headline:", summary["headline"])
print("plain:", summary["plain_english"])
for k in summary["key_numbers"]:
    print(f"  {k['label']}: {k['value']}")
print("caveats (words):", [len(c.split()) for c in summary["caveats"]], "total", sum(len(c.split()) for c in summary["caveats"]))
for c in summary["caveats"]:
    print("  -", c)
for n in summary["next_steps"]:
    print("  >", n)
