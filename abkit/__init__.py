"""abkit: reusable A/B testing toolkit for the Claude Code experimentation workflow.

Submodules are imported explicitly (``from abkit import frequentist``) so that
lightweight consumers such as the hooks never pay for pandas/scipy imports.

Modules
-------
state               run folders, runs/.active, state.json schema
results             results.json schema, StatResult, number formatting
io                  CSV loading and run-folder data helpers
validation          data profiling, SRM, contamination, outliers
power               sample size, MDE, power curves, runtime
frequentist         z-test, Welch, Mann-Whitney, chi-square, bootstrap, non-inferiority, multi-arm
bayesian            beta-binomial and normal models
variance_reduction  CUPED and regression adjustment
sequential          alpha spending boundaries and mSPRT
ratio_metrics       delta method and cluster-robust tests
multiple_testing    Bonferroni / Holm / Benjamini-Hochberg
segments            segment effects, interaction tests, Simpson's paradox
time_effects        daily / cumulative effects, novelty and primacy
quasi               difference-in-differences, ITS, synthetic control
decision            ship / don't ship / iterate / extend logic and run summary
viz, deck, report   deliverable builders
"""

__version__ = "0.1.0"
