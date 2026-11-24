"""Guidance-status engine.

Rule set (applied as of the evaluation date):
  * effective              -> may be presented as a requirement
  * pending (final, not yet effective) / pending_adoption
                           -> must be labelled with its future applicability
  * draft / consultation   -> must be labelled as draft, and the answer must give
                              a way forward to adoption (e.g. confirm with the
                              agency, follow current guidance until final)
  * superseded / withdrawn -> may only be cited as historical
Anything else is a finding. Required guidance (e.g. an applicable product-
specific guidance) that the answer never cites is also a finding.
"""
from __future__ import annotations

import os
import re
from datetime import date

from .utils import ROOT, load_json, load_rubric

REGISTRY_PATH = ROOT / "knowledge" / "guidance_registry.json"

WAY_FORWARD = [
    r"until (the )?(guidance|guideline|PSG|it|they)? ?(is|are)? ?final", r"once (it is |they are )?final", r"when (it is |FDA |EMA |ICH )?final",
    r"finalis|finaliz", r"pre-?ANDA", r"(BPD|Biosimilar Product Development|scientific advice|Type [ABCD]) meeting",
    r"controlled correspondence", r"monitor", r"re-?assess", r"gap-?assess", r"confirm (it |this |the approach )?(with|in)",
    r"step 4", r"implemented regionally|regional implementation", r"final version", r"after (the )?consultation",
]


def load_registry(path=REGISTRY_PATH) -> dict:
    return load_json(path)


def evaluation_as_of() -> date:
    env = os.environ.get("PHARMAEVAL_AS_OF")
    if env:
        return date.fromisoformat(env)
    rub = load_rubric()
    if rub.get("evaluation_as_of"):
        return date.fromisoformat(rub["evaluation_as_of"])
    return date.today()


def _d(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def status_as_of(doc: dict, as_of: date) -> str:
    withdrawn = _d(doc.get("withdrawn_on"))
    if withdrawn and withdrawn <= as_of:
        return "withdrawn"
    superseded = _d(doc.get("superseded_on"))
    if superseded and superseded <= as_of:
        return "superseded"
    st = doc["status"]
    if st == "final":
        eff = _d(doc.get("effective_date"))
        return "effective" if (eff is None or eff <= as_of) else "pending"
    return st  # draft | concept | pending_adoption


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


def watchlist(registry: dict, as_of: date) -> list[dict]:
    """All tracked documents that are not plain 'effective' on the evaluation date."""
    rows = []
    for doc in registry["documents"]:
        st = status_as_of(doc, as_of)
        if st == "effective":
            continue
        row = {"id": doc["id"], "title": doc["title"], "issuer": doc["issuer"], "status": st,
               "published": doc.get("published"), "effective_date": doc.get("effective_date"),
               "url": doc.get("url"), "verified_on": doc.get("verified_on")}
        if st in ("withdrawn", "superseded"):
            rep = next((d for d in registry["documents"] if d["id"] == doc.get("superseded_by")), None)
            row["way_forward"] = (f"Do not cite as current. Use: {rep['title']}" if rep else "Do not cite as current.")
        elif st == "pending":
            row["way_forward"] = f"Final text; applies from {doc.get('effective_date')}. Prepare transition now."
        else:
            ap = doc.get("adoption_path", {})
            row["way_forward"] = " | ".join(x for x in (ap.get("stage"), "Next: " + ap["next_milestone"] if ap.get("next_milestone") else None,
                                                         "Expected: " + ap["expected"] if ap.get("expected") else None,
                                                         "Action: " + ap["action"] if ap.get("action") else None) if x)
        rows.append(row)
    return rows


def check_guidance(text: str, case: dict, registry: dict, as_of: date) -> tuple[list[dict], list[dict]]:
    """Return (guidance_citations, findings)."""
    W = registry.get("label_window_chars", 160)
    draft_l, pend_l, hist_l = registry["draft_label_patterns"], registry["pending_label_patterns"], registry["historical_label_patterns"]
    cites, findings = [], []
    cited_ids = set()
    has_way_forward = _any(WAY_FORWARD, text)

    for doc in registry["documents"]:
        m = None
        for p in doc["patterns"]:
            m = re.search(p, text, re.I)
            if m:
                break
        if not m:
            continue
        cited_ids.add(doc["id"])
        st = status_as_of(doc, as_of)
        window = text[max(0, m.start() - W): m.end() + W]
        entry = {"id": doc["id"], "title": doc["title"], "status_as_of": st, "matched": m.group(0)[:80],
                 "presented_as": None, "ok": True, "url": doc.get("url")}
        if st == "effective":
            entry["presented_as"] = "requirement"
        elif st in ("withdrawn", "superseded"):
            if _any(hist_l, window):
                entry["presented_as"] = "historical"
            else:
                entry.update(presented_as="current", ok=False)
                rule = doc.get("if_cited_as_current", {"error": "outdated_guidance", "severity": "major"})
                rep = next((d["title"] for d in registry["documents"] if d["id"] == doc.get("superseded_by")), "the current document")
                findings.append({"check": "guidance_status", "passed": False, "error": rule["error"], "severity": rule["severity"],
                                 "detail": f"Cites {st} document as current: {doc['title']}; use {rep}"})
        elif st == "pending":
            if _any(pend_l + draft_l, window):
                entry["presented_as"] = "pending (labelled)"
            else:
                entry.update(presented_as="as if in force", ok=False)
                findings.append({"check": "guidance_status", "passed": False, "error": "draft_cited_as_effective", "severity": "minor",
                                 "detail": f"{doc['title']} is final but applies only from {doc.get('effective_date')}; not labelled"})
        else:  # draft, concept, pending_adoption
            labels = draft_l + (pend_l if st == "pending_adoption" else [])
            if _any(labels, window):
                entry["presented_as"] = f"{st} (labelled)"
                ap = doc.get("adoption_path", {})
                entry["way_forward_expected"] = ap.get("action")
                if not has_way_forward:
                    entry["ok"] = False
                    findings.append({"check": "guidance_status", "passed": False, "error": "incomplete", "severity": "minor",
                                     "detail": f"Draft cited without a way forward to adoption: {doc['title']}"})
            else:
                entry.update(presented_as="as if in force", ok=False)
                findings.append({"check": "guidance_status", "passed": False, "error": "draft_cited_as_effective", "severity": "major",
                                 "detail": f"Presents a {st.replace('_', ' ')} as a requirement: {doc['title']} "
                                           f"(next step: {doc.get('adoption_path', {}).get('next_milestone', 'finalisation')})"})
        cites.append(entry)

    for rid in case.get("required_guidance", []):
        if rid not in cited_ids:
            doc = next((d for d in registry["documents"] if d["id"] == rid), None)
            name = doc["title"] if doc else rid
            findings.append({"check": "guidance_status", "passed": False, "error": "missing_applicable_guidance", "severity": "major",
                             "detail": f"Applicable guidance not cited: {name}"})
    return cites, findings
