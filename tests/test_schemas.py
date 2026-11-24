import pytest
from pydantic import ValidationError

from pharmaeval.schemas import DIMENSIONS, Annotation, EvaluationCase

GOOD_ANN = {"case_id": "TT-001", "model_id": "m", "evaluator_id": "e1", "scores": {d: 4 for d in DIMENSIONS},
            "primary_error": "none", "severity": "none", "confidence": 4,
            "rationale": "Correct and complete answer for the context of use."}


def test_valid_annotation():
    Annotation.model_validate(GOOD_ANN)


def test_score_out_of_range():
    bad = {**GOOD_ANN, "scores": {**GOOD_ANN["scores"], "relevance": 6}}
    with pytest.raises(ValidationError):
        Annotation.model_validate(bad)


def test_missing_dimension():
    bad = {**GOOD_ANN, "scores": {d: 4 for d in DIMENSIONS[:-1]}}
    with pytest.raises(ValidationError):
        Annotation.model_validate(bad)


def test_rationale_too_short():
    with pytest.raises(ValidationError):
        Annotation.model_validate({**GOOD_ANN, "rationale": "ok"})


def test_label_severity_pairing():
    with pytest.raises(ValidationError):
        Annotation.model_validate({**GOOD_ANN, "primary_error": "factual_error", "severity": "none"})


def test_unknown_error_label():
    with pytest.raises(ValidationError):
        Annotation.model_validate({**GOOD_ANN, "primary_error": "vibes", "severity": "minor"})


CASE = {"case_id": "FDA-010", "domain": "regulatory_fda", "task_type": "x", "dosage_form": "tablet", "jurisdiction": "FDA",
        "context_of_use": "Draft change-control assessment", "model_influence": "high", "decision_consequence": "high",
        "prompt": "Classify this post-approval change please.", "reference_answer": "Prior Approval Supplement",
        "expected_filing": {"jurisdiction": "FDA", "category": "PAS"}, "format_requirements": ["recommended_filing_line"]}


def test_valid_case():
    EvaluationCase.model_validate(CASE)


def test_case_id_must_match_domain():
    with pytest.raises(ValidationError):
        EvaluationCase.model_validate({**CASE, "case_id": "EMA-010"})


def test_expected_filing_requires_line():
    with pytest.raises(ValidationError):
        EvaluationCase.model_validate({**CASE, "format_requirements": []})
