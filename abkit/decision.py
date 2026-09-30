"""Turn results into a recommendation: ship / don't ship / iterate / extend.

The logic follows interpretation_and_decisions.md:

- primary significantly worse                      -> don't ship
- a guardrail breached                             -> don't ship (or iterate if the primary won)
- primary significantly better, >= practical MDE   -> ship
- primary significantly better, < practical MDE    -> iterate (real but small effect: weigh the cost)
- not significant, CI rules out the MDE            -> iterate (well-powered null: idea does not move the metric)
- not significant, CI still includes the MDE       -> extend (inconclusive / underpowered - NOT "no effect")

:func:`build_summary` writes ``results.json -> summary`` with a headline and key
numbers generated only from stored results, so deck and report never re-type numbers.

Example
-------
>>> from abkit.decision import recommend
>>> recommend({"rel_lift": 0.032, "rel_ci_low": 0.01, "rel_ci_high": 0.05, "p_value": 0.004, "significant": True})["verdict"]
'ship'
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from abkit import results as R

VERDICTS = {
    "ship": {"label": "Ship", "color": "positive"},
    "dont_ship": {"label": "Don't ship", "color": "negative"},
    "iterate": {"label": "Iterate", "color": "neutral"},
    "extend": {"label": "Extend the test / inconclusive", "color": "neutral"},
    "blocked": {"label": "Blocked: data issue", "color": "negative"},
    "plan": {"label": "Test plan", "color": "accent"},
}


def _d(r: Any) -> dict[str, Any]:
    return r.to_dict() if hasattr(r, "to_dict") else dict(r)


def recommend(primary: Any, guardrails: Iterable[Any] = (), mde_rel: float | None = None, direction: str = "increase",
              prob_threshold: float = 0.95) -> dict[str, Any]:
    """Return ``{verdict, label, color, reason, caveats}`` for a primary result and guardrail results."""
    p = _d(primary)
    gs = [_d(g) for g in guardrails]
    good = 1 if direction in ("increase", "no_decrease") else -1
    rel = p.get("rel_lift") or 0.0
    lo, hi = p.get("rel_ci_low"), p.get("rel_ci_high")
    if p.get("p_value") is None and p.get("probability") is not None:
        sig_pos = p["probability"] >= prob_threshold
        sig_neg = p["probability"] <= 1 - prob_threshold
    else:
        sig = bool(p.get("significant"))
        sig_pos, sig_neg = sig and rel * good > 0, sig and rel * good < 0
    breaches = [g.get("metric") for g in gs if (g.get("extra") or {}).get("status") == "breach"]
    unclear = [g.get("metric") for g in gs if (g.get("extra") or {}).get("status") == "inconclusive"]
    caveats = [f"Guardrail {m} is inconclusive (cannot rule out harm beyond the margin)." for m in unclear]

    if sig_neg:
        v, why = "dont_ship", "The primary metric moved significantly in the wrong direction."
    elif breaches:
        v = "iterate" if sig_pos else "dont_ship"
        why = f"Guardrail breached: {', '.join(breaches)}." + (" The primary metric improved, so fix the side effect and retest." if sig_pos else "")
    elif sig_pos:
        if mde_rel is not None and abs(rel) < mde_rel:
            v, why = "iterate", f"The effect is statistically significant but smaller than the practical threshold ({R.fmt_pct(mde_rel)})."
        else:
            v, why = "ship", "The primary metric improved significantly and no guardrail was breached."
    else:
        bound = hi if good > 0 else (-lo if lo is not None else None)
        if mde_rel is not None and bound is not None and bound < mde_rel:
            v, why = "iterate", f"No significant effect, and the CI rules out a lift as large as the practical threshold ({R.fmt_pct(mde_rel)})."
        else:
            v, why = "extend", "No significant effect, but the CI is too wide to rule out a meaningful lift: the result is inconclusive, not 'no effect'."
    return {"verdict": v, **VERDICTS[v], "reason": why, "caveats": caveats}


def build_summary(
    run_dir: str | Path, primary_step: str, script: str, guardrail_step: str | None = None, mde_rel: float | None = None,
    direction: str = "increase", caveats: Iterable[str] = (), next_steps: Iterable[str] = (), primary_index: int = 0,
    prob_threshold: float = 0.95, extra_key_numbers: Iterable[dict[str, str]] = (), metric_label: str | None = None,
) -> dict[str, Any]:
    """Write ``summary`` into results.json from stored results and return it."""
    res = R.load_results(run_dir)
    p = R.get_step(res, primary_step)["results"][primary_index]
    gs = R.get_step(res, guardrail_step)["results"] if guardrail_step else []
    rec = recommend(p, gs, mde_rel, direction, prob_threshold)
    level = round((1 - (p.get("alpha") or 0.05)) * 100)
    metric = metric_label or p.get("metric") or "the primary metric"
    tr, ct = p.get("treatment") or "Treatment", p.get("control") or "control"
    rel = p.get("rel_lift")
    verb = "raises" if (rel or 0) > 0 else "lowers"
    if p.get("p_value") is not None:
        sig_txt = "statistically significant" if p.get("significant") else "not statistically significant"
        stat_txt = R.fmt_p_stat(p.get("p_value_adjusted") or p["p_value"])
    else:
        sig_txt = f"P(better than {ct}) = {R.fmt_prob(p.get('probability'))}"
        stat_txt = sig_txt
    headline = f"{tr} {verb} {metric} by {R.fmt_pct(abs(rel or 0), signed=False)} vs {ct} ({sig_txt})"
    headline = headline[0].upper() + headline[1:]
    mtype = "binary" if any(k in p.get("method", "") for k in ("proportion", "beta_binomial")) else None
    key = [
        {"label": f"Relative lift in {metric}", "value": f"{R.fmt_pct(rel)} ({level}% CI {R.fmt_ci(p.get('rel_ci_low'), p.get('rel_ci_high'))})"},
        {"label": "Evidence", "value": stat_txt},
        {"label": f"{metric}: {ct} vs {tr}", "value": f"{R.fmt_value(p.get('control_value'), mtype)} vs {R.fmt_value(p.get('treatment_value'), mtype)}"},
        {"label": "Units analysed", "value": " / ".join(f"{k}: {R.fmt_num(v)}" for k, v in (p.get("n") or {}).items())},
    ]
    for g in gs:
        st = (g.get("extra") or {}).get("status", "n/a")
        key.append({"label": f"Guardrail {g.get('metric')}", "value": f"{st} ({R.fmt_pct(g.get('rel_lift'))})"})
    key.extend(extra_key_numbers)
    summary = {
        "plain_english": plain_english(p, metric, mtype),
        "verdict": rec["verdict"], "verdict_label": rec["label"], "verdict_color": rec["color"], "reason": rec["reason"],
        "headline": headline, "key_numbers": key, "caveats": [*rec["caveats"], *caveats], "next_steps": list(next_steps),
        "primary": {"step": primary_step, "index": primary_index}, "mde_rel": mde_rel,
    }
    R.set_summary(run_dir, summary, script)
    return summary


def plain_english(p: dict[str, Any], metric: str, metric_type: str | None) -> str:
    """One or two sentences a non-statistician can read, built only from the result's numbers."""
    tr, ct = p.get("treatment") or "the new version", p.get("control") or "the current version"
    est = p.get("estimate") or 0.0
    if metric_type == "binary":
        per_k = abs(est) * 1000
        first = (f"for every 1,000 users, about {per_k:,.0f} {'more' if est > 0 else 'fewer'} achieved {metric} "
                 f"with {tr} than with {ct}.")
    else:
        first = f"average {metric} was {R.fmt_num(abs(est))} {'higher' if est > 0 else 'lower'} with {tr} than with {ct}."
    if p.get("p_value") is not None:
        second = ("A difference this large is unlikely to be down to chance." if p.get("significant")
                  else "A difference this size could easily be down to chance, so we cannot yet say the change made a difference.")
    else:
        second = f"There is a {R.fmt_prob(p.get('probability'))} chance that {tr} is genuinely better."
    return f"{first[0].upper()}{first[1:]} {second}"


def build_blocked_summary(run_dir: str | Path, script: str, next_steps: Iterable[str] = (), caveats: Iterable[str] = ()) -> dict[str, Any]:
    """Summary for a run stopped at validation (e.g. SRM): verdict 'blocked', numbers from the validation checks."""
    res = R.load_results(run_dir)
    val = res.get("validation") or {}
    blocking = [c for c in val.get("checks", []) if c["verdict"] == "block"]
    if not blocking:
        raise ValueError("No blocking validation check in results.json; use build_summary instead")
    key: list[dict[str, str]] = []
    headline = f"Results withheld: blocking data issue ({', '.join(c['check'] for c in blocking)})"
    srm = next((c for c in blocking if c["check"] == "SRM"), None)
    if srm:
        d = srm["data"]
        obs, exp = d["extra"]["observed_share"], d["extra"]["expected_share"]
        short = min(obs, key=lambda k: obs[k] - exp[k])
        headline = (f"Results withheld: {short} has {R.fmt_pct(obs[short] / exp[short] - 1, signed=False).lstrip(chr(0x2212))} "
                    f"fewer units than the intended split ({R.fmt_p_stat(d['p_value'])}, sample ratio mismatch)")
        key += [{"label": f"Observed share {k}", "value": f"{R.fmt_prob(obs[k])} (expected {R.fmt_prob(exp[k])})"} for k in obs]
        key.append({"label": "SRM test", "value": f"chi-square {R.fmt_p_stat(d['p_value'])} (threshold {d['extra']['threshold']})"})
        where = srm["detail"].split("Concentrated in: ")[-1] if "Concentrated in" in srm["detail"] else None
        if where:
            key.append({"label": "Concentrated in", "value": where})
    for c in blocking:
        if c["check"] != "SRM":
            key.append({"label": c["check"], "value": str(c["detail"])[:120]})
    summary = {
        "verdict": "blocked", "verdict_label": VERDICTS["blocked"]["label"], "verdict_color": VERDICTS["blocked"]["color"],
        "reason": "The data failed a blocking validation check, so treatment effects cannot be trusted.",
        "headline": headline, "plain_english": ("The groups being compared are not the ones the experiment created, so any "
                                                 "difference between them could come from the data problem rather than the change."),
        "key_numbers": key[:5], "caveats": list(caveats), "next_steps": list(next_steps), "primary": None, "mde_rel": None,
    }
    R.set_summary(run_dir, summary, script)
    return summary
