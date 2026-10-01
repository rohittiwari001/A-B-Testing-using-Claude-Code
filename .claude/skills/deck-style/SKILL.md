---
name: deck-style
description: The consulting storyline, slide anatomy, layout and wording rules for every experiment readout deck (deck.pptx) built with abkit.deck (python-pptx, 16:9, no template). Every deck follows the same flow whatever the problem - answer first, then the ask, approach, findings, impact, recommendation - in the style of a top-tier strategy consulting deck. Use when building, extending or reviewing a deck (deck-builder agent, 40_deck_*.py scripts), and when writing the summary inputs that feed it (stats-analyst summary step, viz-designer charts).
---

# Deck style: the consulting storyline

A partner at a top consulting firm should be able to read only the slide titles and know the whole story,
and a busy executive should be able to stop after slide 2 and still know the answer. The deck is built
automatically by `abkit.deck.build_standard_deck`; this skill explains the storyline it produces, what each
slide needs as input, and the rules for anything you add by hand.

## 1. Principles

1. **Answer first (pyramid principle).** The executive summary states the recommendation and the evidence before
   any detail. Never build up to a reveal.
2. **One fixed storyline, whatever the problem.** Every deck has the same five chapters, so stakeholders always
   know where they are. Only the Findings chapter changes with the problem type.
3. **One message per slide.** The action title *is* the message: a full sentence with the number
   ("Ads lift conversion by +43.1% vs PSA, above the 5% threshold"), never a topic ("Results").
4. **The ghost-deck test.** Read the titles alone, top to bottom, in `deck_storyline.md`. They must tell
   the story: question -> approach -> what we found -> what it is worth -> what to do. If a title doesn't advance the
   story, rewrite it or cut the slide.
5. **So what, always.** Every finding is followed by what it means for the business; every number has units and a range.
6. **Evidence in the main story, detail in the appendix.** Data validation, full tables and method details go to the
   appendix unless they *are* the finding (e.g. a blocked run).
7. **Nothing typed by hand.** Every number comes from results.json via `abkit.results.fmt_*`.

## 2. The storyline (built by `build_standard_deck`)

| # | Slide | Chapter tracker | Purpose | Content comes from |
|---|---|---|---|---|
| 1 | Title | - | Experiment name, the headline, date | state.title, summary.headline |
| 2 | **Executive summary** | - | The whole answer on one page: verdict panel (green / red / amber) on the left; *The ask, What we found, What it means, What we recommend, Main caveat* on the right | intake.md business question, summary key_numbers / plain_english / next_steps[0] / caveats[0] |
| 3 | Agenda | - | The five chapters (+ appendix) | fixed |
| 4 | **The ask** | 1 The ask | The question (as the title), the decision, the hypothesis, what success looks like; "What was tested" fact table (groups, split, unit, period, metric, guardrails, threshold) | intake.md (Business question, Decision to be made, Hypothesis), state.json metrics / design, validation |
| 5 | **Approach** | 2 Approach | Chevron flow: Data -> Quality checks -> Analysis -> Review, each with one or two plain sentences | validation checks, results steps (method names), review.md rounds, gates |
| 6+ | **Findings** | 3 Findings | One chart slide per message with three numbered takeaways; headline result first, then supporting evidence, then breakdowns; guardrail table if guardrails exist | charts/manifest.json (in saved order), results.json |
| n | **Impact** | 4 Impact | Up to four big-number tiles plus a "So what" bar: what the result is worth in business terms | summary.impact / impact_headline / so_what (derived from the primary result if absent) |
| n+1 | **Risks** | 5 Recommendation | "N caveats could change or qualify this conclusion" | summary.caveats + failed assumptions |
| n+2 | **Recommendation** | 5 Recommendation | Decision banner, the reason, and a next-steps table: # / Action / Owner / Timing | summary.verdict, reason, next_steps |
| A | Appendix | - | Divider, methodology (tests + scripts), validation (charts + checks table), full results, appendix charts | results.json, manifest |

Every content slide has the chapter tracker (top), an action title (max two lines, accent underline), the content,
the footer (source note + page number) and speaker notes stating the slide's one point.

### What changes with the problem type: the Findings chapter only

`state.plan.deck_sections` selects the findings modules and their order: `results`, `secondary`, `guardrails`,
`segments`, `time`, `power`, plus `appendix` (include it unless the deck must be very short). Older names
(`exec_summary`, `setup`, `risks`, `next_steps`) are accepted and ignored: those slides are always built.
`validation` evidence moves into the main story automatically when the run is blocked.

| Problem | Findings chapter | Impact chapter shows | Typical length |
|---|---|---|---|
| Standard readout | headline lift -> levels -> guardrails -> segments / time | lift, absolute change, units, business value | 12-16 |
| Power analysis | sample size vs MDE, power curve | users and days needed, MDE achievable | 9-10 |
| Blocked (SRM / bad data) | split chart(s) + validation table | what we can and cannot conclude | 8-9 |
| Multi-arm | lift per arm, levels per arm | best arm's value vs control | 12-16 |
| CUPED / ratio / sequential | adjusted vs unadjusted, CI width, boundaries | lift and precision gained | 11-14 |
| Quasi-experiment | treated vs control trends, DiD estimate, placebo | estimated effect and its range | 11-14 |

## 3. Feeding the storyline (inputs other agents must provide)

- **intake.md** must have `## Business question`, `## Decision to be made`, `## Hypothesis` headings (the
  intake template has them). The business question becomes the title of "The ask".
- **Summary** (`abkit.decision.build_summary`, written by the stats-analyst):
  - `metric_label`, `treatment_label`, `control_label`: business names, not column names.
  - `impact`: 2-4 tiles `{"value", "label", "note"}`, biggest business number first, each with its range in `note`.
  - `impact_headline`: the business-terms action title ("The ads produced about 4,343 extra conversions").
  - `so_what`: one sentence turning the impact into a decision ("Campaign value = extra conversions × value per
    conversion; compare with ad spend").
  - `next_steps`: 3-5 items as `"Owner: action (timing)"`, e.g. `"Data owner: confirm random assignment (within 1 week)"`,
    or dicts `{"action", "owner", "timing"}`. The first step is shown on the executive summary.
  - `caveats`: short (under 15 words each, about 60 words in total); the most important first (it is shown as the
    "Main caveat" on the executive summary).
- **Charts** (`save_chart`, viz-designer): save the headline chart of each section first (slide order = save order);
  three takeaways each; `tag="Exploratory"` (or "Preliminary", "Directional") for evidence that is not confirmatory.

## 4. Building

```python
"""Build deck.pptx for <run>."""
from pathlib import Path
from abkit.deck import build_standard_deck
RUN = Path(__file__).resolve().parents[1]
print(build_standard_deck(RUN))     # also writes deck_storyline.md (and deck_warnings.txt if limits are broken)
```

Custom slides: use `abkit.deck.Deck` primitives (`context`, `approach`, `impact`, `recommendation`, `chart`,
`two_charts`, `table`, `bullets`) with a `chapter=` from `abkit.deck.builder.CHAPTERS`, reading every number from
results.json. Never type a result into a string (the numbers_guard hook checks 40_ scripts).

## 5. Writing rules

- **Action titles:** a full sentence with the number and the verdict word (significant / not significant /
  inconclusive). Max about 130 characters (two lines). No questions, except that the title of "The ask" slide *is* the question.
- **Body text:** about 40 words per chart slide; the builder warns above the limits (exec summary 130, ask 90,
  impact 90, approach 110, risks 70). Fix warnings at the source text (summary script, chart script), never by
  shrinking fonts.
- **Numbers:** changes signed with one decimal (+3.2%); p-values to three decimals or "<0.001"; levels with units;
  every estimate with its range in the takeaways or tile note.
- **Language:** plain business English first, statistical term second ("a difference this large is unlikely to be
  chance (p < 0.001)"). Say "inconclusive", not "no effect", when the range includes the practical threshold.
- **Recommendations:** verb first, specific, with owner and timing ("Finance: agree a value per conversion (within 2 weeks)").
- **Consistency:** the same business names for groups and metrics on every slide (summary labels, chart titles).

## 6. Visual rules

- 16:9, Arial, the abkit palette only: navy for structure, accent blue for the one thing to look at, green / red /
  amber only for verdicts and status, greys for context.
- Left-aligned text, generous white space, at most one visual idea per slide; charts at about 65% width with
  takeaways on the right.
- Verdict colour is consistent: green = ship / pass, red = don't ship / breach / blocked, amber = iterate / extend / inconclusive.
- Stickers (amber) mark exploratory or preliminary evidence; never hide that label.

## 7. Pre-delivery checklist

- [ ] `deck_storyline.md` passes the ghost-deck test (titles alone tell the story).
- [ ] The executive summary answers the ask, shows the verdict, 3-5 numbers, the meaning, the first action and the main caveat.
- [ ] "The ask" restates the question, the decision and the success criterion before any result.
- [ ] Findings: the headline result comes first; every chart slide has three takeaways; exploratory evidence is tagged.
- [ ] The Impact slide expresses the result in business terms with ranges.
- [ ] Every next step has an owner and a timing.
- [ ] No `deck_warnings.txt`; `python -m abkit.tracecheck <run-id>` passes.
