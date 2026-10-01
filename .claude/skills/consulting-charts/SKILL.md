---
name: consulting-charts
description: The house visual system for experiment charts - palette tokens, Arial typography, action-title rules with good and bad examples, the 15-chart catalogue in abkit.viz.charts, section tags for the deck, and a pre-save checklist. Use whenever creating, editing or reviewing any chart for an experiment run (viz-designer, 30_charts_*.py scripts) or when a user asks for a new chart.
---

# Consulting charts

Charts from any run must look like they came from the same team. Everything below is implemented in
`abkit/viz`; never restyle by hand.

## Visual system (abkit/viz/style.py)

| Token | Hex | Use |
|---|---|---|
| ink | #1A1A1A | titles, primary text |
| navy | #0B2545 | control / baseline series |
| accent | #2251FF | the one thing to look at (treatment, key bar) |
| accent_light | #9DB4FF | secondary treatment arms |
| grey_mid | #8C8C8C | context series, axis labels, notes |
| grey_light | #E3E3E3 | gridlines, dividers, CI bands |
| positive | #1B7F5A | significant positive result |
| negative | #C0392B | significant negative result, guardrail breach |
| neutral | #B08900 | inconclusive |

- Font: Arial (fallback Helvetica, Liberation Sans, DejaVu Sans). Title 14 pt bold, subtitle 11 pt grey_mid,
  axis labels and annotations 10 pt, source 8 pt. 10 x 5.625 in (16:9), PNG 300 dpi + SVG.
- Variant colours come from `variant_colors(variants, control)`: control navy, first treatment accent, then
  accent_light, grey_mid. Same mapping in every chart of a run.
- Status colours come from `status_color(result)`. Positive vs negative is only moderately separable for
  colour-blind readers, so every status also carries a text label or a filled / hollow marker.
- Mostly greys; at most four colours per chart. No borders, no top/right spines, light horizontal grid only,
  no 3-D, no pie charts. Direct labels instead of legends where possible. CIs always shown for estimates.

## Script template (30_charts_<name>.py)

```python
"""Charts for <run>: <which charts>."""
from pathlib import Path
from abkit import results as R
from abkit.viz import apply_style, charts, save_chart

apply_style()
RUN = Path(__file__).resolve().parents[1]
res = R.load_results(RUN)
p = R.get_result(res, "primary_test")
src = f"Source: {csv_name}, {start} to {end}; two-proportion z-test; n = {sum(p['n'].values()):,}"   # from results/validation
title = f"Treatment lifts conversion by {R.fmt_pct(p['rel_lift'])}, statistically significant"
fig = charts.lift_ci([{**p, "metric": "Conversion"}], title, "Relative lift vs control, 95% CI", src)
save_chart(fig, RUN, "lift_ci", title, key_message=f"Conversion {R.fmt_pct(p['rel_lift'])}",
           subtitle="Relative lift vs control, 95% CI", source=src, section="results",
           takeaways=[f"Lift {R.fmt_pct(p['rel_lift'])} ...", "...", "..."])
```

Every number in a title, subtitle, takeaway or label is formatted from results.json with `abkit.results.fmt_*`.
Interval levels too: build "95% CI" from the run's alpha (`f"{1 - alpha:.0%} CI"`; non-inferiority `1 - 2*alpha`), never
type it - a follow-up like "rerun with alpha 0.01" must relabel every chart.
`save_chart` writes PNG + SVG and upserts `charts/manifest.json` (id, title, subtitle, key_message,
takeaways, section, source, title_crop).

## Action titles

The title states the takeaway, in one sentence, max two lines (about 88 characters per line).

| Bad (topic title) | Good (action title) |
|---|---|
| Conversion by variant | Variant B lifts checkout conversion by 3.2%, statistically significant |
| Segment results | The lift is concentrated on iOS; Android and Web show no significant change |
| Daily lift | The lift fell from +9% in week one to +4%: a novelty effect |
| SRM check | Treatment is missing 7% of its expected users: results cannot be trusted yet |
| Power curve | About 34,000 users per variant give 80% power for a +3% lift |

Rules: lead with the subject and the verb; include the number; say "significant" / "not significant" /
"inconclusive" explicitly; no hedging words ("seems", "appears"); never a question.
Subtitle: metric, unit, interval type ("Relative lift vs control, 95% CI"). Source line: data file, dates,
test used, n.

## Chart catalogue (abkit.viz.charts)

| id | Use for | Input from results.json | Default section |
|---|---|---|---|
| lift_ci | relative lift + CI for several metrics / arms | result dicts | results |
| metric_by_variant | level of the primary metric per variant | `extra.variant_stats` | results |
| cumulative_daily | did the lead hold over time | `time_effects.cumulative_effects` records | time |
| daily_lift | novelty / primacy | `time_effects.effects_by` records | time |
| segment_forest | lift by segment with "All" row | segment result dicts | segments |
| power_curve | power vs n for several MDEs | `power.power_curve` records | power |
| sample_size_vs_mde | n (and days) per MDE | `power.sample_size_table` records | power |
| posterior_distributions | Bayesian posteriors per variant | `extra.posteriors` | results |
| prob_to_beat_control | P(beat) with threshold | `probability` per arm | results |
| srm_bar | observed vs intended split | `srm_check` extra | validation |
| distribution_compare | distribution shape (hist / ECDF) | `charts.histogram_data` stored in step data | appendix |
| cuped_variance_reduction | CI width before vs after CUPED | cuped `extra` | results |
| sequential_boundaries | boundaries + observed z path | `sequential.boundaries` records | results |
| guardrail_scorecard | PASS / BREACH / INCONCLUSIVE table | guardrail result dicts | guardrails |
| did_trends | treated vs control with launch line | `quasi.group_trends` records | results |

Sections used by the deck and report: setup, validation, results, secondary, guardrails, segments, time,
power, appendix. In the deck, charts fill the Findings chapter of the fixed storyline (deck-style skill) in the
order they are saved: save the headline chart of each section first. Pass `tag="Exploratory"` (or "Preliminary",
"Directional") to `save_chart` for non-confirmatory evidence; the slide shows it as an amber sticker. A chart not in
the catalogue: build it with `new_figure()` + `finalize()` + palette tokens and flag it as a promotion candidate.

## Pre-save checklist
- [ ] `apply_style()` called (the style_guard hook enforces it) and colours only from `PALETTE`.
- [ ] Action title states the takeaway with a number; max two lines.
- [ ] Subtitle names metric, unit and interval; source line names file, dates, test, n.
- [ ] CIs shown for every estimate; zero line on lift charts.
- [ ] Key element in accent or a status colour; everything else grey / navy.
- [ ] Direct labels readable, nothing overlapping (open the PNG and look).
- [ ] Every number traceable to results.json; `save_chart` used so the manifest is updated with takeaways.
