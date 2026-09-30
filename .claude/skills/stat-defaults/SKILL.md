---
name: stat-defaults
description: Explains the standard statistical settings in config/stat_defaults.yaml (alpha, sidedness, power, corrections, SRM threshold, duration, Bayesian threshold, bootstrap, guardrail margin), when deviating is reasonable, and how to record overrides in state.json. Use at intake when showing defaults, whenever a user asks to change a setting (e.g. "rerun with alpha 0.01"), and when reviewing whether settings were applied.
---

# Statistical defaults

Source of truth: `config/stat_defaults.yaml`. Load with `abkit.state.default_settings()` (flattened into the
`state.json` settings shape). Never quote defaults from memory.

| YAML key | state.json key | Default | Reasonable deviations |
|---|---|---|---|
| alpha | alpha | 0.05 | 0.01 for high-risk / irreversible launches or many primary decisions; 0.10 for cheap, reversible UI tweaks (say so) |
| sidedness | sidedness | two-sided | one-sided only for pre-registered non-inferiority or when harm is impossible to act on - decided before data |
| power | power | 0.80 | 0.90 for decisions that are expensive to revisit |
| confidence_level | confidence_level | 0.95 | tied to alpha (1 - alpha) |
| correction.primary | correction_primary | none | keep none: one pre-registered primary |
| correction.secondary | correction_secondary | holm | bonferroni if the family must be reported with simultaneous CIs |
| correction.segments | correction_segments | benjamini-hochberg | holm when a segment result will drive a rollout decision |
| srm.threshold | srm_threshold | 0.001 | 0.01 for small tests where SRM is costly to miss |
| duration.min_days / prefer_full_weeks | min_days / prefer_full_weeks | 7 / true | never below 7 without a strong reason (weekday effects) |
| bayesian.prior | bayes_prior | weakly_informative | flat for sensitivity; informative only with documented, shrunk history |
| bayesian.decision_threshold_prob_beat | bayes_decision_threshold | 0.95 | 0.90 with an explicit expected-loss rule for cheap changes |
| bootstrap.n_resamples / seed | bootstrap_n_resamples / bootstrap_seed | 10000 / 42 | 2000 for quick exploration |
| guardrails.default_noninferiority_margin_relative | noninferiority_margin_relative | 0.01 | per-guardrail margins agreed with the metric owner |

## Recording overrides

```python
from abkit import state
state.set_settings(run_dir, alpha=0.01)        # updates settings and records overrides.alpha = {from, to, at}
```

- Only change settings through `set_settings` so `state.json.overrides` keeps the audit trail; the report
  appendix lists overrides.
- A setting change after results were seen is a follow-up: rerun the affected phases (analysis, review,
  deliverables) and mention in the summary that the setting changed and why.
- Record the reason in `intake.md` under "Statistical settings".
