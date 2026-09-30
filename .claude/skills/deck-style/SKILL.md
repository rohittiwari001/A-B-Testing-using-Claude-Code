---
name: deck-style
description: Structure, slide types, layout and wording rules for the experiment readout deck (deck.pptx) built with abkit.deck (python-pptx, 16:9, no template file). Use when building, extending or reviewing a deck for an experiment run (deck-builder agent, 40_deck_*.py scripts).
---

# Deck style

## Build it with abkit

```python
"""Build deck.pptx for <run>."""
from pathlib import Path
from abkit.deck import build_standard_deck
RUN = Path(__file__).resolve().parents[1]
print(build_standard_deck(RUN))       # sections from state.plan.deck_sections
```

`build_standard_deck` reads `state.json` (sections, title, settings), `results.json` (summary, results, validation)
and `charts/manifest.json` (chart slides, takeaways). For custom slides use `abkit.deck.Deck` primitives inside
the same script, reading every number from results.json. Never type a number into a slide.

## Slide types (abkit.deck.Deck)

| Method | Slide |
|---|---|
| `title_slide` | title, subtitle (the headline), date |
| `exec_summary` | verdict box (positive / negative / neutral colour) + 3-5 bullets with numbers |
| `section` | navy divider |
| `chart` | chart at ~65% width, three numbered takeaways on the right (chart's own title band cropped) |
| `two_charts` | two charts side by side with one-line captions |
| `table` | navy header row, status column coloured |
| `bullets(kind=...)` | methodology, risks, next steps (numbered), appendix text |

Every slide: action title (max two lines), content, footer with source note and slide number.
Speaker notes on every content slide explaining its key point.

## Default section order (state.plan.deck_sections)

title -> `exec_summary` -> `setup` -> `results` (primary) -> `secondary` / `guardrails` -> `segments` (if planned)
-> `time` / `power` (if planned) -> `risks` -> `next_steps` -> `appendix` (methodology, validation, full tables).

Size to the problem:
- Power analysis: exec_summary, setup, power, next_steps (5-6 slides).
- SRM blocked: exec_summary (verdict "Blocked: data issue"), validation, next_steps.
- Standard readout: the default list (12-16 slides).
- Deep dive: add segments, time, secondary and a longer appendix.

## Wording rules
- Action titles state the takeaway with the number ("Treatment lifts conversion by +3.2%, statistically significant").
- About 40 words of body text per slide maximum; the builder writes `deck_warnings.txt` when exceeded - fix them.
- Percentages to one decimal with sign for changes (+3.2%); p-values to three decimals or "<0.001"
  (`abkit.results.fmt_pct`, `fmt_p`, `fmt_ci`).
- Say "inconclusive", not "no effect", when the CI includes the practical threshold.
- Recommendations name an action and, when known, an owner and a date.
- Consistent terms: the variant labels from the data, metric names as agreed at intake.
