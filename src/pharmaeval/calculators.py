"""Reference calculators used to independently verify numbers produced by AI models.

Every function is deterministic and documented with its source formula so the
evaluator never relies on the model under test for the "correct" value.
"""
from __future__ import annotations

import math
from typing import Sequence


def f2_similarity(reference: Sequence[float], test: Sequence[float]) -> float:
    """Dissolution similarity factor f2 (Moore & Flanner; FDA SUPAC-IR / dissolution guidance, EMA BE guideline).

    f2 = 50 * log10( 100 / sqrt(1 + mean((R_t - T_t)^2)) )
    """
    if len(reference) != len(test) or not reference:
        raise ValueError("reference and test profiles must be the same non-zero length")
    msd = sum((r - t) ** 2 for r, t in zip(reference, test)) / len(reference)
    return 50 * math.log10(100 / math.sqrt(1 + msd))


def f2_points_after_85(reference: Sequence[float], test: Sequence[float]) -> int:
    """Number of time points at which BOTH products are above 85% dissolved (regulators expect at most one)."""
    return sum(1 for r, t in zip(reference, test) if r > 85 and t > 85)


def cpk(mean: float, sd: float, lsl: float | None = None, usl: float | None = None) -> float:
    """Process capability index Cpk = min((USL - mean)/3s, (mean - LSL)/3s)."""
    if sd <= 0:
        raise ValueError("sd must be positive")
    parts = []
    if usl is not None:
        parts.append((usl - mean) / (3 * sd))
    if lsl is not None:
        parts.append((mean - lsl) / (3 * sd))
    if not parts:
        raise ValueError("at least one specification limit is required")
    return min(parts)


def maco_dose_based(tdd_previous_mg: float, mbs_next_mg: float, safety_factor: float, tdd_next_mg: float) -> float:
    """Maximum allowable carry-over (mg), dose-based criterion.

    MACO = (TDD_previous * MBS_next) / (SF * TDD_next)
    Note: EMA (2014) and PIC/S expect health-based exposure limits (PDE) to be considered.
    """
    return tdd_previous_mg * mbs_next_mg / (safety_factor * tdd_next_mg)


def maco_pde_based(pde_mg_per_day: float, mbs_next_mg: float, tdd_next_mg: float) -> float:
    """MACO (mg) using a health-based exposure limit: PDE * MBS / TDD_next."""
    return pde_mg_per_day * mbs_next_mg / tdd_next_mg


def impeller_speed_constant_tip_speed(n1_rpm: float, d1_m: float, d2_m: float) -> float:
    """Scale impeller speed keeping tip speed (pi * D * N) constant: N2 = N1 * D1 / D2."""
    return n1_rpm * d1_m / d2_m


def impeller_speed_constant_froude(n1_rpm: float, d1_m: float, d2_m: float) -> float:
    """Scale impeller speed keeping Froude number (N^2 D / g) constant: N2 = N1 * sqrt(D1 / D2)."""
    return n1_rpm * math.sqrt(d1_m / d2_m)


CALCULATORS = {
    "f2": lambda i: f2_similarity(i["reference"], i["test"]),
    "cpk": lambda i: cpk(i["mean"], i["sd"], i.get("lsl"), i.get("usl")),
    "maco_dose": lambda i: maco_dose_based(i["tdd_previous_mg"], i["mbs_next_mg"], i["safety_factor"], i["tdd_next_mg"]),
    "maco_pde": lambda i: maco_pde_based(i["pde_mg_per_day"], i["mbs_next_mg"], i["tdd_next_mg"]),
    "tip_speed_scaleup": lambda i: impeller_speed_constant_tip_speed(i["n1_rpm"], i["d1_m"], i["d2_m"]),
    "froude_scaleup": lambda i: impeller_speed_constant_froude(i["n1_rpm"], i["d1_m"], i["d2_m"]),
}


def compute(kind: str, inputs: dict) -> float:
    if kind not in CALCULATORS:
        raise KeyError(f"unknown calculator: {kind}")
    return CALCULATORS[kind](inputs)


UNIT_FACTORS = {"mg": 1.0, "g": 1000.0, "kg": 1_000_000.0, "rpm": 1.0, "%": 1.0, "": 1.0}


def to_base_unit(value: float, unit: str) -> float:
    return value * UNIT_FACTORS.get(unit.lower(), 1.0)
