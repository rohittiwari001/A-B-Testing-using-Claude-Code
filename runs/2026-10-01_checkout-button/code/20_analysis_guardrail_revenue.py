"""Guardrail: non-inferiority of revenue per user (margin from settings, one-sided). Step: guardrail_revenue."""

from pathlib import Path

from abkit import frequentist, io, results, state

RUN = Path(__file__).resolve().parents[1]
st = state.load_state(RUN)
s = st["settings"]
margin = next(m.get("ni_margin_rel", s["noninferiority_margin_relative"]) for m in st["metrics"] if m["name"] == "revenue")
df = io.load_run_csv(RUN)

c = df.loc[df.variant == "control", "revenue"]
t = df.loc[df.variant == "treatment", "revenue"]
g = frequentist.noninferiority_test(c, t, margin_rel=margin, direction="no_decrease", alpha=s["alpha"], metric="revenue")
g.extra["variant_stats"] = {"control": frequentist.mean_ci(c.to_numpy(), s["alpha"]), "treatment": frequentist.mean_ci(t.to_numpy(), s["alpha"])}
results.add_result(RUN, "guardrail_revenue", g, __file__)
state.set_step_status(RUN, "guardrail_revenue", "done")
print(results.describe(g.to_dict()), "| status:", g.extra["status"])
