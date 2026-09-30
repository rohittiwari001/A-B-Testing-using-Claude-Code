"""Build summary.docx from results.json, intake.md, review.md and charts/manifest.json.

Standard build via abkit.report.build_standard_report, then three run-specific adjustments (every number is
formatted from results.json with abkit.results.fmt_*; caveat / next-step text is looked up by keyword, not index):
1. Page one: plain-words "how sure we are", the recommendation's condition (random assignment unconfirmed,
   reviewer note #6) and scope (no guardrail metrics, reviewer note #9), placed right after the plain-English line.
2. Segments: the builder's generic "Segments were pre-specified" text is wrong for this run (intake.md: none
   pre-specified, exploratory only) and is replaced by an exploratory / non-causal warning; the interaction-test
   line is rewritten so the Wald statistic is not read as an effect.
3. Appendix: reviewer findings rendered as clean bullets (the generic builder turns markdown tables into raw
   '|' rows and truncates at 25 items).
"""

import re
from pathlib import Path

from docx import Document

from abkit import results as R

RUN = Path(__file__).resolve().parents[1]

from abkit.report import build_standard_report  # noqa: E402

out = build_standard_report(RUN)

res = R.load_results(RUN)
summ = res["summary"]
prim = R.get_result(res, summ["primary"]["step"], summ["primary"]["index"])
bayes = R.get_result(res, "bayesian")
seg_step = R.get_step(res, "exposure_explore")
inter = next(r for r in seg_step["results"] if r["method"] == "segments.interaction_test")


def pick(items, *keywords):
    """First item containing any keyword (case-insensitive); fail loudly if the wording no longer matches."""
    for it in items:
        if any(k in it.lower() for k in keywords):
            return it
    raise KeyError(f"No summary item matching {keywords!r}; check results.json summary wording")


def prob_text(p):
    return "> 99.9%" if p is not None and p > 0.999 else R.fmt_prob(p)  # numbers-ok: display cap, same as the deck


conf = R.fmt_pct(1 - prim["alpha"], 0, signed=False)
cav_assign = pick(summ["caveats"], "assign")
cav_guard = pick(summ["caveats"], "guardrail")
step_assign = pick(summ["next_steps"], "randomly assigned", "random")

doc = Document(str(out))


def new_para(text, bold_lead=None, style=None):
    p = doc.add_paragraph(style=style) if style else doc.add_paragraph()
    if bold_lead:
        p.add_run(bold_lead).bold = True
    p.add_run(text)
    return p


def insert_after(anchor, paras):
    for p in paras:
        anchor._p.addnext(p._p)
        anchor = p
    return anchor


def find(prefix):
    return next(p for p in doc.paragraphs if p.text.startswith(prefix))


# 1. Page one -------------------------------------------------------------------------------------------------
sure = (f"Very sure the ads raise conversion. The true lift is most likely between {R.fmt_pct(prim['rel_ci_low'])} "
        f"and {R.fmt_pct(prim['rel_ci_high'])} ({conf} confidence interval); even the low end is well above the "
        f"{R.fmt_pct(summ['mde_rel'], 0)} lift we set in advance as worth acting on. The Bayesian view gives the ads a "
        f"{prob_text(bayes['probability'])} chance of beating the PSA.") \
    if prim.get("significant") and prim["rel_ci_low"] > summ["mde_rel"] else \
    (f"The lift is estimated at {R.fmt_pct(prim['rel_lift'])}, with a plausible range of {R.fmt_pct(prim['rel_ci_low'])} "
     f"to {R.fmt_pct(prim['rel_ci_high'])} ({conf} confidence interval).")
condition = ("This recommendation assumes users were randomly assigned to see ads or the PSA, which is not yet "
             f"confirmed: {cav_assign} {step_assign}")
scope = (f"{cav_guard} Guardrail metrics are checks that nothing else got worse (for example, users put off by the ads); "
         "none were available in the data.")
insert_after(find("In plain terms: "), [
    new_para(sure, "How sure we are: "),
    new_para(condition, "Condition: "),
    new_para(scope, "Only conversion was checked: "),
])

# 2. Segments -------------------------------------------------------------------------------------------------
seg_rows = [r for r in seg_step["results"] if r["method"] == "frequentist.two_proportion_ztest" and r.get("segment") != "All"]
corr = sorted({r["correction"] for r in seg_rows if r.get("correction") not in (None, "none")})
seg_warn = (f"{seg_step['data']['label']}. No segments were pre-specified: these breakdowns (by number of ads seen and "
            f"by the day a user saw most ads) were added for exploration only. P-values are corrected within each "
            f"breakdown ({', '.join('-'.join(w.capitalize() for w in c.split('-')) for c in corr)}). Users who saw more ads are different people from those who saw few, so "
            f"these results do not show that more ads cause more lift. Buckets that are not significant are "
            f"inconclusive (wide ranges), not evidence of no effect.")
generic = find("No segments were pre-specified")      # builder's exploratory sentence, replaced by the run-specific one
seg_par = next(p for p in doc.paragraphs if p.style.name == "Heading 1" and p.text == "Segments")
generic._p.getparent().remove(generic._p)
insert_after(seg_par, [new_para(seg_warn)])

inter_par = find(f"Interaction test for {inter['segment']}")
inter_par.text = ""
inter_par.add_run(f"Interaction test for {inter['segment']}: ").bold = True
inter_par.add_run(f"{R.fmt_p_stat(inter.get('p_value'))} (Wald chi-square {R.fmt_num(inter.get('estimate'), 1)}). "
                  "The lift differs across ads-seen buckets, but because ads seen is measured during the test this is "
                  "descriptive, not a dose-response. Test ad frequency directly in a new randomised test before acting on it.")

# 3. Appendix reviewer findings ---------------------------------------------------------------------------------
review = (RUN / "review.md").read_text(encoding="utf-8")
latest = [r for r in re.split(r"^(?=# Review)", review, flags=re.M) if r.strip()][-1]
items, buf, header = [], [], None


def flush():
    if buf:
        items.append(" ".join(buf))
        buf.clear()


for ln in latest.splitlines()[1:]:
    s = ln.strip()
    if not s or s.startswith("#"):
        flush()
        continue
    if s.startswith("|"):
        flush()
        cells = [c.strip() for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if header is None:
            header = cells
            continue
        items.append(f"#{cells[0]} {cells[1]}: " + "; ".join(f"{h.lower()} {c}" for h, c in zip(header[2:], cells[2:])))
        continue
    header = None
    m = re.match(r"^([-*]|\d+\.)\s+(.*)", s)
    if m:
        flush()
        buf.append(m.group(2))
    else:
        buf.append(s)
flush()
items = [re.sub(r"\*\*(.+?)\*\*", r"\1", i) for i in items]

rev_head = find("Review: ")
nxt = rev_head._p.getnext()
while nxt is not None and not (nxt.tag.endswith("}p") and "".join(nxt.itertext()).startswith("Table ")):
    following = nxt.getnext()
    nxt.getparent().remove(nxt)
    nxt = following
insert_after(rev_head, [new_para(i, style="List Bullet") for i in items])

doc.save(str(out))
print(out)
