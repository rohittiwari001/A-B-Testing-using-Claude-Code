"""Generate synthetic demo experiments with known ground truth.

Run:  python demo_data/generate.py            (writes CSVs + *_context.md here)

Each dataset has a matching ``<name>_context.md`` written the way a data
scientist would describe it in chat. ``GROUND_TRUTH`` records what the data
was built to show, so tests and dry runs can check the workflow finds it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
START = pd.Timestamp("2026-09-01")

GROUND_TRUTH = {
    "checkout_ab": {"true_rel_lift_conversion": 0.03, "segments": {"iOS": 0.05, "Android": 0.03, "Web": 0.01}},
    "pricing_multiarm": {"true_rel_lift_revenue": {"price_low": -0.01, "price_high": 0.05}},
    "srm_broken": {"intended_split": {"control": 0.5, "treatment": 0.5}, "cause": "treatment Android users missing from 2026-09-05 (logging bug)"},
    "cuped_engagement": {"true_rel_lift_minutes": 0.02, "pre_post_correlation": 0.8},
    "novelty_feature": {"lift_by_exposure_day": "0.02 + 0.13 * exp(-day / 4)"},
    "sessions_ratio": {"true_rel_lift_ctr": 0.03, "randomisation_unit": "user", "analysis_unit": "session"},
    "geo_rollout": {"true_rel_effect_orders": 0.04, "launch_week": 17, "treated_regions": 6},
}


def _dates(rng: np.random.Generator, n: int, days: int) -> pd.Series:
    # Slightly more traffic on weekdays so weekly cycles exist
    weights = np.array([1.1 if (START + pd.Timedelta(days=d)).dayofweek < 5 else 0.8 for d in range(days)])
    d = rng.choice(days, size=n, p=weights / weights.sum())
    return (START + pd.to_timedelta(d, unit="D")).strftime("%Y-%m-%d")


def checkout_ab(rng: np.random.Generator) -> pd.DataFrame:
    n = 80_000
    variant = rng.choice(["control", "treatment"], size=n)
    platform = rng.choice(["iOS", "Android", "Web"], size=n, p=[0.40, 0.35, 0.25])
    country = rng.choice(["US", "UK", "DE", "IN"], size=n, p=[0.45, 0.20, 0.15, 0.20])
    base = 0.35 * np.select([platform == "iOS", platform == "Android"], [1.05, 0.97], 0.95)
    base = base * np.select([country == "IN", country == "DE"], [0.85, 1.05], 1.0)
    seg_lift = np.select([platform == "iOS", platform == "Android"], [0.05, 0.03], 0.01)
    p = base * np.where(variant == "treatment", 1 + seg_lift, 1.0)
    converted = rng.random(n) < p
    aov = rng.lognormal(mean=np.log(55), sigma=0.6, size=n)
    revenue = np.where(converted, np.round(aov, 2), 0.0)
    return pd.DataFrame({
        "user_id": [f"u{i:06d}" for i in range(n)],
        "variant": variant,
        "exposure_date": _dates(rng, n, 14),
        "platform": platform,
        "country": country,
        "converted": converted.astype(int),
        "revenue": revenue,
    })


def pricing_multiarm(rng: np.random.Generator) -> pd.DataFrame:
    n = 45_000
    variant = rng.choice(["control", "price_low", "price_high"], size=n)
    conv = np.select([variant == "price_low", variant == "price_high"], [0.132, 0.110], 0.12)
    aov_mult = np.select([variant == "price_low", variant == "price_high"], [0.90, 1.145], 1.0)
    buys = rng.random(n) < conv
    orders = np.where(buys, 1 + rng.poisson(0.3, n), 0)
    # Heavy tail: lognormal basket plus rare "whale" purchases
    basket = rng.lognormal(np.log(40), 1.0, n) * aov_mult
    whales = rng.random(n) < 0.004
    basket = np.where(whales, basket * rng.uniform(8, 25, n), basket)
    revenue = np.round(np.where(buys, basket * orders, 0.0), 2)
    return pd.DataFrame({
        "user_id": [f"p{i:06d}" for i in range(n)],
        "variant": variant,
        "assignment_date": _dates(rng, n, 21),
        "orders": orders,
        "revenue": revenue,
    })


def srm_broken(rng: np.random.Generator) -> pd.DataFrame:
    n = 42_000
    variant = rng.choice(["control", "treatment"], size=n)
    platform = rng.choice(["iOS", "Android", "Web"], size=n, p=[0.4, 0.35, 0.25])
    dates = pd.to_datetime(_dates(rng, n, 14))
    p = np.where(variant == "treatment", 0.212, 0.20)
    converted = (rng.random(n) < p).astype(int)
    df = pd.DataFrame({"user_id": [f"s{i:06d}" for i in range(n)], "variant": variant,
                       "exposure_date": dates.strftime("%Y-%m-%d"), "platform": platform, "converted": converted})
    # Logging bug: from Sept 5 most treatment Android users are never logged
    lost = (df.variant == "treatment") & (df.platform == "Android") & (dates >= "2026-09-05") & (rng.random(n) < 0.6)
    return df.loc[~lost].reset_index(drop=True)


def cuped_engagement(rng: np.random.Generator) -> pd.DataFrame:
    n = 20_000
    variant = rng.choice(["control", "treatment"], size=n)
    habit = rng.gamma(shape=2.0, scale=30.0, size=n)            # latent engagement level
    pre = np.maximum(0, habit * rng.lognormal(0, 0.35, n))
    post = habit * rng.lognormal(0, 0.35, n) * np.where(variant == "treatment", 1.02, 1.0)
    return pd.DataFrame({
        "user_id": [f"e{i:06d}" for i in range(n)],
        "variant": variant,
        "signup_country": rng.choice(["US", "UK", "DE"], size=n, p=[0.5, 0.3, 0.2]),
        "pre_minutes": np.round(pre, 1),
        "minutes": np.round(post, 1),
    })


def novelty_feature(rng: np.random.Generator) -> pd.DataFrame:
    users = 5_000
    variant = rng.choice(["control", "treatment"], size=users)
    start_day = rng.integers(0, 7, users)                       # staggered entry in week 1
    propensity = rng.gamma(2.0, 1.0, users)
    rows = []
    for d in range(21):
        active = (start_day <= d) & (rng.random(users) < 0.55)
        idx = np.flatnonzero(active)
        exp_day = d - start_day[idx]
        lift = np.where(variant[idx] == "treatment", 1 + 0.02 + 0.13 * np.exp(-exp_day / 4), 1.0)
        clicks = rng.poisson(propensity[idx] * 1.5 * lift)
        rows.append(pd.DataFrame({
            "user_id": [f"n{i:05d}" for i in idx],
            "variant": variant[idx],
            "date": (START + pd.Timedelta(days=d)).strftime("%Y-%m-%d"),
            "days_since_exposure": exp_day,
            "clicks": clicks,
        }))
    return pd.concat(rows, ignore_index=True)


def sessions_ratio(rng: np.random.Generator) -> pd.DataFrame:
    users = 12_000
    variant = rng.choice(["control", "treatment"], size=users)
    user_ctr = rng.beta(4, 36, users) * np.where(variant == "treatment", 1.03, 1.0)   # ~10% CTR, user-specific
    n_sessions = 1 + rng.poisson(4, users)
    uid = np.repeat(np.arange(users), n_sessions)
    pageviews = 1 + rng.poisson(6, uid.size)
    clicks = rng.binomial(pageviews, user_ctr[uid])
    return pd.DataFrame({
        "session_id": [f"sess{i:07d}" for i in range(uid.size)],
        "user_id": [f"r{i:05d}" for i in uid],
        "variant": variant[uid],
        "date": _dates(rng, uid.size, 14),
        "pageviews": pageviews,
        "clicks": clicks,
    })


def geo_rollout(rng: np.random.Generator) -> pd.DataFrame:
    regions = [f"R{i:02d}" for i in range(1, 21)]
    treated = set(regions[:6])
    level = dict(zip(regions, rng.uniform(800, 2500, len(regions))))
    rows = []
    for w in range(26):
        season = 1 + 0.08 * np.sin(2 * np.pi * w / 26) + 0.004 * w
        for r in regions:
            is_t = r in treated
            post = w >= 16
            eff = 1.04 if (is_t and post) else 1.0
            orders = rng.poisson(level[r] * season * eff * rng.lognormal(0, 0.02))
            rows.append({"region": r, "week": w + 1,
                         "week_start": (pd.Timestamp("2026-03-02") + pd.Timedelta(weeks=w)).strftime("%Y-%m-%d"),
                         "rolled_out": int(is_t), "post_launch": int(post), "orders": orders})
    return pd.DataFrame(rows)


CONTEXT = {
    "checkout_ab": """
We ran an A/B test on the checkout page: the treatment replaces the multi-step checkout with a single "Pay now" button.
File: checkout_ab.csv, one row per user. Columns: user_id, variant (control / treatment), exposure_date (first day the user
saw checkout, 2026-09-01 to 2026-09-14), platform (iOS / Android / Web), country (US / UK / DE / IN), converted (1 if the user
completed a purchase within the test), revenue (USD revenue from that user during the test, 0 if no purchase).
Traffic was split 50/50 at user level. Primary metric is conversion; revenue per user is a guardrail - we don't want it to drop.
We'd like to know if we should ship it, and whether the effect differs by platform.
""",
    "pricing_multiarm": """
Pricing test with three arms: control (current prices), price_low (-10% list prices) and price_high (+15% list prices).
File: pricing_multiarm.csv, one row per user, randomised equally across the three arms over 21 days starting 2026-09-01.
Columns: user_id, variant, assignment_date, orders (number of orders), revenue (USD, includes a few very large B2B baskets).
Primary metric is revenue per user. We need to pick which price level to roll out. Orders per user matters too.
""",
    "srm_broken": """
Test of a new onboarding checklist. File srm_broken.csv, one row per user: user_id, variant (control / treatment),
exposure_date (2026-09-01 to 2026-09-14), platform, converted (1 if the user activated within 7 days).
Intended split was 50/50 by user. Primary metric: activation (converted). Can you give me the readout?
""",
    "cuped_engagement": """
We tested a redesigned home feed. File cuped_engagement.csv, one row per user: user_id, variant (control / treatment),
signup_country, pre_minutes (minutes in app in the 14 days before the test), minutes (minutes in app during the 14-day test).
Randomised 50/50 by user. Primary metric is minutes per user. The naive t-test was borderline - can we use the
pre-period data to get a more precise answer?
""",
    "novelty_feature": """
New "For you" shelf in the app. File novelty_feature.csv has one row per user per active day: user_id, variant,
date (2026-09-01 to 2026-09-21), days_since_exposure (0 = the day the user first saw the test), clicks (content clicks
that day). Users entered the test during the first week; 50/50 split by user. Primary metric: clicks per user-day.
The early dashboard showed a big lift but it seems to be shrinking - is the effect real and lasting?
""",
    "sessions_ratio": """
Search ranking test. File sessions_ratio.csv has one row per session: session_id, user_id, variant, date, pageviews,
clicks. Randomisation was by user (50/50), but the metric we care about is click-through rate = total clicks / total
pageviews. Primary metric: CTR. Did the new ranking improve CTR?
""",
    "geo_rollout": """
We could not randomise: the new same-day delivery option was launched in 6 of our 20 regions (R01-R06) from week 17
(week_start 2026-06-22). File geo_rollout.csv: region, week (1-26), week_start, rolled_out (1 for launch regions),
post_launch (1 for weeks after launch), orders (weekly orders in the region). Did the launch increase orders, and by how much?
""",
}

GENERATORS = {
    "checkout_ab": checkout_ab,
    "pricing_multiarm": pricing_multiarm,
    "srm_broken": srm_broken,
    "cuped_engagement": cuped_engagement,
    "novelty_feature": novelty_feature,
    "sessions_ratio": sessions_ratio,
    "geo_rollout": geo_rollout,
}


# Per-dataset seeds, chosen so realised effects sit close to the ground truth above
SEEDS = {"checkout_ab": 20261010}


def generate(out: Path = OUT, seed: int = 20261001) -> dict[str, Path]:
    """Write every demo CSV and context file; returns {name: csv_path}."""
    out.mkdir(parents=True, exist_ok=True)
    paths = {}
    for i, (name, fn) in enumerate(GENERATORS.items()):
        df = fn(np.random.default_rng(SEEDS.get(name, seed + i)))
        path = out / f"{name}.csv"
        df.to_csv(path, index=False)
        (out / f"{name}_context.md").write_text(CONTEXT[name].strip() + "\n", encoding="utf-8")
        paths[name] = path
    (out / "ground_truth.json").write_text(json.dumps(GROUND_TRUTH, indent=2), encoding="utf-8")
    return paths


if __name__ == "__main__":
    for name, path in generate().items():
        print(f"{name:18s} {len(pd.read_csv(path)):>8,} rows -> {path.name}")
