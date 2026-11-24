"""Pydantic schemas for every record that enters the evaluation pipeline."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Domain = Literal["tech_transfer", "regulatory_fda", "regulatory_ema"]
Level = Literal["low", "medium", "high"]
Severity = Literal["none", "minor", "major", "critical"]

ERROR_LABELS = (
    "none",
    # accuracy
    "factual_error", "calculation_error", "unit_error", "outdated_guidance",
    # grounding / hallucination
    "fabricated_citation", "misquoted_regulation", "unsupported_claim", "hallucination", "failed_to_abstain",
    # guidance status (effective vs draft vs withdrawn)
    "draft_cited_as_effective", "missing_applicable_guidance",
    # regulatory judgement
    "wrong_filing_category", "jurisdiction_confusion", "unsafe_recommendation", "data_integrity_risk",
    "prompt_injection_followed",
    # completeness / relevance / format
    "incomplete", "missing_critical_step", "irrelevant", "inappropriate_abstention",
    "instruction_violation", "format_violation",
)
ErrorLabel = Literal[ERROR_LABELS]  # type: ignore[valid-type]

DIMENSIONS = (
    "scientific_regulatory_accuracy", "grounding_and_citations", "completeness",
    "regulatory_risk_judgement", "relevance", "instruction_following", "actionability",
)


class RequiredPoint(BaseModel):
    id: str
    description: str
    any_of: list[str] = Field(min_length=1)


class ForbiddenClaim(BaseModel):
    id: str
    description: str
    pattern: str
    error: ErrorLabel
    severity: Severity


class Computation(BaseModel):
    kind: str
    inputs: dict
    label: str
    unit: str = ""
    tolerance: float = Field(gt=0)


class ExpectedFiling(BaseModel):
    jurisdiction: Literal["FDA", "EMA"]
    category: str


class EvaluationCase(BaseModel):
    case_id: str = Field(pattern=r"^(TT|FDA|EMA)-\d{3}$")
    domain: Domain
    task_type: str
    dosage_form: str
    jurisdiction: Literal["FDA", "EMA", "FDA+EMA"]
    context_of_use: str = Field(min_length=10)
    model_influence: Level
    decision_consequence: Level
    prompt: str = Field(min_length=20)
    reference_answer: str = Field(min_length=5)
    context: list[str] = Field(default_factory=list)
    required_points: list[RequiredPoint] = Field(default_factory=list)
    forbidden_claims: list[ForbiddenClaim] = Field(default_factory=list)
    computation: Optional[Computation] = None
    expected_filing: Optional[ExpectedFiling] = None
    expect_abstention: bool = False
    adversarial: bool = False
    format_requirements: list[Literal["recommended_filing_line"]] = Field(default_factory=list)
    required_guidance: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistency(self):
        prefix = {"tech_transfer": "TT", "regulatory_fda": "FDA", "regulatory_ema": "EMA"}[self.domain]
        if not self.case_id.startswith(prefix):
            raise ValueError(f"case_id {self.case_id} does not match domain {self.domain}")
        if self.expected_filing and "recommended_filing_line" not in self.format_requirements:
            raise ValueError("cases with expected_filing must require a 'Recommended filing:' line")
        if not self.expect_abstention and not (self.required_points or self.computation or self.expected_filing):
            raise ValueError("non-abstention cases need at least one objective check")
        return self


class ModelResponse(BaseModel):
    case_id: str
    model_id: str = Field(min_length=1)
    model_version: str = "unspecified"
    sample_index: int = Field(ge=0, default=0)
    response: str = Field(min_length=1)
    stated_confidence: Optional[float] = Field(default=None, ge=0, le=1)


class Annotation(BaseModel):
    case_id: str
    model_id: str
    evaluator_id: str = Field(min_length=1)
    scores: dict[str, int]
    primary_error: ErrorLabel
    severity: Severity
    confidence: int = Field(ge=1, le=5)
    rationale: str = Field(min_length=25, max_length=1500)

    @field_validator("scores")
    @classmethod
    def _scores(cls, v: dict[str, int]):
        missing = set(DIMENSIONS) - set(v)
        extra = set(v) - set(DIMENSIONS)
        if missing or extra:
            raise ValueError(f"scores must cover exactly {DIMENSIONS}; missing={sorted(missing)} extra={sorted(extra)}")
        for k, s in v.items():
            if not 1 <= s <= 5:
                raise ValueError(f"score {k}={s} outside 1-5")
        return v

    @model_validator(mode="after")
    def _label_severity(self):
        if (self.primary_error == "none") != (self.severity == "none"):
            raise ValueError("primary_error 'none' must be paired with severity 'none' and vice versa")
        return self


class Adjudication(BaseModel):
    case_id: str
    model_id: str
    adjudicator_id: str
    final_error: ErrorLabel
    final_severity: Severity
    rationale: str = Field(min_length=25)
    signature_meaning: Literal["Reviewed and approved as final evaluation"] = "Reviewed and approved as final evaluation"
    signed_at_utc: str
    signature_hash: str
