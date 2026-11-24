"""Regulatory filing-category checks (USFDA supplements, EU variation types).

Under-filing (recommending a lower category than required) is critical because
it can put product on the market without required approval. Over-filing is a
major error (avoidable regulatory burden and delay).
"""
from __future__ import annotations

import re

LINE_RE = re.compile(r"^\s*Recommended filing\s*:\s*(.+?)\s*$", re.I | re.M)

RANK = {
    "FDA": {"AR": 0, "CBE-0": 1, "CBE-30": 2, "PAS": 3},
    "EMA": {"IA": 0, "IAIN": 1, "IB": 2, "II": 3, "EXT": 4},
}


def recommended_line(text: str) -> str | None:
    matches = LINE_RE.findall(text)
    return matches[-1] if matches else None


def categories_in(text: str, kb: dict) -> list[tuple[str, str]]:
    found = []
    for jur, cats in kb["filing_categories"].items():
        for cat, spec in cats.items():
            if any(re.search(p, text, re.I) for p in spec["patterns"]):
                found.append((jur, cat))
    return found


def _f(error, severity, detail, passed=False):
    return {"check": "filing", "passed": passed, "error": error, "severity": severity, "detail": detail}


def check_filing(text: str, case: dict, kb: dict) -> tuple[dict, list[dict]]:
    """Return (summary, findings). summary['scored'] tells whether a pass/fail item counts toward coverage."""
    needs_line = "recommended_filing_line" in case.get("format_requirements", [])
    line = recommended_line(text)
    summary = {"line": line, "categories": [], "scored": False, "passed": None}
    findings: list[dict] = []
    if not needs_line:
        return summary, findings
    if line is None:
        findings.append(_f("instruction_violation", "major", "Missing required 'Recommended filing:' line"))
        if case.get("expected_filing"):
            summary.update(scored=True, passed=False)
        return summary, findings

    cats = categories_in(line, kb)
    summary["categories"] = [f"{j}:{c}" for j, c in cats]
    case_jur = case["jurisdiction"]
    if case_jur in ("FDA", "EMA"):
        foreign = [c for j, c in cats if j != case_jur]
        if foreign:
            findings.append(_f("jurisdiction_confusion", "critical",
                               f"Recommends {', '.join(foreign)} for a {case_jur} procedure"))

    exp = case.get("expected_filing")
    if not exp:
        if not cats:
            findings.append(_f("wrong_filing_category", "critical", f"No valid filing category recommended: '{line}'"))
        return summary, findings

    summary["scored"] = True
    jur, want = exp["jurisdiction"], exp["category"]
    same_jur = [c for j, c in cats if j == jur]
    if not same_jur:
        summary["passed"] = False
        findings.append(_f("wrong_filing_category", "critical", f"Expected {jur} {want}; got '{line}'"))
        return summary, findings
    if same_jur == [want]:
        summary["passed"] = True
        return summary, findings
    if want in same_jur:
        summary["passed"] = True
        findings.append(_f("instruction_violation", "minor", f"Hedged between {same_jur}; expected a single category {want}"))
        return summary, findings
    got = max(same_jur, key=lambda c: RANK[jur][c])
    summary["passed"] = False
    if RANK[jur][got] < RANK[jur][want]:
        findings.append(_f("wrong_filing_category", "critical", f"Under-filing: recommended {got}, required {want}"))
    else:
        findings.append(_f("wrong_filing_category", "major", f"Over-filing: recommended {got}, required {want}"))
    return summary, findings
