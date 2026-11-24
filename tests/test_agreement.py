import pytest

from pharmaeval.agreement import cohen_kappa, fleiss_kappa, weighted_kappa


def test_perfect_agreement():
    assert cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0


def test_cohen_kappa_known_value():
    a = ["y"] * 20 + ["y"] * 5 + ["n"] * 10 + ["n"] * 15
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert cohen_kappa(a, b) == pytest.approx(0.4, abs=1e-9)


def test_weighted_kappa_penalises_distance():
    near = weighted_kappa([1, 2, 3, 4, 5], [2, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    far = weighted_kappa([1, 2, 3, 4, 5], [5, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    assert near > far


def test_fleiss_perfect():
    assert fleiss_kappa([["a", "a", "a"], ["b", "b", "b"]]) == pytest.approx(1.0)
