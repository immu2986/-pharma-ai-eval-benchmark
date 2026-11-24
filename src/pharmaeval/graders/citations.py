"""Citation verification: detects fabricated or unverifiable regulatory references.

Checks ICH guideline IDs, 21 CFR parts/sections, CTD Module 3 section numbers
and EU GMP annex numbers against the curated knowledge base.
"""
from __future__ import annotations

import re

ICH_RE = re.compile(r"\bICH\s+(?:guideline\s+)?([QM]\d{1,2}[A-F]?)(?:\s*\(R\d\))?", re.I)
CFR_RE = re.compile(r"\b21\s*CFR\s*(?:Part\s*)?(\d{1,4})(?:\.(\d{1,4}))?", re.I)
CTD_RE = re.compile(r"(?<![\d.])(3\.2\.[SPAR](?:\.\d{1,2}){0,2}|3\.3)(?![\d])")
ANNEX_RE = re.compile(r"\b(?:EU\s+GMP\s+|GMP\s+)?Annex\s+(\d{1,2})\b")


def _finding(error: str, severity: str, detail: str) -> dict:
    return {"check": "citation", "passed": False, "error": error, "severity": severity, "detail": detail}


def check_citations(text: str, kb: dict) -> tuple[list[dict], list[dict]]:
    """Return (citations, findings)."""
    citations: list[dict] = []
    findings: list[dict] = []

    ich_known = {k.upper() for k in kb["ich_guidelines"]}
    for m in ICH_RE.finditer(text):
        gid = m.group(1).upper()
        ok = gid in ich_known
        status = kb["ich_guidelines"].get(gid, {}).get("status") if ok else None
        citations.append({"type": "ICH", "ref": f"ICH {gid}", "verified": ok, "status": status})
        if not ok:
            findings.append(_finding("fabricated_citation", "critical", f"ICH {gid} is not a known ICH guideline"))

    parts = kb["cfr_title21_parts"]
    sections = kb["cfr_known_sections"]
    for m in CFR_RE.finditer(text):
        part, sec = m.group(1), m.group(2)
        ref = f"21 CFR {part}" + (f".{sec}" if sec else "")
        if part not in parts:
            citations.append({"type": "CFR", "ref": ref, "verified": False})
            findings.append(_finding("unsupported_claim", "minor", f"{ref}: part not in reference set (verify manually)"))
            continue
        if sec and part in sections and f"{part}.{sec}" not in sections[part]:
            citations.append({"type": "CFR", "ref": ref, "verified": False})
            findings.append(_finding("unsupported_claim", "minor", f"{ref}: section not in reference set (verify manually)"))
            continue
        citations.append({"type": "CFR", "ref": ref, "verified": True})

    ctd_known = set(kb["ctd_module3_sections"])
    for m in CTD_RE.finditer(text):
        sec = m.group(1)
        ok = sec in ctd_known
        citations.append({"type": "CTD", "ref": sec, "verified": ok})
        if not ok:
            findings.append(_finding("fabricated_citation", "major", f"CTD section {sec} does not exist in Module 3"))

    annexes = kb["eu_gmp_annexes"]
    for m in ANNEX_RE.finditer(text):
        num = m.group(1)
        ok = num in annexes
        citations.append({"type": "EU_GMP_ANNEX", "ref": f"Annex {num}", "verified": ok})
        if not ok:
            findings.append(_finding("fabricated_citation", "major", f"EU GMP Annex {num} is not a current annex"))

    return citations, findings
