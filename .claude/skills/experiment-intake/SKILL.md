---
name: experiment-intake
description: Clarifying Q&A for a new A/B test or experiment analysis. Use at the start of every experiment run (Phase 1 intake), after the user describes a problem or shares a CSV, to ask only the questions their description has not answered, show the statistical defaults, and record agreed decisions in intake.md and state.json.
---

# Experiment intake

Goal: turn the user's plain-English description (saved verbatim as `context.md`) into a complete,
unambiguous set of decisions **before** any method is chosen. Ask little, ask well.

## Procedure

1. Read `runs/.active`, then `context.md` and `state.json` of that run. Peek at the CSV header and
   10 rows (`python -c "import pandas as pd; print(pd.read_csv(path, nrows=10))"`) so you don't ask
   what the data already shows (column names, variant labels, date range).
2. Walk the question bank in [question_bank.md](question_bank.md). For every topic decide:
   **answered** (by context or data), **inferable** (state your assumption, ask to confirm), or
   **unknown** (ask).
3. Ask in **one batch** (two at most), grouped by topic, numbered, each with a suggested default
   answer in brackets so the user can reply "all defaults except 3". Never ask one question at a time.
4. Always include the statistical defaults table (below) and ask "keep or change?".
5. When answers arrive, write `intake.md` (template below) and update `state.json`:
   `metrics` (name, role, type, direction), `settings` (only overridden keys, via
   `abkit.state.set_settings`, which records `overrides`), `title`, and set phase to `planning`.
6. If an answer creates a methodological problem (e.g. "we looked at results daily and stopped
   early"), note it under **Risks flagged at intake** - the planner and reviewer read it.

## Defaults table (render from config/stat_defaults.yaml, never from memory)

```python
from abkit import state; s = state.default_settings()
```

| Setting | Default | Meaning |
|---|---|---|
| alpha | 0.05 | false-positive rate per test |
| sidedness | two-sided | detect harm as well as benefit |
| power | 0.80 | used for MDE / sample-size statements |
| correction (primary / secondary / segments) | none / holm / benjamini-hochberg | multiple-testing control |
| SRM threshold | p < 0.001 | chi-square on variant counts |
| min duration | 7 days, full weeks preferred | weekly cycles |
| Bayesian decision threshold | P(beat control) >= 0.95 | if a Bayesian readout is planned |
| bootstrap | 10,000 resamples, seed 42 | for heavy-tailed metrics |
| guardrail NI margin | 1% relative | default non-inferiority margin |

## What "answered" looks like (examples)

- "Traffic was split 50/50 at user level" -> variants, split and randomisation unit answered.
- "Primary metric is conversion; revenue per user is a guardrail" -> roles answered; type is
  inferable (binary / continuous) - confirm, don't ask.
- A `date` column spanning 14 days -> dates answered; ask only about incidents.

## intake.md template

```markdown
# Intake: <title>
## Business question
## Decision to be made
## Hypothesis
## Design
- Variants and intended split:
- Randomisation unit / analysis unit:
- Dates:
- Pre-period data:
## Metrics
| name | role | type | direction | notes |
## Segments (pre-specified)
## Known incidents
## Statistical settings (defaults kept unless listed)
## Deliverable depth
## Risks flagged at intake
## Open assumptions (confirmed by user: yes/no)
```
