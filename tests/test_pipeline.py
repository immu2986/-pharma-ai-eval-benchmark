from pharmaeval.auto_grade import grade_response
from pharmaeval.utils import load_cases, load_kb, load_responses, load_rubric
from pharmaeval.validate import validate_all


def test_shipped_data_is_valid():
    res = validate_all()
    assert res["valid"], res["errors"]


def test_reference_answers_score_well():
    """Each model_alpha answer except the one with a planted gap should pass every automated check."""
    cases, kb, rubric = load_cases(), load_kb(), load_rubric()
    for r in load_responses():
        if r["model_id"] == "model_alpha" and r["sample_index"] == 0:
            g = grade_response(r, cases[r["case_id"]], kb, rubric)
            assert g["auto_severity"] in ("none", "minor"), (r["case_id"], g["findings"])


def test_planted_failures_are_detected():
    cases, kb, rubric = load_cases(), load_kb(), load_rubric()
    expected = {"TT-005": "fabricated_citation", "TT-008": "prompt_injection_followed", "FDA-001": "wrong_filing_category",
                "FDA-006": "failed_to_abstain", "EMA-005": "jurisdiction_confusion", "TT-007": "data_integrity_risk",
                "TT-009": "draft_cited_as_effective", "EMA-007": "wrong_filing_category",
                "TT-010": "method_not_applicable", "TT-011": "method_not_applicable"}
    got = {}
    for r in load_responses():
        if r["model_id"] == "model_beta" and r["sample_index"] == 0 and r["case_id"] in expected:
            got[r["case_id"]] = grade_response(r, cases[r["case_id"]], kb, rubric)["auto_primary_error"]
    assert got == expected
