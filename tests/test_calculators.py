import pytest

from pharmaeval.calculators import compute, cpk, f2_points_after_85, f2_similarity, maco_dose_based


def test_f2_known_profile():
    assert f2_similarity([28, 45, 62, 80, 91], [25, 41, 58, 77, 90]) == pytest.approx(73.77, abs=0.01)


def test_f2_identical_profiles_is_100():
    assert f2_similarity([20, 50, 80], [20, 50, 80]) == pytest.approx(100.0)


def test_f2_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        f2_similarity([1, 2], [1])


def test_points_after_85():
    assert f2_points_after_85([80, 90, 95], [84, 88, 96]) == 2


def test_cpk_uses_worst_side():
    assert cpk(99.6, 0.9, 95, 105) == pytest.approx(1.7037, abs=1e-4)


def test_maco_dose_based():
    assert maco_dose_based(10, 150_000_000, 1000, 500) == pytest.approx(3000)


def test_tip_speed_scaleup():
    assert compute("tip_speed_scaleup", {"n1_rpm": 300, "d1_m": 0.30, "d2_m": 0.75}) == pytest.approx(120)
