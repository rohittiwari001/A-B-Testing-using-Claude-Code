import json

import pandas as pd

NAMES = ["checkout_ab", "pricing_multiarm", "srm_broken", "cuped_engagement", "novelty_feature", "sessions_ratio", "geo_rollout"]


def test_all_demo_files_exist(demo_csvs):
    for name in NAMES:
        assert (demo_csvs / f"{name}.csv").is_file()
        assert (demo_csvs / f"{name}_context.md").read_text().strip()
    truth = json.loads((demo_csvs / "ground_truth.json").read_text())
    assert set(truth) == set(NAMES)


def test_checkout_has_expected_shape(checkout_df):
    assert set(checkout_df.variant) == {"control", "treatment"}
    assert checkout_df.exposure_date.nunique() == 14
    lift = checkout_df.groupby("variant").converted.mean()
    assert 0.02 < lift.treatment / lift.control - 1 < 0.045


def test_srm_dataset_is_unbalanced(demo_csvs):
    counts = pd.read_csv(demo_csvs / "srm_broken.csv").variant.value_counts()
    assert counts.control / counts.sum() > 0.52
