# Interpretation and decisions

## When to use
Every readout, at the end: turning estimates into ship / don't ship / iterate / extend, and wording the result.

## Assumptions
- A practical threshold (MDE) exists; if not, ask for one at intake or use the MDE the test was powered for.
- Guardrail statuses and the primary result come from results.json.

## Step-by-step procedure
1. Check validity first: SRM passed, correct unit, planned correction applied, no unplanned peeking.
2. `decision.recommend(primary, guardrails, mde_rel, direction)`:
   - primary significantly worse -> **don't ship**;
   - any guardrail breached -> **don't ship** (or **iterate** if the primary won: fix the side effect);
   - primary significantly better and lift >= MDE -> **ship**;
   - significant but below the MDE -> **iterate** (real but small; weigh cost of shipping / maintaining);
   - not significant and the CI excludes the MDE -> **iterate** (well-powered null: the idea does not move the metric);
   - not significant and the CI still includes the MDE -> **extend** (inconclusive; more data needed).
3. `decision.build_summary(run_dir, primary_step, script, guardrail_step, mde_rel, next_steps=[...], metric_label=...)`
   writes the verdict, headline, plain-English sentence, key numbers and caveats into results.json.
4. Add caveats: novelty, heavy tails, inconclusive guardrails, exploratory segments, external validity (season, population).

## abkit function(s)
`decision.recommend`, `decision.build_summary`, `decision.plain_english`, `bayesian.decide`.

## How to interpret
- Statistical significance = unlikely to be noise. Practical significance = big enough to matter. You need both to ship.
- Inconclusive is not "no effect": state the range the CI allows ("between -0.5% and +3.9%").
- Effects from winning tests are biased upward (winner's curse); expect somewhat smaller effects after rollout.

## Common pitfalls
- "p = 0.06, so no effect". Say "inconclusive" and give the CI.
- "p = 0.001, so a big effect". p says nothing about size.
- Headlining a secondary or segment result when the primary failed.
- Ignoring the cost side (engineering, complexity) when the effect is small.

## How to present it
Executive summary slide: verdict box coloured positive / negative / neutral, then 3-5 bullets with numbers.
Wording templates:
- Ship: "Treatment raises conversion by +3.2% (95% CI +1.2% to +5.2%), above the 2% threshold, with no guardrail harm. Ship."
- Extend: "The result is inconclusive: the lift could be anywhere from -0.5% to +3.9%. Run two more weeks to reach the planned power."
- Iterate: "The change does not move conversion meaningfully (CI -0.4% to +0.9%, below the 2% threshold). Rework the idea."
