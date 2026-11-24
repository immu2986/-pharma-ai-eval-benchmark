from datetime import date

from pharmaeval.guidance import check_guidance, load_registry, status_as_of, watchlist

REG = load_registry()
DOCS = {d["id"]: d for d in REG["documents"]}
NOW = date(2026, 11, 24)


def _errors(findings):
    return {(f["error"], f["severity"]) for f in findings}


def test_status_is_computed_as_of_date():
    assert status_as_of(DOCS["EU-VAR-GL-2013"], date(2025, 12, 1)) == "effective"
    assert status_as_of(DOCS["EU-VAR-GL-2013"], NOW) == "superseded"
    assert status_as_of(DOCS["EU-VAR-GL-2025"], date(2025, 12, 1)) == "pending"
    assert status_as_of(DOCS["EU-VAR-GL-2025"], NOW) == "effective"
    assert status_as_of(DOCS["FDA-QMSR"], date(2025, 6, 1)) == "pending"
    assert status_as_of(DOCS["FDA-PEPTIDE-2021"], date(2026, 7, 1)) == "effective"
    assert status_as_of(DOCS["FDA-PEPTIDE-2021"], NOW) == "withdrawn"
    assert status_as_of(DOCS["ICH-Q1-CONSOLIDATED"], NOW) == "draft"


def test_labelled_draft_with_way_forward_passes():
    text = "The consolidated ICH Q1 is still a draft; gap-assess protocols now and update once it is final."
    cites, f = check_guidance(text, {}, REG, NOW)
    assert not f and cites[0]["presented_as"] == "draft (labelled)"


def test_draft_presented_as_requirement_is_flagged():
    _, f = check_guidance("ICH Q1 (2025) has replaced Q1A(R2); follow ICH Q1 only.", {}, REG, NOW)
    assert ("draft_cited_as_effective", "major") in _errors(f)


def test_draft_without_way_forward_is_minor():
    _, f = check_guidance("The consolidated ICH Q1 is a draft guideline.", {}, REG, NOW)
    assert ("incomplete", "minor") in _errors(f)


def test_withdrawn_cited_as_current_is_flagged():
    _, f = check_guidance("Follow the synthetic peptide guidance (2021) limits.", {}, REG, NOW)
    assert ("outdated_guidance", "major") in _errors(f)


def test_withdrawn_cited_as_historical_is_ok():
    _, f = check_guidance("The 2021 synthetic peptide guidance was withdrawn in July 2026.", {}, REG, NOW)
    assert not f


def test_same_answer_before_withdrawal_is_fine():
    _, f = check_guidance("Follow the synthetic peptide guidance (2021) limits.", {}, REG, date(2026, 1, 1))
    assert not f


def test_superseded_eu_codes_flagged_unless_marked():
    _, f = check_guidance("Classify under B.II.b.1.e as Type IB.", {}, REG, NOW)
    assert ("outdated_guidance", "major") in _errors(f)
    _, f2 = check_guidance("Q.II.b.1.d applies (formerly B.II.b.1).", {}, REG, NOW)
    assert not f2


def test_missing_required_guidance():
    _, f = check_guidance("Impurities must be below 0.5%.", {"required_guidance": ["FDA-PSG-TIRZEPATIDE"]}, REG, NOW)
    assert ("missing_applicable_guidance", "major") in _errors(f)


def test_watchlist_has_way_forward_for_every_entry():
    rows = watchlist(REG, NOW)
    assert rows and all(r["way_forward"] for r in rows)
    assert all(r["status"] != "effective" for r in rows)
