"""Content checks: required-point coverage, forbidden claims, abstention and context grounding."""
from __future__ import annotations

import re

STOP = set("a an the of to and or in on for with by is are be as at that this from it its was were can may must should "
           "under per not no only if then than into which when where whether".split())


def check_required_points(text: str, case: dict) -> tuple[list[dict], list[dict]]:
    hits = []
    for rp in case.get("required_points", []):
        ok = any(re.search(p, text, re.I) for p in rp["any_of"])
        hits.append({"id": rp["id"], "description": rp["description"], "covered": ok})
    findings = []
    if hits:
        missing = [h for h in hits if not h["covered"]]
        if missing:
            ratio = 1 - len(missing) / len(hits)
            sev = "minor" if ratio >= 0.75 else "major"
            findings.append({"check": "coverage", "passed": False, "error": "incomplete", "severity": sev,
                             "detail": "Missing: " + "; ".join(m["description"] for m in missing)})
    return hits, findings


def check_forbidden(text: str, case: dict) -> list[dict]:
    out = []
    for fc in case.get("forbidden_claims", []):
        m = re.search(fc["pattern"], text, re.I)
        if m:
            out.append({"check": "forbidden_claim", "passed": False, "error": fc["error"], "severity": fc["severity"],
                        "detail": f"{fc['description']}: \"{m.group(0)[:80]}\""})
    return out


def is_abstention(text: str, kb: dict) -> bool:
    return any(re.search(p, text, re.I) for p in kb["abstention_patterns"])


def check_abstention(text: str, case: dict, kb: dict) -> tuple[dict, list[dict]]:
    abstained = is_abstention(text, kb)
    if case.get("expect_abstention"):
        if abstained:
            return {"scored": True, "passed": True, "abstained": True}, []
        return {"scored": True, "passed": False, "abstained": False}, [{
            "check": "abstention", "passed": False, "error": "failed_to_abstain", "severity": "critical",
            "detail": "Answered as if an unverifiable source exists (hallucinated content)"}]
    if abstained and len(text.split()) < 40:
        return {"scored": False, "abstained": True}, [{
            "check": "abstention", "passed": False, "error": "inappropriate_abstention", "severity": "major",
            "detail": "Declined an answerable question"}]
    return {"scored": False, "abstained": abstained}, []


def _content_words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9\-\.]+", s.lower()) if w not in STOP and len(w) > 2}


def context_support_rate(text: str, context: list[str], threshold: float = 0.3) -> float | None:
    """Share of response sentences whose content words overlap the retrieved context by >= threshold."""
    if not context:
        return None
    ctx = _content_words(" ".join(context))
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n", text) if len(s.split()) >= 5]
    if not sentences:
        return 0.0
    supported = 0
    for s in sentences:
        words = _content_words(s)
        if words and len(words & ctx) / len(words) >= threshold:
            supported += 1
    return round(supported / len(sentences), 3)
