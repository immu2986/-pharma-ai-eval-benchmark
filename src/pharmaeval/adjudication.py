"""Disagreement detection, adjudication queue and signed adjudication records."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from .agreement import group_by_item
from .audit import log_event
from .schemas import DIMENSIONS, Adjudication
from .utils import DATA, REPORTS, SEVERITY_RANK, load_annotations, load_jsonl, load_rubric

ADJ_PATH = DATA / "adjudications.jsonl"


def load_adjudications() -> dict[tuple, dict]:
    if not ADJ_PATH.exists():
        return {}
    return {(a["case_id"], a["model_id"]): a for a in load_jsonl(ADJ_PATH)}


def majority(values: list[str], rank: dict | None = None) -> str:
    """Most common value; ties broken toward the most severe (conservative)."""
    counts = Counter(values)
    top = max(counts.values())
    tied = [v for v, c in counts.items() if c == top]
    if rank:
        return max(tied, key=lambda v: rank[v])
    return sorted(tied)[0]


def disagreement_reasons(evals: dict[str, dict], auto: dict | None, rules: dict) -> list[str]:
    anns = list(evals.values())
    reasons = []
    if rules.get("label_mismatch") and len({a["primary_error"] for a in anns}) > 1:
        reasons.append("error_label_mismatch")
    if rules.get("severity_mismatch") and len({a["severity"] for a in anns}) > 1:
        reasons.append("severity_mismatch")
    rng = rules.get("dimension_score_range", 2)
    wide = [d for d in DIMENSIONS if max(a["scores"][d] for a in anns) - min(a["scores"][d] for a in anns) >= rng]
    if wide:
        reasons.append("score_spread:" + ",".join(wide))
    if rules.get("auto_human_critical_conflict") and auto is not None:
        human_sev = majority([a["severity"] for a in anns], SEVERITY_RANK)
        if (auto["auto_severity"] == "critical") != (human_sev == "critical"):
            reasons.append(f"auto_vs_human_critical(auto={auto['auto_severity']},human={human_sev})")
    return reasons


def build_queue() -> list[dict]:
    rubric = load_rubric()
    items = group_by_item(load_annotations())
    autos = {(g["case_id"], g["model_id"]): g for g in load_jsonl(REPORTS / "auto_grades.jsonl") if g["sample_index"] == 0}
    adjudicated = load_adjudications()
    queue = []
    for key, evals in sorted(items.items()):
        reasons = disagreement_reasons(evals, autos.get(key), rubric["disagreement_rules"])
        if not reasons:
            continue
        adj = adjudicated.get(key)
        row = {"case_id": key[0], "model_id": key[1], "reasons": " | ".join(reasons),
               "auto_error": autos.get(key, {}).get("auto_primary_error"), "auto_severity": autos.get(key, {}).get("auto_severity")}
        for ev, a in sorted(evals.items()):
            row[f"{ev}_error"] = a["primary_error"]
            row[f"{ev}_severity"] = a["severity"]
            row[f"{ev}_rationale"] = a["rationale"]
        row.update({
            "status": "adjudicated" if adj else "pending",
            "final_error": adj["final_error"] if adj else "",
            "final_severity": adj["final_severity"] if adj else "",
            "adjudicator": adj["adjudicator_id"] if adj else "",
            "adjudicator_rationale": adj["rationale"] if adj else "",
        })
        queue.append(row)
    out = REPORTS / "adjudication_queue.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for r in queue for k in r}, key=lambda k: (not k.startswith(("case", "model", "reasons", "auto")), k))
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(queue)
    return queue


def sign_adjudication(case_id: str, model_id: str, adjudicator_id: str, final_error: str, final_severity: str,
                      rationale: str) -> dict:
    """Record a final decision with an electronic-signature manifest (who, when, meaning) and log it."""
    signed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {"case_id": case_id, "model_id": model_id, "adjudicator_id": adjudicator_id, "final_error": final_error,
               "final_severity": final_severity, "rationale": rationale,
               "signature_meaning": "Reviewed and approved as final evaluation", "signed_at_utc": signed_at}
    payload["signature_hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    record = Adjudication.model_validate(payload).model_dump()
    existing = load_adjudications()
    existing[(case_id, model_id)] = record
    ADJ_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ADJ_PATH.open("w", encoding="utf-8") as fh:
        for r in existing.values():
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    log_event("adjudication_signed", outputs=[ADJ_PATH], actor=adjudicator_id,
              details={"case_id": case_id, "model_id": model_id, "final_error": final_error,
                       "final_severity": final_severity, "signature_hash": record["signature_hash"]})
    return record
