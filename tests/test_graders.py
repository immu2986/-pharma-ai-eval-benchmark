from pharmaeval.graders import check_abstention, check_citations, check_filing, check_numeric
from pharmaeval.utils import load_kb

KB = load_kb()


def _errors(findings):
    return {(f["error"], f["severity"]) for f in findings}


def test_fabricated_ich_guideline_is_critical():
    _, f = check_citations("As required by ICH Q15 and ICH Q12, ...", KB)
    assert ("fabricated_citation", "critical") in _errors(f)
    assert len(f) == 1


def test_real_citations_verify():
    cites, f = check_citations("ICH Q1A(R2), 21 CFR 211.192, 21 CFR 314.70(b), CTD 3.2.P.3.5 and EU GMP Annex 1", KB)
    assert not f and all(c["verified"] for c in cites)


def test_nonexistent_ctd_section():
    _, f = check_citations("Place it in 3.2.P.3.7", KB)
    assert ("fabricated_citation", "major") in _errors(f)


FDA_CASE = {"case_id": "FDA-999", "jurisdiction": "FDA", "format_requirements": ["recommended_filing_line"],
            "expected_filing": {"jurisdiction": "FDA", "category": "PAS"}}
EMA_CASE = {"case_id": "EMA-999", "jurisdiction": "EMA", "format_requirements": ["recommended_filing_line"],
            "expected_filing": {"jurisdiction": "EMA", "category": "IB"}}


def test_correct_filing_passes():
    s, f = check_filing("text\nRecommended filing: PAS", FDA_CASE, KB)
    assert s["passed"] and not f


def test_under_filing_is_critical():
    s, f = check_filing("Recommended filing: CBE-30", FDA_CASE, KB)
    assert not s["passed"] and ("wrong_filing_category", "critical") in _errors(f)


def test_over_filing_is_major():
    s, f = check_filing("Recommended filing: Type II", EMA_CASE, KB)
    assert ("wrong_filing_category", "major") in _errors(f)


def test_type_ia_in_is_not_confused_with_type_ia():
    s, _ = check_filing("Recommended filing: Type IA(IN)", EMA_CASE, KB)
    assert s["categories"] == ["EMA:IAIN"]


def test_jurisdiction_confusion():
    _, f = check_filing("Recommended filing: CBE-30", EMA_CASE, KB)
    assert ("jurisdiction_confusion", "critical") in _errors(f)


def test_missing_filing_line():
    _, f = check_filing("I think a PAS", FDA_CASE, KB)
    assert ("instruction_violation", "major") in _errors(f)


MACO_CASE = {"computation": {"kind": "maco_dose", "label": "MACO", "unit": "mg", "tolerance": 1.0,
                             "inputs": {"tdd_previous_mg": 10, "mbs_next_mg": 150000000, "safety_factor": 1000, "tdd_next_mg": 500}}}


def test_numeric_correct_with_unit_conversion():
    s, f = check_numeric("MACO = 3.0 g", MACO_CASE)
    assert s["passed"] and not f


def test_numeric_unit_slip():
    _, f = check_numeric("MACO = 3 mg", MACO_CASE)
    assert ("unit_error", "major") in _errors(f)


def test_numeric_uses_last_reported_value():
    s, _ = check_numeric("MACO = 10 x ... so MACO = 3000 mg", MACO_CASE)
    assert s["passed"]


def test_failed_to_abstain():
    _, f = check_abstention("Section III.A requires a transfer master plan.", {"expect_abstention": True}, KB)
    assert ("failed_to_abstain", "critical") in _errors(f)


def test_correct_abstention():
    s, f = check_abstention("I cannot verify that this guidance exists.", {"expect_abstention": True}, KB)
    assert s["passed"] and not f
