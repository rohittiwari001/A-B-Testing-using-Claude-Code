"""Statistical functions validated against scipy/statsmodels, closed forms and simulation."""

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from abkit import bayesian, decision, frequentist, multiple_testing, power, quasi, ratio_metrics, segments
from abkit import sequential, time_effects, validation, variance_reduction


# --------------------------------------------------------------------------- frequentist


def test_ztest_matches_statsmodels():
    from statsmodels.stats.proportion import proportions_ztest

    r = frequentist.two_proportion_ztest(500, 10_000, 560, 10_000)
    z, p = proportions_ztest([560, 500], [10_000, 10_000])
    assert r.p_value == pytest.approx(p, rel=1e-9)
    assert r.extra["z"] == pytest.approx(z, rel=1e-9)
    assert r.rel_lift == pytest.approx(0.12)
    assert r.ci_low < r.estimate < r.ci_high


def test_ztest_one_sided_and_bad_input():
    two = frequentist.two_proportion_ztest(500, 10_000, 560, 10_000)
    one = frequentist.two_proportion_ztest(500, 10_000, 560, 10_000, alternative="greater")
    assert one.p_value == pytest.approx(two.p_value / 2)
    with pytest.raises(ValueError):
        frequentist.two_proportion_ztest(5, 0, 3, 10)
    with pytest.raises(ValueError):
        frequentist.two_proportion_ztest(5, 10, 3, 10, alternative="bigger")


def test_welch_matches_scipy(rng):
    c, t = rng.normal(10, 3, 800), rng.normal(10.5, 4, 700)
    r = frequentist.welch_ttest(c, t)
    ref = stats.ttest_ind(t, c, equal_var=False)
    assert r.p_value == pytest.approx(ref.pvalue, rel=1e-9)
    ci = ref.confidence_interval(0.95)
    assert (r.ci_low, r.ci_high) == pytest.approx((ci.low, ci.high), rel=1e-6)


def test_aa_simulation_rejects_at_alpha():
    rng = np.random.default_rng(7)
    p = [frequentist.two_proportion_ztest(rng.binomial(5000, 0.2), 5000, rng.binomial(5000, 0.2), 5000).p_value for _ in range(2000)]
    rate = np.mean(np.array(p) < 0.05)
    assert 0.035 < rate < 0.065


def test_bootstrap_agrees_with_welch(rng):
    c, t = rng.lognormal(3, 1, 3000), rng.lognormal(3.05, 1, 3000)
    b = frequentist.bootstrap_diff(c, t, n_resamples=2000, seed=1)
    w = frequentist.welch_ttest(c, t)
    assert b.estimate == pytest.approx(w.estimate)
    assert b.ci_low == pytest.approx(w.ci_low, abs=0.25 * (w.ci_high - w.ci_low))
    assert b.ci_high == pytest.approx(w.ci_high, abs=0.25 * (w.ci_high - w.ci_low))


def test_mann_whitney_and_chi_square(rng):
    c, t = rng.normal(0, 1, 300), rng.normal(0.3, 1, 300)
    r = frequentist.mann_whitney(c, t)
    assert r.p_value == pytest.approx(stats.mannwhitneyu(t, c).pvalue)
    assert r.probability > 0.5
    tab = pd.DataFrame([[100, 900], [130, 870]], index=["control", "treatment"])
    chi = frequentist.chi_square_test(tab)
    assert chi.p_value == pytest.approx(stats.chi2_contingency(tab, correction=False)[1])


def test_noninferiority_statuses(rng):
    base = rng.normal(100, 20, 20_000)
    same = frequentist.noninferiority_test(base, rng.normal(100, 20, 20_000), margin_rel=0.01)
    worse = frequentist.noninferiority_test(base, rng.normal(95, 20, 20_000), margin_rel=0.01)
    tiny = frequentist.noninferiority_test(base[:50], rng.normal(100, 20, 50), margin_rel=0.01)
    assert same.extra["status"] == "pass"
    assert worse.extra["status"] == "breach"
    assert tiny.extra["status"] == "inconclusive"
    up = frequentist.noninferiority_test(base, rng.normal(105, 20, 20_000), margin_rel=0.01, direction="no_increase")
    assert up.extra["status"] == "breach"
    binary = frequentist.noninferiority_test(counts=(3000, 10_000, 2990, 10_000), margin_rel=0.10)
    assert binary.extra["status"] == "pass"


def test_compare_dispatch_and_multi_arm(demo_csvs):
    df = pd.read_csv(demo_csvs / "pricing_multiarm.csv")
    rows = frequentist.compare_to_control(df, "revenue", "continuous", "variant", "control", correction="holm")
    assert {r.treatment for r in rows} == {"price_low", "price_high"}
    assert all(r.p_value_adjusted >= r.p_value for r in rows)
    dun = frequentist.compare_to_control(df, "revenue", "continuous", "variant", "control", dunnett=True)
    assert all(r.correction == "dunnett" for r in dun)
    with pytest.raises(ValueError):
        frequentist.compare(df, "revenue", "ratio", "variant", "control", "price_low")
    with pytest.raises(KeyError):
        frequentist.compare(df, "nope", "continuous", "variant", "control", "price_low")


def test_multiple_testing_matches_statsmodels():
    from statsmodels.stats.multitest import multipletests

    p = [0.001, 0.01, 0.02, 0.04, 0.3]
    for ours, theirs in (("holm", "holm"), ("bonferroni", "bonferroni"), ("benjamini-hochberg", "fdr_bh")):
        assert np.allclose(multiple_testing.adjust_pvalues(p, ours), multipletests(p, method=theirs)[1])
    assert np.allclose(multiple_testing.adjust_pvalues(p, "none"), p)
    rs = [{"p_value": 0.01}, {"p_value": 0.04}, {"p_value": None}]
    multiple_testing.apply_correction(rs, "bonferroni", 0.05)
    assert rs[0]["significant"] and not rs[1]["significant"] and "p_value_adjusted" not in rs[2]
    with pytest.raises(ValueError):
        multiple_testing.adjust_pvalues([0.1], "magic")


# --------------------------------------------------------------------------- power


def test_sample_size_proportions_matches_statsmodels_and_simulation():
    from statsmodels.stats.power import NormalIndPower
    from statsmodels.stats.proportion import proportion_effectsize

    r = power.sample_size_proportions(0.10, 0.10)
    h = proportion_effectsize(0.11, 0.10)
    ref = NormalIndPower().solve_power(h, alpha=0.05, power=0.8)
    assert r.estimate == pytest.approx(ref, rel=0.02)
    assert power.power_proportions(0.10, 0.10, r.estimate) == pytest.approx(0.8, abs=0.005)
    sim = power.simulate_power("proportion", 0.10, 0.10, r.estimate, n_sims=1500, seed=3)
    assert sim == pytest.approx(0.8, abs=0.04)


def test_means_power_roundtrip_and_simulation():
    r = power.sample_size_means(sd=20, mde_abs=2)
    assert r.estimate == int(np.ceil(2 * (1.959964 + 0.841621) ** 2 * 400 / 4))
    mde = power.mde_means(sd=20, n_control=r.estimate)
    assert mde.estimate == pytest.approx(2, rel=0.01)
    sim = power.simulate_power("mean", 100, 0.02, r.estimate, sd=20, n_sims=1000, seed=4)
    assert sim == pytest.approx(0.8, abs=0.05)
    m = power.mde_proportions(0.10, 14_751)
    assert m.estimate == pytest.approx(0.10, rel=0.02)


def test_curves_tables_runtime_history():
    curve = power.power_curve("proportion", 0.1, [0.05, 0.1], [1000, 10_000, 100_000])
    assert curve.groupby("mde").power.apply(lambda s: s.is_monotonic_increasing).all()
    tab = power.sample_size_table("proportion", 0.1, [0.05, 0.1], daily_units=5000)
    assert tab.n_per_variant.iloc[0] > tab.n_per_variant.iloc[1] and (tab.days % 7 == 0).all()
    assert power.runtime_days(10_000, 2_000) == 14
    assert power.runtime_days(10_000, 2_000, prefer_full_weeks=False) == 10
    h = power.variance_from_history([0, 1, 1, 0])
    assert h["binary"] and h["sd"] == pytest.approx(0.5)


# --------------------------------------------------------------------------- bayesian


def test_beta_binomial_probability_close_to_normal_approx():
    r = bayesian.beta_binomial(500, 10_000, 560, 10_000, prior="flat")
    se = np.sqrt(0.05 * 0.95 / 10_000 + 0.056 * 0.944 / 10_000)
    assert r.probability == pytest.approx(stats.norm.cdf(0.006 / se), abs=0.01)
    assert r.extra["expected_loss_treatment"] < r.extra["expected_loss_control"]
    assert bayesian.decide(r, threshold=0.95) in ("ship", "extend")
    assert r.extra["posteriors"]["treatment"]["a"] == 561


def test_normal_model_flat_matches_frequentist(rng):
    c, t = rng.normal(50, 10, 5000), rng.normal(50.6, 10, 5000)
    b = bayesian.normal_model(c, t, prior="flat")
    w = frequentist.welch_ttest(c, t)
    assert b.ci_low == pytest.approx(w.ci_low, abs=0.05) and b.ci_high == pytest.approx(w.ci_high, abs=0.05)
    shrunk = bayesian.normal_model(c, t, prior="weakly_informative", prior_sd_rel=0.001)
    assert abs(shrunk.estimate) < abs(b.estimate)
    best = bayesian.posterior_prob_best({"a": rng.normal(0, 1, 1000), "b": rng.normal(3, 1, 1000)})
    assert best["b"] > 0.95


# --------------------------------------------------------------------------- variance reduction


def test_cuped_reduces_variance_on_demo(demo_csvs):
    df = pd.read_csv(demo_csvs / "cuped_engagement.csv")
    r = variance_reduction.cuped(df, "minutes", "pre_minutes", "variant", "control", "treatment")
    corr = r.extra["correlation"]
    assert r.extra["variance_reduction"] == pytest.approx(corr**2, abs=0.02)
    assert r.extra["ci_width_adjusted"] < r.extra["ci_width_unadjusted"]
    assert r.p_value < r.extra["unadjusted"]["p_value"]
    reg = variance_reduction.regression_adjustment(df, "minutes", ["pre_minutes"], "variant", "control", "treatment")
    assert reg.estimate == pytest.approx(r.estimate, rel=0.05)


def test_cuped_is_unbiased_in_aa():
    rng = np.random.default_rng(11)
    ests = []
    for _ in range(300):
        x = rng.gamma(2, 30, 2000)
        y = x * rng.lognormal(0, 0.3, 2000)
        df = pd.DataFrame({"x": x, "y": y, "v": rng.choice(["c", "t"], 2000)})
        ests.append(variance_reduction.cuped(df, "y", "x", "v", "c", "t").p_value < 0.05)
    assert 0.02 < np.mean(ests) < 0.09


# --------------------------------------------------------------------------- sequential


def test_boundaries_match_reference_values():
    obf = sequential.boundaries([0.2, 0.4, 0.6, 0.8, 1.0], kind="obrien-fleming")["z_boundary"]
    assert np.allclose(obf, [4.8769, 3.3569, 2.6803, 2.2898, 2.0310], atol=0.002)
    poc = sequential.boundaries([0.2, 0.4, 0.6, 0.8, 1.0], kind="pocock")["z_boundary"]
    assert np.allclose(poc, [2.4380, 2.4268, 2.4101, 2.3966, 2.3859], atol=0.002)


def test_group_sequential_controls_type_one_error():
    rng = np.random.default_rng(5)
    t = np.array([0.25, 0.5, 0.75, 1.0])
    bnd = sequential.boundaries(t)["z_boundary"].to_numpy()
    inc = rng.normal(size=(20_000, 4)) * np.sqrt(np.diff(np.concatenate([[0], t])))
    z = np.cumsum(inc, axis=1) / np.sqrt(t)
    fpr = (np.abs(z) >= bnd).any(axis=1).mean()
    assert fpr == pytest.approx(0.05, abs=0.006)
    res = sequential.group_sequential_test([1.0, 3.5], [0.25, 0.5], planned_fractions=list(t))
    assert res.extra["stopped_at_look"] == 2


def test_peeking_inflates_and_msprt_does_not():
    sim = sequential.peeking_simulation(n_looks=14, n_sims=3000)
    assert sim["peeking_fpr"] > 2 * sim["fixed_horizon_fpr"]
    rng = np.random.default_rng(9)
    rejections = 0
    for _ in range(150):
        n = 4200
        df = pd.DataFrame({"v": rng.choice(["c", "t"], n), "y": rng.binomial(1, 0.3, n),
                           "d": pd.Timestamp("2026-01-01") + pd.to_timedelta(rng.integers(0, 14, n), unit="D")})
        rejections += sequential.msprt_path(df, "y", "d", "v", "c", "t", tau_rel=0.05).significant
    assert rejections / 150 <= 0.06


# --------------------------------------------------------------------------- ratio metrics


def test_delta_method_on_demo_and_against_cluster_robust(demo_csvs):
    df = pd.read_csv(demo_csvs / "sessions_ratio.csv")
    r = ratio_metrics.delta_method_ratio(df, "clicks", "pageviews", "user_id", "variant", "control", "treatment")
    assert r.extra["design_effect"] > 1.5
    df["ctr"] = df.clicks / df.pageviews
    c = ratio_metrics.cluster_robust_test(df, "ctr", "user_id", "variant", "control", "treatment", weights="pageviews")
    assert c.estimate == pytest.approx(r.estimate, rel=1e-6)
    assert c.extra["se"] == pytest.approx(r.extra["se"], rel=0.05)


def test_delta_method_aa_calibrated():
    rng = np.random.default_rng(21)
    naive, delta = 0, 0
    for _ in range(200):
        users = 1500
        ctr = rng.beta(4, 36, users)
        n_s = 1 + rng.poisson(4, users)
        uid = np.repeat(np.arange(users), n_s)
        pv = 1 + rng.poisson(6, uid.size)
        df = pd.DataFrame({"u": uid, "v": np.repeat(rng.choice(["c", "t"], users), n_s), "pv": pv, "cl": rng.binomial(pv, ctr[uid])})
        r = ratio_metrics.delta_method_ratio(df, "cl", "pv", "u", "v", "c", "t")
        delta += r.p_value < 0.05
        naive += r.extra["naive_p"] < 0.05
    assert delta / 200 < 0.09 and naive / 200 > 0.12


# --------------------------------------------------------------------------- segments


def test_segment_effects_and_interaction():
    rng = np.random.default_rng(2)
    n = 40_000
    seg = rng.choice(["a", "b"], n)
    v = rng.choice(["control", "treatment"], n)
    p = 0.2 + np.where((v == "treatment") & (seg == "a"), 0.04, 0.0)
    df = pd.DataFrame({"seg": seg, "variant": v, "y": (rng.random(n) < p).astype(int)})
    rows = segments.segment_effects(df, "y", "binary", "seg", "variant", "control", "treatment")
    assert [r.segment for r in rows] == ["All", "a", "b"]
    assert rows[1].correction == "benjamini-hochberg" and rows[1].significant
    inter = segments.interaction_test(df, "y", "seg", "variant", "control", "treatment")
    assert inter.significant
    null = segments.interaction_test(df.assign(seg=rng.choice(["x", "y"], n)), "y", "seg", "variant", "control", "treatment")
    assert not null.significant


def test_simpsons_paradox_detected():
    # Treatment better within each segment but concentrated in the low-converting segment
    rows = []
    for seg, var, n, conv in [("hi", "control", 900, 0.5), ("hi", "treatment", 100, 0.55),
                              ("lo", "control", 100, 0.1), ("lo", "treatment", 900, 0.12)]:
        k = int(n * conv)
        rows += [{"seg": seg, "variant": var, "y": 1}] * k + [{"seg": seg, "variant": var, "y": 0}] * (n - k)
    r = segments.simpsons_check(pd.DataFrame(rows), "y", "seg", "variant", "control", "treatment")
    assert r.extra["flagged"] and r.extra["pooled_diff"] < 0 < r.extra["standardised_diff"]


# --------------------------------------------------------------------------- time effects


def test_novelty_detected_on_demo(demo_csvs):
    df = pd.read_csv(demo_csvs / "novelty_feature.csv")
    by_exp = time_effects.effects_by(df, "clicks", "count", "days_since_exposure", "variant", "control", "treatment")
    trend = time_effects.trend_test(by_exp)
    assert trend.extra["pattern"].startswith("novelty")
    assert trend.extra["first_third_lift"] > trend.extra["last_third_lift"]
    cum = time_effects.cumulative_effects(df, "clicks", "count", "date", "variant", "control", "treatment")
    assert len(cum) == 21 and cum.n_control.is_monotonic_increasing
    ev = time_effects.early_vs_late(df, "clicks", "count", "days_since_exposure", 7, "variant", "control", "treatment")
    assert ev[0].rel_lift > ev[1].rel_lift


def test_stable_effect_has_no_trend():
    rng = np.random.default_rng(4)
    n = 30_000
    df = pd.DataFrame({"day": rng.integers(0, 14, n), "variant": rng.choice(["control", "treatment"], n)})
    df["y"] = rng.poisson(np.where(df.variant == "treatment", 2.1, 2.0))
    trend = time_effects.trend_test(time_effects.effects_by(df, "y", "count", "day", "variant", "control", "treatment"))
    assert trend.extra["pattern"].startswith("stable")


# --------------------------------------------------------------------------- quasi


def test_did_recovers_geo_effect(demo_csvs):
    df = pd.read_csv(demo_csvs / "geo_rollout.csv")
    r = quasi.diff_in_diff(df, "orders", "rolled_out", "post_launch", unit_col="region", time_col="week", log=True)
    assert r.rel_lift == pytest.approx(0.04, abs=0.015) and r.significant
    pt = quasi.parallel_trends_test(df, "orders", "rolled_out", "week", "post_launch", unit_col="region", log=True)
    assert not pt.significant
    tr = quasi.group_trends(df, "orders", "rolled_out", "week", index_to_pre=True, post_col="post_launch")
    assert list(tr.columns) == ["week", "control", "treated"]


def test_its_and_synthetic_control():
    rng = np.random.default_rng(8)
    t = np.arange(60)
    y = 100 + 0.5 * t + np.where(t >= 40, 10, 0) + rng.normal(0, 1, 60)
    its = quasi.interrupted_time_series(pd.DataFrame({"t": t, "y": y}), "t", "y", 40)
    assert its.estimate == pytest.approx(10, abs=2) and its.significant
    units = {f"d{i}": 50 + 5 * i + np.sin(t / 5 + i) * 3 + rng.normal(0, 0.5, 60) for i in range(8)}
    treated = 0.5 * units["d2"] + 0.5 * units["d5"] + np.where(t >= 40, 6, 0)
    long = pd.concat([pd.DataFrame({"unit": k, "t": t, "y": v}) for k, v in {**units, "T": treated}.items()])
    sc = quasi.synthetic_control(long, "unit", "t", "y", ["T"], 40)
    assert sc.estimate == pytest.approx(6, abs=1.5)
    assert sc.p_value <= 1 / 9 + 1e-9


# --------------------------------------------------------------------------- validation & decision


def test_validation_blocks_srm_demo(demo_csvs):
    df = pd.read_csv(demo_csvs / "srm_broken.csv")
    spec = {"unit_col": "user_id", "variant_col": "variant", "control": "control", "date_col": "exposure_date",
            "expected_split": {"control": 0.5, "treatment": 0.5}, "metrics": {"converted": "binary"}, "segments": ["platform"]}
    prof = validation.full_profile(df, spec)
    assert prof["verdict"] == "block" and prof["blocking"] == ["SRM"]
    srm = next(c for c in prof["checks"] if c["check"] == "SRM")
    assert "platform=Android" in srm["detail"]
    md = validation.profile_to_markdown(prof)
    assert "BLOCK" in md and "Likely causes" in md


def test_validation_passes_checkout(checkout_df):
    spec = {"unit_col": "user_id", "variant_col": "variant", "control": "control", "date_col": "exposure_date",
            "expected_split": {"control": 0.5, "treatment": 0.5}, "metrics": {"converted": "binary", "revenue": "continuous"},
            "segments": ["platform", "country"], "non_negative": ["revenue"],
            "expected_columns": list(checkout_df.columns)}
    prof = validation.full_profile(checkout_df, spec)
    assert prof["verdict"] in ("pass", "warn") and not prof["blocking"]


def test_validation_catches_bad_data():
    df = pd.DataFrame({"u": ["a", "a", "b", "c", "d"], "v": ["c", "t", "c", "t", "t"], "y": [0, 1, 2, 1, -1]})
    prof = validation.full_profile(df, {"unit_col": "u", "variant_col": "v", "metrics": {"y": "binary"}, "min_days": 1})
    verdicts = {c["check"]: c["verdict"] for c in prof["checks"]}
    assert verdicts["contamination"] == "block" and verdicts["impossible values"] == "block"
    missing = validation.full_profile(df, {"unit_col": "u", "variant_col": "variant"})
    assert missing["verdict"] == "block"
    assert validation.srm_check({"control": 5000, "treatment": 5000}).p_value == pytest.approx(1.0)


@pytest.mark.parametrize("res,mde,expected", [
    ({"rel_lift": 0.03, "rel_ci_low": 0.01, "rel_ci_high": 0.05, "p_value": 0.004, "significant": True}, 0.02, "ship"),
    ({"rel_lift": 0.01, "rel_ci_low": 0.002, "rel_ci_high": 0.018, "p_value": 0.01, "significant": True}, 0.02, "iterate"),
    ({"rel_lift": -0.03, "rel_ci_low": -0.05, "rel_ci_high": -0.01, "p_value": 0.004, "significant": True}, 0.02, "dont_ship"),
    ({"rel_lift": 0.002, "rel_ci_low": -0.005, "rel_ci_high": 0.009, "p_value": 0.6, "significant": False}, 0.02, "iterate"),
    ({"rel_lift": 0.01, "rel_ci_low": -0.02, "rel_ci_high": 0.04, "p_value": 0.5, "significant": False}, 0.02, "extend"),
    ({"rel_lift": 0.02, "rel_ci_low": 0.0, "rel_ci_high": 0.04, "p_value": None, "probability": 0.97}, None, "ship"),
])
def test_recommend(res, mde, expected):
    assert decision.recommend(res, mde_rel=mde)["verdict"] == expected


def test_recommend_guardrail_breach():
    win = {"rel_lift": 0.03, "p_value": 0.001, "significant": True}
    g = {"metric": "revenue", "extra": {"status": "breach"}}
    assert decision.recommend(win, [g])["verdict"] == "iterate"
    assert decision.recommend({"rel_lift": 0.0, "p_value": 0.9, "significant": False}, [g])["verdict"] == "dont_ship"
