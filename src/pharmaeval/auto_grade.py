"""Automated, deterministic grading of every model response.

Output: reports/auto_grades.jsonl  (one record per case x model x sample)
"""
from __future__ import annotations

from .graders import (check_abstention, check_citations, check_filing, check_forbidden, check_numeric,
                      check_required_points, context_support_rate)
from .guidance import check_guidance, evaluation_as_of, load_registry
from .utils import REPORTS, SEVERITY_RANK, load_cases, load_kb, load_responses, load_rubric, max_severity, risk_tier, write_jsonl


def grade_response(resp: dict, case: dict, kb: dict, rubric: dict, registry: dict | None = None, as_of=None) -> dict:
    text = resp["response"]
    findings: list[dict] = []

    points, f = check_required_points(text, case)
    findings += f
    findings += check_forbidden(text, case)
    citations, f = check_citations(text, kb)
    findings += f
    numeric, f = check_numeric(text, case)
    findings += f
    filing, f = check_filing(text, case, kb)
    findings += f
    abstention, f = check_abstention(text, case, kb)
    findings += f
    registry = registry or load_registry()
    as_of = as_of or evaluation_as_of()
    guidance_cites, f = check_guidance(text, case, registry, as_of)
    findings += f

    items = [p["covered"] for p in points]
    if numeric.get("scored"):
        items.append(bool(numeric["passed"]))
    if filing.get("scored"):
        items.append(bool(filing["passed"]))
    if abstention.get("scored"):
        items.append(bool(abstention["passed"]))
    coverage = sum(items) / len(items) if items else 1.0

    penalties = rubric["severity_levels"]
    # 'incomplete' is already reflected in coverage, so it is not penalised twice
    penalty = sum(penalties[x["severity"]]["auto_penalty"] for x in findings if x["error"] != "incomplete")
    auto_score = max(0.0, min(100.0, 100.0 * coverage - penalty))
    severity = max_severity(x["severity"] for x in findings)
    primary = "none"
    if findings:
        # highest severity wins; on ties a specific error beats generic 'incomplete'
        primary = max(findings, key=lambda x: (SEVERITY_RANK[x["severity"]], x["error"] != "incomplete"))["error"]

    return {
        "case_id": case["case_id"], "model_id": resp["model_id"], "model_version": resp.get("model_version"),
        "sample_index": resp.get("sample_index", 0), "domain": case["domain"], "risk_tier": risk_tier(case, rubric),
        "stated_confidence": resp.get("stated_confidence"),
        "coverage": round(coverage, 3), "auto_score": round(auto_score, 1),
        "auto_primary_error": primary, "auto_severity": severity,
        "required_points": points, "numeric": numeric, "filing": filing, "abstention": abstention,
        "citations": citations,
        "guidance_citations": guidance_cites,
        "evaluation_as_of": as_of.isoformat(),
        "citations_verified_rate": (round(sum(c["verified"] for c in citations) / len(citations), 3) if citations else None),
        "context_support_rate": context_support_rate(text, case.get("context", [])),
        "findings": findings,
    }


def run(out_path=None) -> list[dict]:
    cases, kb, rubric = load_cases(), load_kb(), load_rubric()
    registry, as_of = load_registry(), evaluation_as_of()
    results = []
    for resp in load_responses():
        case = cases.get(resp["case_id"])
        if case is None:
            raise KeyError(f"response references unknown case {resp['case_id']}")
        results.append(grade_response(resp, case, kb, rubric, registry, as_of))
    write_jsonl(out_path or REPORTS / "auto_grades.jsonl", results)
    return results


if __name__ == "__main__":
    res = run()
    print(f"auto-graded {len(res)} responses -> reports/auto_grades.jsonl")
