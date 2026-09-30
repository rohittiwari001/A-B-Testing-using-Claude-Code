---
name: ab-methods
description: Core A/B testing methods library - maps problem types and metric types to statistical methods, with one reference file per concept (power/MDE, frequentist tests, Bayesian, SRM, CUPED, sequential testing, ratio metrics/delta method, multiple testing, multi-arm, heterogeneous effects, novelty, guardrails, quasi-experiments, interpretation and decisions). Use when planning an experiment analysis, choosing or executing a method, reviewing an analysis, or answering any general A/B testing or experimentation statistics question.
---

# A/B testing methods: index

Every reference file has the same sections: When to use, Assumptions, Step-by-step procedure,
abkit function(s), How to interpret, Common pitfalls, How to present it. Open only the files you need.

## 1. Problem type -> methods

| Problem type (state.json) | Core steps (in order) | Reference files |
|---|---|---|
| `power_analysis` | baseline and variance -> sample size / MDE table -> runtime -> power curve | power_and_mde.md |
| `post_test_readout` | validation + SRM -> primary test -> secondary (Holm) -> guardrails (NI) -> time trend -> decision | frequentist_tests.md, srm.md, guardrails.md, multiple_testing.md, interpretation_and_decisions.md |
| `srm_investigation` | SRM overall -> SRM by day / segment -> contamination, filters -> recommendation (usually: fix and rerun) | srm.md |
| `bayesian_readout` | validation + SRM -> beta-binomial / normal model -> P(beat), expected loss -> decision | bayesian.md |
| `cuped_reanalysis` | validation + covariate balance -> CUPED (and/or regression adjustment) -> compare with unadjusted | cuped.md |
| `sequential_monitoring` | planned looks -> alpha-spending boundaries or mSPRT path -> stop / continue | sequential_testing.md |
| `heterogeneous_effects` | pre-specified segments -> per-segment effects (BH) -> interaction test -> Simpson's check | heterogeneous_effects.md |
| `multi_arm` | each arm vs control -> Holm or Dunnett -> pick best with CIs | multi_arm.md |
| `ratio_metric` | aggregate to randomisation unit -> delta method (or clustered SE) -> compare with naive | ratio_metrics_delta_method.md |
| `novelty_check` | lift by exposure day / calendar day -> trend test -> early vs late | novelty_primacy.md |
| `guardrail_check` | non-inferiority per guardrail with margin | guardrails.md |
| `quasi_experiment` | parallel trends -> DiD (or ITS / synthetic control) -> placebo checks | quasi_experiments.md |

Problem types combine: a typical readout is `post_test_readout` + `guardrail_check` (+ `heterogeneous_effects`).

## 2. Metric type -> default test

| Metric type | Default | Heavy tails / small n | Notes |
|---|---|---|---|
| binary (per unit) | two-proportion z-test | Fisher exact (tiny counts) | `frequentist.two_proportion_ztest` |
| continuous (per unit) | Welch t-test | bootstrap CI; winsorised sensitivity | never Mann-Whitney for "did revenue change" |
| count (per unit) | Welch t-test | bootstrap | Poisson GLM only with care (overdispersion) |
| ratio (sum A / sum B, finer unit) | delta method | cluster-robust regression | `ratio_metrics.delta_method_ratio` |
| any, with pre-period covariate | CUPED | regression adjustment | variance reduction ~ corr^2 |

## 3. Always, whatever the problem

1. Unit of analysis = randomisation unit (or delta method / clustered SEs).
2. SRM check before reading any effect (srm.md).
3. One pre-registered primary metric; corrections for the rest (multiple_testing.md).
4. Report effect size + CI, not just p-values; compare the CI with the practical threshold.
5. A non-significant result is "inconclusive" unless the CI rules out the MDE (interpretation_and_decisions.md).
6. Every number goes into results.json via `abkit.results.add_result` with the producing script.

## 4. Reference files

- [power_and_mde.md](references/power_and_mde.md)
- [frequentist_tests.md](references/frequentist_tests.md)
- [bayesian.md](references/bayesian.md)
- [srm.md](references/srm.md)
- [cuped.md](references/cuped.md)
- [sequential_testing.md](references/sequential_testing.md)
- [ratio_metrics_delta_method.md](references/ratio_metrics_delta_method.md)
- [multiple_testing.md](references/multiple_testing.md)
- [multi_arm.md](references/multi_arm.md)
- [heterogeneous_effects.md](references/heterogeneous_effects.md)
- [novelty_primacy.md](references/novelty_primacy.md)
- [guardrails.md](references/guardrails.md)
- [quasi_experiments.md](references/quasi_experiments.md)
- [interpretation_and_decisions.md](references/interpretation_and_decisions.md)

## 5. Answering general questions (no data)

Answer directly from the relevant reference file: definition, when it applies, a worked number
(compute it with abkit, e.g. `power.sample_size_proportions(0.1, 0.05)`), and the main pitfall.
Do not create a run folder for a general question.
