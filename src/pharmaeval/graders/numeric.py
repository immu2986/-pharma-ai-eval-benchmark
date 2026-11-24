"""Independent recomputation of numeric answers (f2, Cpk, MACO, scale-up speeds)."""
from __future__ import annotations

import re

from ..calculators import UNIT_FACTORS, compute

NUM = r"([-+]?\d[\d,]*(?:\.\d+)?)"


def extract_value(text: str, label: str) -> tuple[float, str] | None:
    pattern = re.compile(rf"\b{re.escape(label)}\s*(?:=|≈|:|is)\s*{NUM}\s*(mg|g|kg|rpm|%)?(?![\w·])", re.I)
    matches = pattern.findall(text)
    if not matches:
        return None
    value, unit = matches[-1]
    return float(value.replace(",", "")), (unit or "").lower()


def check_numeric(text: str, case: dict) -> tuple[dict, list[dict]]:
    comp = case.get("computation")
    if not comp:
        return {"scored": False}, []
    expected = compute(comp["kind"], comp["inputs"])
    summary = {"scored": True, "expected": round(expected, 4), "label": comp["label"], "unit": comp.get("unit", ""),
               "reported": None, "passed": False}
    got = extract_value(text, comp["label"])
    if got is None:
        return summary, [{"check": "numeric", "passed": False, "error": "instruction_violation", "severity": "major",
                          "detail": f"No value reported as '{comp['label']} = <value>'"}]
    value, unit = got
    want_unit = comp.get("unit", "")
    unit = unit or want_unit
    summary["reported"] = f"{value:g} {unit}".strip()
    base_val = value * UNIT_FACTORS.get(unit, 1.0)
    base_exp = expected * UNIT_FACTORS.get(want_unit, 1.0)
    tol = comp["tolerance"] * UNIT_FACTORS.get(want_unit, 1.0)
    if abs(base_val - base_exp) <= tol:
        summary["passed"] = True
        return summary, []
    for factor in (1000.0, 0.001, 1_000_000.0, 0.000001):
        if abs(base_val * factor - base_exp) <= tol:
            return summary, [{"check": "numeric", "passed": False, "error": "unit_error", "severity": "major",
                              "detail": f"{comp['label']} reported as {value:g} {unit}; expected {expected:.4g} {want_unit} (unit/magnitude slip)"}]
    rel = abs(base_val - base_exp) / max(abs(base_exp), 1e-9)
    return summary, [{"check": "numeric", "passed": False, "error": "calculation_error", "severity": "major",
                      "detail": f"{comp['label']} reported as {value:g}; independent recomputation gives {expected:.4g} ({rel:.0%} off)"}]
