import json

from pharmaeval import audit
from pharmaeval.schemas import DIMENSIONS
from pharmaeval.scoring import final_item, weighted_human_score
from pharmaeval.utils import load_rubric, risk_tier

RUBRIC = load_rubric()


def test_weighted_score_bounds():
    assert weighted_human_score({d: 5 for d in DIMENSIONS}, RUBRIC) == 100
    assert weighted_human_score({d: 1 for d in DIMENSIONS}, RUBRIC) == 0


def test_weights_sum_to_one():
    assert abs(sum(d["weight"] for d in RUBRIC["dimensions"].values()) - 1) < 1e-9


def test_risk_matrix():
    assert risk_tier({"model_influence": "high", "decision_consequence": "high"}, RUBRIC) == "high"
    assert risk_tier({"model_influence": "low", "decision_consequence": "low"}, RUBRIC) == "low"


def test_auto_critical_cannot_be_outvoted():
    case = {"case_id": "FDA-001", "domain": "regulatory_fda", "task_type": "x", "model_influence": "low", "decision_consequence": "low"}
    auto = {"model_id": "m", "auto_score": 90, "auto_severity": "critical", "auto_primary_error": "wrong_filing_category", "findings": []}
    ann = {"scores": {d: 5 for d in DIMENSIONS}, "primary_error": "none", "severity": "none"}
    item = final_item(case, auto, {"e1": ann, "e2": ann}, None, RUBRIC)
    assert item["final_severity"] == "critical" and not item["passed"]
    assert item["label_source"] == "auto_critical_override"


def test_signed_adjudication_overrides():
    case = {"case_id": "FDA-001", "domain": "regulatory_fda", "task_type": "x", "model_influence": "low", "decision_consequence": "low"}
    auto = {"model_id": "m", "auto_score": 90, "auto_severity": "critical", "auto_primary_error": "fabricated_citation", "findings": []}
    ann = {"scores": {d: 5 for d in DIMENSIONS}, "primary_error": "none", "severity": "none"}
    adj = {"final_error": "none", "final_severity": "none"}
    assert final_item(case, auto, {"e1": ann}, adj, RUBRIC)["passed"]


def test_audit_chain_detects_tampering(tmp_path):
    p = tmp_path / "audit.jsonl"
    audit.log_event("a", path=p, actor="t")
    audit.log_event("b", path=p, actor="t")
    assert audit.verify(p)["valid"]
    lines = p.read_text().splitlines()
    e = json.loads(lines[0])
    e["action"] = "edited"
    lines[0] = json.dumps(e)
    p.write_text("\n".join(lines) + "\n")
    assert not audit.verify(p)["valid"]
