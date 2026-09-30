"""Charts for 2026-10-01_marketing-ads: segment_forest by ads-seen bucket (exploratory, not causal).

Run from the project root:  python runs/2026-10-01_marketing-ads/code/30_charts_segments.py
Uses the pre-ordered rows in step `exposure_explore` data.segment_forest (All first, buckets in numeric order).
The interaction-test row is not plotted (its estimate is a chi-square statistic, not a lift).
"""

import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN.parents[1]))

from abkit import results as R  # noqa: E402
from abkit import state  # noqa: E402
from abkit.viz import apply_style, charts, save_chart  # noqa: E402

apply_style()
res = R.load_results(RUN)
st = state.load_state(RUN)
alpha = st["settings"]["alpha"]
ci = f"{1 - alpha:.0%} CI"
csv_name = Path(st["input_csv"]).name

step = R.get_step(res, "exposure_explore")
data = step["data"]
FAMILY = "total ads bucket"
order = data["segment_order"][FAMILY]
by_seg = {r["segment"]: r for r in data["segment_forest"][FAMILY] if r.get("rel_lift") is not None}
rows = [by_seg[s] for s in order if s in by_seg]           # numeric bucket order, "All" first
buckets = [r for r in rows if r["segment"] != "All"]
overall = next(r for r in rows if r["segment"] == "All")
sig = [r for r in buckets if r["significant"]]
insig = [r for r in buckets if not r["significant"]]
plot_rows = [r if r["segment"] == "All" else {**r, "segment": f"{r['segment']} ads"} for r in rows]   # "All" stays on top


def join(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


sig_names = join([r["segment"] for r in sig])
insig_names = join([r["segment"] for r in insig])
n_total = sum(overall["n"].values())
corr = data["correction"]["method"].replace("benjamini-hochberg", "Benjamini-Hochberg")
src = (f"Source: {csv_name} (no dates); z-test per bucket, {corr} across {len(buckets)} buckets; "
       f"n = {n_total:,} users")

t = (f"Exploratory, not causal: lift significant only at {sig_names} ads seen; "
     f"{len(insig)} of {len(buckets)} buckets inconclusive")
sub = f"Relative conversion lift, Ads vs PSA, by ads seen, {ci}. Ads seen is measured during the test, not assigned"
fig = charts.segment_forest(plot_rows, t, sub, src)
fig.axes[0].set_xlabel("Relative lift, Ads vs PSA")
bal_p = data["covariate_balance_p"][FAMILY]
save_chart(fig, RUN, "segment_forest", t,
           f"Exploratory: lift significant in {len(sig)} of {len(buckets)} ads-seen buckets (not causal)", sub, src,
           section="segments",
           takeaways=[f"Significant: {sig_names} ads "
                      f"({', '.join(R.fmt_pct(r['rel_lift']) for r in sig)})",
                      f"Inconclusive: {insig_names} ads - wide intervals, not no effect",
                      f"Ads seen reflects behaviour; PSA share varies by bucket ({R.fmt_p_stat(bal_p)}): "
                      f"not dose-response"],
           notes="speaker note: descriptive only - heavier-exposure users are different people, so this does not show that "
                 "more ads cause more lift.")
print("segment chart saved")
