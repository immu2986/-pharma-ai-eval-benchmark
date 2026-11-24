"""Dosage-form applicability of the f2 similarity factor.

f2 compares dissolution / drug-release profiles. It has no meaning where the drug is
already in solution (most parenterals: solutions, monoclonal antibodies, biosimilars,
peptide solutions such as GLP-1 products), where sameness rests on Q1/Q2 equivalence,
physicochemical characterisation and, for biologics, ICH Q5E comparability.

It can be used, with care, for complex injectables whose drug release is a critical
quality attribute (injectable suspensions, PLGA microspheres, liposomes, implants,
in-situ gels). There the usual f2 preconditions (>= 3 time points, at most one point
above 85 %, low variability) are often not met, and FDA product-specific guidances may
ask for "a proper statistical method" instead, so the answer must address those caveats.

Classification comes from the case's `release_comparison` field when set, otherwise it
is inferred from `dosage_form`.
"""
from __future__ import annotations

import re

F2_MENTION = re.compile(r"\bf\s?2\b|f₂|similarity factor", re.I)

CONDITIONAL_FORM = re.compile(
    r"suspension|microsphere|liposom|implant|depot|long[- ]acting|in[- ]situ|emulsion|"
    r"extended[- ]release inject", re.I)
NOT_APPLICABLE_FORM = re.compile(
    r"\bsolution\b|monoclonal|\bmabs?\b|antibod|biosimilar|biologic|therapeutic protein|vaccine|"
    r"lyophili[sz]ed powder for (injection|solution)", re.I)

# An f2 mention in a sentence that rejects it is correct behaviour, not an error.
NEGATION = re.compile(
    r"not applicable|\bn/?a\b|does ?n[o']t apply|not appropriate|inappropriate|not relevant|not meaningful|"
    r"cannot be (used|applied)|should not be (used|applied)|is not used|no dissolution|no release profile|"
    r"(instead of|rather than|not) (an? )?f\s?2", re.I)

# What a sound answer says when it does use f2 for a complex injectable.
CAVEATS = re.compile(
    r"85\s?%|\bCV\b|coefficient of variation|variabilit|bootstrap|multivariate|\bMSD\b|Mahalanobis|"
    r"product[- ]specific guidance|\bPSG\b|proper statistical method|accelerated (IVRT|in vitro|release)", re.I)

SENTENCE = re.compile(r"(?<=[.!?;\n])\s+")


def classify(case: dict) -> str | None:
    """Return 'not_applicable', 'conditional', 'applicable' or None (cannot tell)."""
    explicit = case.get("release_comparison")
    if explicit:
        return explicit
    form = case.get("dosage_form", "")
    if CONDITIONAL_FORM.search(form):
        return "conditional"
    if NOT_APPLICABLE_FORM.search(form):
        return "not_applicable"
    return None


def affirmative_f2(text: str) -> list[str]:
    """Sentences that use f2 without rejecting it."""
    return [s.strip() for s in SENTENCE.split(text) if F2_MENTION.search(s) and not NEGATION.search(s)]


def check_f2_applicability(text: str, case: dict) -> tuple[dict, list[dict]]:
    cls = classify(case)
    summary = {"release_comparison": cls, "f2_used": False}
    if cls not in ("not_applicable", "conditional"):
        return summary, []
    used = affirmative_f2(text)
    summary["f2_used"] = bool(used)
    if not used:
        return summary, []
    form = case.get("dosage_form", "this dosage form")
    if cls == "not_applicable":
        return summary, [{"check": "f2_applicability", "passed": False, "error": "method_not_applicable", "severity": "major",
                          "detail": (f"Applies f2 to '{form}'. The drug is in solution (or is a biologic), so there is no "
                                     "dissolution profile to compare; use Q1/Q2 sameness, characterisation or ICH Q5E comparability.")}]
    if not CAVEATS.search(text):
        return summary, [{"check": "f2_applicability", "passed": False, "error": "method_not_applicable", "severity": "minor",
                          "detail": (f"Uses f2 for '{form}' without addressing its preconditions (time points, 85 % rule, "
                                     "variability) or the statistical method named in the product-specific guidance.")}]
    return summary, []
