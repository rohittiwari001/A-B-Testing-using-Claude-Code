"""Data validation: profile the CSV against the user's description before any analysis.

Each check returns ``{"check", "verdict": pass|warn|block, "detail", "data"}``.
``full_profile`` runs them all and ``profile_to_markdown`` renders data_profile.md.

Example
-------
>>> spec = {"unit_col": "user_id", "variant_col": "variant", "control": "control",
...         "expected_split": {"control": 0.5, "treatment": 0.5}, "date_col": "exposure_date",
...         "metrics": {"converted": "binary", "revenue": "continuous"}}
>>> profile = full_profile(df, spec)           # doctest: +SKIP
>>> profile["verdict"]                          # doctest: +SKIP
'pass'
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from abkit.results import StatResult

PASS, WARN, BLOCK = "pass", "warn", "block"
SRM_CAUSES = [
    "Assignment or bucketing bug (hash salt, uneven ramp, variant-specific eligibility)",
    "Logging loss that differs by variant (crashes, slow pages, ad blockers, client-side events)",
    "Bot or fraud filtering that interacts with the treatment",
    "Data pipeline joins or filters applied after assignment (e.g. 'users who reached step X')",
    "Ramp changes or restarts during the test without re-randomisation",
]


def _check(name: str, verdict: str, detail: str, data: Any = None) -> dict[str, Any]:
    return {"check": name, "verdict": verdict, "detail": detail, "data": data}


# --------------------------------------------------------------------------- SRM


def srm_check(
    counts: dict[str, int] | pd.DataFrame, variant_col: str | None = None,
    expected: dict[str, float] | None = None, threshold: float = 0.001, unit_col: str | None = None,
) -> StatResult:
    """Chi-square goodness-of-fit of observed variant counts against the intended split.

    ``counts`` is ``{variant: n_units}`` or a DataFrame (units counted by ``unit_col`` if given).
    ``significant`` is True when SRM is detected (p < threshold).

    >>> srm_check({"control": 5000, "treatment": 5200}).p_value < 0.05
    True
    """
    if isinstance(counts, pd.DataFrame):
        if variant_col is None:
            raise ValueError("variant_col is required when passing a DataFrame")
        grp = counts.groupby(variant_col)
        counts = (grp[unit_col].nunique() if unit_col else grp.size()).to_dict()
    counts = {str(k): int(v) for k, v in counts.items()}
    names = sorted(counts)
    if expected is None:
        expected = {k: 1 / len(names) for k in names}
    expected = {str(k): float(v) for k, v in expected.items()}
    missing = set(expected) - set(counts)
    for m in missing:
        counts[m] = 0
    names = sorted(expected)
    total = sum(counts[k] for k in names)
    share_sum = sum(expected.values())
    exp_n = np.array([expected[k] / share_sum * total for k in names])
    obs = np.array([counts[k] for k in names])
    chi2, p = stats.chisquare(obs, exp_n)
    obs_share = {k: counts[k] / total if total else 0.0 for k in names}
    r = StatResult(
        method="validation.srm_check", estimate=float(max(abs(obs_share[k] - expected[k] / share_sum) for k in names)),
        p_value=float(p), n=counts, significant=bool(p < threshold), alpha=threshold,
        extra={"chi2": float(chi2), "observed": counts, "expected_share": {k: expected[k] / share_sum for k in names},
               "observed_share": obs_share, "expected_count": dict(zip(names, exp_n.tolist())), "threshold": threshold},
    )
    if r.significant:
        r.notes.append("Sample ratio mismatch: do not trust effect estimates until the cause is understood.")
    return r


def srm_by(
    df: pd.DataFrame, variant_col: str, by_col: str, expected: dict[str, float] | None = None,
    threshold: float = 0.001, unit_col: str | None = None,
) -> pd.DataFrame:
    """SRM test within each level of ``by_col`` (day, platform, ...) to localise the cause."""
    rows = []
    for level, g in df.groupby(by_col):
        r = srm_check(g, variant_col, expected, threshold, unit_col)
        if isinstance(level, pd.Timestamp):
            level = level.date().isoformat()
        rows.append({by_col: level, **{f"n_{k}": v for k, v in r.n.items()},
                     **{f"share_{k}": v for k, v in r.extra["observed_share"].items()},
                     "p_value": r.p_value, "srm": r.significant})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- individual checks


def check_schema(df: pd.DataFrame, expected_columns: list[str], required: list[str]) -> dict:
    missing = [c for c in expected_columns if c not in df.columns]
    missing_required = [c for c in required if c not in df.columns]
    extra = [c for c in df.columns if c not in expected_columns] if expected_columns else []
    if missing_required:
        return _check("schema", BLOCK, f"Required columns missing: {missing_required}", {"missing": missing, "extra": extra})
    if missing:
        return _check("schema", WARN, f"Described but missing: {missing}", {"missing": missing, "extra": extra})
    detail = f"{len(df.columns)} columns, {len(df):,} rows" + (f"; undescribed: {extra}" if extra else "")
    return _check("schema", PASS, detail, {"missing": [], "extra": extra, "rows": len(df)})


def check_dtypes(df: pd.DataFrame, metrics: dict[str, str]) -> dict:
    bad = [m for m in metrics if m in df.columns and not pd.api.types.is_numeric_dtype(df[m])]
    dtypes = {c: str(t) for c, t in df.dtypes.items()}
    if bad:
        return _check("dtypes", BLOCK, f"Metric columns are not numeric: {bad}", dtypes)
    return _check("dtypes", PASS, "All metric columns numeric", dtypes)


def check_missing(df: pd.DataFrame, key_cols: list[str]) -> dict:
    miss = df.isna().mean()
    miss = miss[miss > 0].round(4).to_dict()
    key_missing = {c: v for c, v in miss.items() if c in key_cols}
    if key_missing:
        return _check("missing values", WARN, f"Missing values in key columns: {key_missing}", miss)
    if miss:
        return _check("missing values", PASS, f"Missing only in non-key columns: {miss}", miss)
    return _check("missing values", PASS, "No missing values", {})


def check_duplicates(df: pd.DataFrame, unit_col: str, allow_multiple_rows: bool = False) -> dict:
    dup_rows = int(df.duplicated().sum())
    rows_per_unit = df.groupby(unit_col).size()
    multi = int((rows_per_unit > 1).sum())
    data = {"duplicate_rows": dup_rows, "units_with_multiple_rows": multi, "units": int(rows_per_unit.size),
            "max_rows_per_unit": int(rows_per_unit.max())}
    if dup_rows:
        return _check("duplicates", WARN, f"{dup_rows:,} fully duplicated rows", data)
    if multi and not allow_multiple_rows:
        return _check("duplicates", WARN, f"{multi:,} units have more than one row (expected one row per unit)", data)
    return _check("duplicates", PASS, f"{data['units']:,} units" + (f", up to {data['max_rows_per_unit']} rows each" if multi else ", one row each"), data)


def check_contamination(df: pd.DataFrame, unit_col: str, variant_col: str) -> dict:
    per_unit = df.groupby(unit_col)[variant_col].nunique()
    bad = int((per_unit > 1).sum())
    share = bad / max(len(per_unit), 1)
    data = {"units_in_multiple_variants": bad, "share": share}
    if share >= 0.01:
        return _check("contamination", BLOCK, f"{bad:,} units ({share:.2%}) appear in more than one variant", data)
    if bad:
        return _check("contamination", WARN, f"{bad:,} units ({share:.2%}) in more than one variant; exclude them and report", data)
    return _check("contamination", PASS, "No unit appears in more than one variant", data)


def check_variants(df: pd.DataFrame, variant_col: str, expected_split: dict[str, float] | None, control: str | None) -> dict:
    counts = df[variant_col].astype(str).value_counts().to_dict()
    exp = [str(v) for v in (expected_split or {})]
    missing = [v for v in exp if counts.get(v, 0) == 0]
    unexpected = [v for v in counts if exp and v not in exp]
    if len(counts) < 2 or missing or (control and str(control) not in counts):
        return _check("variants", BLOCK, f"Variants found {counts}; missing/empty: {missing or control}", counts)
    if unexpected:
        return _check("variants", WARN, f"Unexpected variant labels {unexpected}; counts {counts}", counts)
    return _check("variants", PASS, f"Counts {counts}", counts)


def check_srm(df: pd.DataFrame, variant_col: str, expected_split: dict[str, float] | None, threshold: float,
              unit_col: str | None, by_cols: list[str]) -> dict:
    r = srm_check(df, variant_col, expected_split, threshold, unit_col)
    data = r.to_dict()
    if r.significant:
        localise = {}
        for col in by_cols:
            if col in df.columns and df[col].nunique() <= 60:
                t = srm_by(df, variant_col, col, expected_split, threshold, unit_col)
                localise[col] = t.to_dict(orient="records")
        data["by"] = localise
        data["likely_causes"] = SRM_CAUSES
        worst = _worst_levels(localise)
        return _check("SRM", BLOCK, f"Sample ratio mismatch: p = {r.p_value:.2e} < {threshold}; observed shares "
                      f"{ {k: round(v, 4) for k, v in r.extra['observed_share'].items()} }." + (f" Concentrated in: {worst}" if worst else ""), data)
    return _check("SRM", PASS, f"p = {r.p_value:.3f} (threshold {threshold})", data)


def check_dates(df: pd.DataFrame, date_col: str, variant_col: str, min_days: int = 7, prefer_full_weeks: bool = True) -> dict:
    d = pd.to_datetime(df[date_col], errors="coerce")
    if d.isna().all():
        return _check("dates", WARN, f"Could not parse {date_col} as dates", None)
    days = pd.date_range(d.min().normalize(), d.max().normalize(), freq="D")
    cover = df.assign(_d=d.dt.normalize()).groupby(["_d", variant_col]).size().unstack(fill_value=0).reindex(days, fill_value=0)
    gaps = [str(x.date()) for x in cover.index[(cover == 0).any(axis=1)]]
    n_days = len(days)
    data = {"start": str(d.min().date()), "end": str(d.max().date()), "days": n_days, "days_with_gaps": gaps,
            "daily_counts": {str(k.date()): {str(c): int(v) for c, v in row.items()} for k, row in cover.iterrows()}}
    issues = []
    if gaps:
        issues.append(f"days with a variant missing: {gaps[:5]}")
    if n_days < min_days:
        issues.append(f"only {n_days} days (< {min_days})")
    if prefer_full_weeks and n_days % 7:
        issues.append(f"{n_days} days is not a whole number of weeks (weekday mix may bias results)")
    verdict = WARN if issues else PASS
    return _check("dates", verdict, f"{data['start']} to {data['end']} ({n_days} days)" + ("; " + "; ".join(issues) if issues else ""), data)


def check_outliers(df: pd.DataFrame, metrics: dict[str, str]) -> dict:
    out = {}
    flags = []
    for m, typ in metrics.items():
        if m not in df.columns or typ == "binary" or not pd.api.types.is_numeric_dtype(df[m]):
            continue
        x = df[m].dropna()
        q1, q3, p99 = x.quantile([0.25, 0.75, 0.99])
        fence = q3 + 3 * (q3 - q1)
        n_out = int((x > fence).sum()) if q3 > q1 else 0
        ratio = float(x.max() / p99) if p99 > 0 else None
        out[m] = {"p50": float(x.median()), "p99": float(p99), "max": float(x.max()), "n_above_3iqr": n_out,
                  "max_over_p99": ratio, "skew": float(stats.skew(x)) if len(x) > 2 else None}
        if ratio and ratio > 10:
            flags.append(f"{m}: max is {ratio:.0f}x the 99th percentile")
    if flags:
        return _check("outliers", WARN, "Extreme values (reported, not removed): " + "; ".join(flags) +
                      ". Consider winsorised or bootstrap sensitivity analysis.", out)
    return _check("outliers", PASS, "No extreme outliers in continuous metrics" if out else "No continuous metrics", out)


def check_impossible(df: pd.DataFrame, metrics: dict[str, str], non_negative: list[str], unit_level: bool = True) -> dict:
    problems = {}
    for m, typ in metrics.items():
        if m not in df.columns or not pd.api.types.is_numeric_dtype(df[m]):
            continue
        x = df[m].dropna()
        if typ == "binary" and unit_level and not set(np.unique(x)) <= {0, 1}:
            problems[m] = f"binary metric has values outside {{0, 1}}: {sorted(set(np.unique(x)) - {0, 1})[:5]}"
        if (m in non_negative or typ in ("binary", "count")) and (x < 0).any():
            problems[m] = f"{int((x < 0).sum())} negative values"
    if problems:
        return _check("impossible values", BLOCK, "; ".join(f"{k}: {v}" for k, v in problems.items()), problems)
    return _check("impossible values", PASS, "Metric values within valid ranges", {})


def check_pre_period(df: pd.DataFrame, pre_cols: list[str], metrics: dict[str, str]) -> dict:
    if not pre_cols:
        return _check("pre-period data", PASS, "None described (CUPED not possible)", {"available": False})
    missing = [c for c in pre_cols if c not in df.columns]
    if missing:
        return _check("pre-period data", WARN, f"Described pre-period columns missing: {missing}", {"available": False})
    corr = {}
    for p in pre_cols:
        for m in metrics:
            if m in df.columns and pd.api.types.is_numeric_dtype(df[m]):
                corr[f"{p}~{m}"] = float(df[[p, m]].corr().iloc[0, 1])
    miss = {c: float(df[c].isna().mean()) for c in pre_cols}
    return _check("pre-period data", PASS, f"Available; correlations with metrics {', '.join(f'{k}={v:.2f}' for k, v in corr.items())}",
                  {"available": True, "correlation": corr, "missing_share": miss})


def check_balance(df: pd.DataFrame, variant_col: str, segment_cols: list[str], threshold: float = 0.001) -> dict:
    out, flags = {}, []
    for s in segment_cols:
        if s not in df.columns or df[s].nunique() > 50:
            continue
        tab = pd.crosstab(df[s], df[variant_col])
        if tab.shape[0] < 2:
            continue
        p = float(stats.chi2_contingency(tab, correction=False)[1])
        out[s] = {"p_value": p, "shares": (tab / tab.sum()).round(4).to_dict()}
        if p < threshold:
            flags.append(f"{s} (p = {p:.1e})")
    if flags:
        return _check("covariate balance", WARN, "Segment mix differs between variants: " + ", ".join(flags) +
                      " (can indicate an assignment or logging problem, or Simpson's paradox risk)", out)
    return _check("covariate balance", PASS, "Segment mix similar across variants" if out else "No segments to check", out)


# --------------------------------------------------------------------------- full profile


def full_profile(df: pd.DataFrame, spec: dict[str, Any]) -> dict[str, Any]:
    """Run every check. ``spec`` keys:

    unit_col, variant_col (required); control, expected_split, date_col, metrics {name: type},
    expected_columns, segments, pre_period_cols, non_negative, srm_threshold (0.001),
    allow_multiple_rows (False; True for session/event-level data), min_days (7), prefer_full_weeks (True).
    """
    unit, var = spec["unit_col"], spec["variant_col"]
    metrics = spec.get("metrics", {})
    segs = spec.get("segments", [])
    required = [unit, var]
    checks = [check_schema(df, spec.get("expected_columns") or [], required)]
    if checks[0]["verdict"] == BLOCK:
        return _summarise(checks)
    checks.append(check_dtypes(df, metrics))
    checks.append(check_missing(df, [unit, var, *metrics]))
    checks.append(check_duplicates(df, unit, spec.get("allow_multiple_rows", False)))
    checks.append(check_contamination(df, unit, var))
    checks.append(check_variants(df, var, spec.get("expected_split"), spec.get("control")))
    count_unit = unit if spec.get("allow_multiple_rows") else None
    by_cols = [c for c in [spec.get("date_col"), *segs] if c]
    checks.append(check_srm(df, var, spec.get("expected_split"), spec.get("srm_threshold", 0.001), count_unit, by_cols))
    if spec.get("date_col") and spec["date_col"] in df.columns:
        checks.append(check_dates(df, spec["date_col"], var, spec.get("min_days", 7), spec.get("prefer_full_weeks", True)))
    checks.append(check_outliers(df, metrics))
    checks.append(check_impossible(df, metrics, spec.get("non_negative", []), not spec.get("allow_multiple_rows", False)))
    checks.append(check_pre_period(df, spec.get("pre_period_cols", []), metrics))
    checks.append(check_balance(df, var, segs))
    return _summarise(checks)


def _summarise(checks: list[dict]) -> dict[str, Any]:
    verdicts = [c["verdict"] for c in checks]
    overall = BLOCK if BLOCK in verdicts else (WARN if WARN in verdicts else PASS)
    return {"verdict": overall, "checks": checks, "blocking": [c["check"] for c in checks if c["verdict"] == BLOCK]}


def profile_to_markdown(profile: dict[str, Any], title: str = "Data profile") -> str:
    """Render data_profile.md: a verdict table, then details of any warn/block checks."""
    icon = {PASS: "PASS", WARN: "WARN", BLOCK: "BLOCK"}
    lines = [f"# {title}", "", f"**Overall verdict: {icon[profile['verdict']]}**", "",
             "| Check | Verdict | Detail |", "|---|---|---|"]
    for c in profile["checks"]:
        lines.append(f"| {c['check']} | {icon[c['verdict']]} | {str(c['detail']).replace('|', '/')} |")
    flagged = [c for c in profile["checks"] if c["verdict"] != PASS]
    if flagged:
        lines += ["", "## Details of flagged checks"]
        for c in flagged:
            lines += ["", f"### {c['check']} ({icon[c['verdict']]})", "", str(c["detail"])]
            if c["check"] == "SRM" and c["verdict"] == BLOCK:
                lines += ["", "Likely causes to investigate:"] + [f"- {x}" for x in SRM_CAUSES]
                for col, rows in (c["data"].get("by") or {}).items():
                    lines += ["", f"SRM by `{col}`:", "", _records_table(rows)]
    return "\n".join(lines) + "\n"


def _worst_levels(localise: dict[str, list[dict]]) -> str:
    """Name segment levels whose own SRM test fails, e.g. 'platform=Android'."""
    hits = []
    for col, rows in localise.items():
        bad = [str(r[col]) for r in rows if r.get("srm")]
        if bad and len(bad) < len(rows):
            if len(bad) > 4:
                hits.append(f"{col} {bad[0]} to {bad[-1]} ({len(bad)} of {len(rows)} levels)")
            else:
                hits.append(f"{col}={', '.join(bad)}")
    return "; ".join(hits)


def _records_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    cols = list(rows[0])
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_fmt_cell(r[c]) for c in cols) + " |")
    return "\n".join(out)


def _fmt_cell(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.2e}" if 0 < abs(v) < 0.001 else f"{v:.4f}"
    return str(v)
