from pharmaeval.graders import check_f2_applicability
from pharmaeval.graders.applicability import classify

MAB = {"dosage_form": "monoclonal antibody solution for injection (vial)"}
GLP1 = {"dosage_form": "peptide solution in autoinjector / pen"}
SUSP = {"dosage_form": "medroxyprogesterone acetate injectable suspension (IM)"}
MICRO = {"dosage_form": "PLGA microspheres for extended-release injectable suspension"}
TABLET = {"dosage_form": "immediate-release tablet"}


def _errors(findings):
    return {(f["error"], f["severity"]) for f in findings}


def test_classification_by_dosage_form():
    assert classify(MAB) == "not_applicable"
    assert classify(GLP1) == "not_applicable"
    assert classify(SUSP) == "conditional"
    assert classify(MICRO) == "conditional"
    assert classify(TABLET) is None
    assert classify({"dosage_form": "solution", "release_comparison": "conditional"}) == "conditional"


def test_f2_on_solution_is_major():
    _, f = check_f2_applicability("Calculate f2 between the two sites; f2 above 50 shows equivalence.", MAB)
    assert ("method_not_applicable", "major") in _errors(f)


def test_f2_on_peptide_solution_is_major():
    _, f = check_f2_applicability("Use the similarity factor to compare the pens.", GLP1)
    assert ("method_not_applicable", "major") in _errors(f)


def test_rejecting_f2_for_solution_passes():
    s, f = check_f2_applicability("f2 is not applicable because the drug is in solution. Use ICH Q5E comparability.", MAB)
    assert not f and not s["f2_used"]


def test_f2_on_suspension_without_caveats_is_minor():
    _, f = check_f2_applicability("Calculate f2 on the release profiles; above 50 means equivalent.", SUSP)
    assert ("method_not_applicable", "minor") in _errors(f)


def test_f2_on_suspension_with_caveats_passes():
    text = ("f2 can be used if no more than one point exceeds 85% and the CV is low; otherwise use a bootstrap f2 "
            "as the product-specific guidance requires.")
    _, f = check_f2_applicability(text, SUSP)
    assert not f


def test_oral_solid_is_not_checked():
    s, f = check_f2_applicability("f2 = 73.8", TABLET)
    assert not f and s["release_comparison"] is None
