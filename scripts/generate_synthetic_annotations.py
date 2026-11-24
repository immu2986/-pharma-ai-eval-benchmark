"""Generate SYNTHETIC human-evaluator annotations for the demo dataset.

Three simulated evaluators with distinct, documented behaviours:
  evaluator_1  senior MSAT reviewer      - closely tracks objective findings
  evaluator_2  regulatory affairs lead   - stricter on regulatory judgement, labels the most specific error
  evaluator_3  junior reviewer           - more lenient on severity (creates realistic disagreements)

Real projects replace these files with annotations captured from qualified SMEs.
Run after auto-grading:  python scripts/generate_synthetic_annotations.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pharmaeval.schemas import DIMENSIONS  # noqa: E402
from pharmaeval.utils import SEVERITY_RANK, load_jsonl, write_jsonl  # noqa: E402

# Plausible confusions between neighbouring taxonomy labels (drives realistic label disagreement)
CONFUSION = {
    "fabricated_citation": "hallucination", "failed_to_abstain": "hallucination",
    "wrong_filing_category": "factual_error", "unsafe_recommendation": "factual_error",
    "misquoted_regulation": "fabricated_citation", "incomplete": "missing_critical_step",
    "calculation_error": "factual_error", "unit_error": "calculation_error",
    "method_not_applicable": "factual_error",
}
LOWER = {"critical": "major", "major": "minor", "minor": "none", "none": "none"}


def base_score(auto_score: float) -> int:
    for cut, s in ((90, 5), (75, 4), (50, 3), (25, 2)):
        if auto_score >= cut:
            return s
    return 1


def dimension_scores(g: dict, rng: random.Random, jitter: float) -> dict[str, int]:
    b = base_score(g["auto_score"])
    errs = {f["error"] for f in g["findings"]}
    sev = g["auto_severity"]
    s = {d: b for d in DIMENSIONS}
    if errs & {"fabricated_citation", "misquoted_regulation", "unsupported_claim", "failed_to_abstain"}:
        s["grounding_and_citations"] = min(s["grounding_and_citations"], 1 if sev == "critical" else 2)
    if errs & {"factual_error", "calculation_error", "unit_error", "outdated_guidance", "wrong_filing_category"}:
        s["scientific_regulatory_accuracy"] = min(s["scientific_regulatory_accuracy"], 2)
    if sev == "critical":
        s["regulatory_risk_judgement"] = 1
    if errs & {"instruction_violation", "format_violation"}:
        s["instruction_following"] = min(s["instruction_following"], 2)
    if b >= 4:
        s["relevance"] = 5
    for d in DIMENSIONS:
        if rng.random() < jitter:
            s[d] = max(1, min(5, s[d] + rng.choice((-1, 1))))
    return s


def rationale(g: dict, label: str, sev: str) -> str:
    if label == "none":
        return "Answer is correct, grounded in the cited sources and complete for the stated context of use."
    details = "; ".join(f["detail"] for f in g["findings"][:2])
    return f"Primary issue {label} ({sev}). {details}"[:1400]


def main() -> None:
    grades = [g for g in load_jsonl(ROOT / "reports" / "auto_grades.jsonl") if g["sample_index"] == 0]
    profiles = {
        "evaluator_1": {"jitter": 0.08, "lenient": 0.0, "specific": False, "confuse": 0.0},
        "evaluator_2": {"jitter": 0.10, "lenient": 0.0, "specific": True, "confuse": 0.30},
        "evaluator_3": {"jitter": 0.18, "lenient": 0.30, "specific": False, "confuse": 0.20},
    }
    for ev, prof in profiles.items():
        rows = []
        for g in grades:
            rng = random.Random(f"{ev}|{g['case_id']}|{g['model_id']}")
            label, sev = g["auto_primary_error"], g["auto_severity"]
            if prof["specific"] and label == "incomplete":
                specific = [f for f in g["findings"] if f["error"] != "incomplete"]
                if specific:
                    best = max(specific, key=lambda f: SEVERITY_RANK[f["severity"]])
                    label, sev = best["error"], best["severity"]
            if label in CONFUSION and rng.random() < prof["confuse"]:
                label = CONFUSION[label]
            if prof["lenient"] and sev != "none" and rng.random() < prof["lenient"]:
                sev = LOWER[sev]
                if sev == "none":
                    label = "none"
            rows.append({
                "case_id": g["case_id"], "model_id": g["model_id"], "evaluator_id": ev,
                "scores": dimension_scores(g, rng, prof["jitter"]),
                "primary_error": label, "severity": sev,
                "confidence": 5 if sev in ("none", "critical") else 4,
                "rationale": rationale(g, label, sev),
            })
        write_jsonl(ROOT / "data" / "annotations" / f"{ev}.jsonl", rows)
    print("wrote synthetic annotations for", ", ".join(profiles))


if __name__ == "__main__":
    main()
