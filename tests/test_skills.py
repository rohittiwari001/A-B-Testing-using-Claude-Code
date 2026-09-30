"""Skills are well-formed: frontmatter, required reference files and sections, working links."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
REQUIRED_SKILLS = ["experiment-intake", "ab-methods", "consulting-charts", "deck-style", "report-style", "stat-defaults"]
AB_REFS = ["power_and_mde", "frequentist_tests", "bayesian", "srm", "cuped", "sequential_testing", "ratio_metrics_delta_method",
           "multiple_testing", "multi_arm", "heterogeneous_effects", "novelty_primacy", "guardrails", "quasi_experiments",
           "interpretation_and_decisions"]
SECTIONS = ["When to use", "Assumptions", "Step-by-step procedure", "abkit function(s)", "How to interpret",
            "Common pitfalls", "How to present it"]


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} has no YAML frontmatter"
    return yaml.safe_load(m.group(1))


@pytest.mark.parametrize("name", REQUIRED_SKILLS)
def test_skill_frontmatter(name):
    fm = frontmatter(SKILLS / name / "SKILL.md")
    assert fm["name"] == name
    assert len(fm["description"]) > 80 and "Use" in fm["description"]


@pytest.mark.parametrize("ref", AB_REFS)
def test_ab_methods_reference_sections(ref):
    text = (SKILLS / "ab-methods" / "references" / f"{ref}.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", text, re.M)
    assert headings == SECTIONS, f"{ref}: {headings}"


def test_skill_links_resolve():
    for md in SKILLS.rglob("*.md"):
        for link in re.findall(r"\]\(([^)#]+\.md)\)", md.read_text(encoding="utf-8")):
            assert (md.parent / link).is_file(), f"{md}: broken link {link}"


def test_abkit_functions_named_in_skills_exist():
    import importlib

    text = "\n".join(p.read_text(encoding="utf-8") for p in SKILLS.rglob("*.md"))
    mods = ["power", "frequentist", "bayesian", "validation", "variance_reduction", "sequential", "ratio_metrics",
            "multiple_testing", "segments", "time_effects", "quasi", "decision", "io", "state", "results"]
    for mod in mods:
        m = importlib.import_module(f"abkit.{mod}")
        for fn in set(re.findall(rf"\b{mod}\.([a-z_]+)\(", text)):
            assert hasattr(m, fn), f"skills reference abkit.{mod}.{fn} which does not exist"
