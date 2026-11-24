"""Statistical analytics: bootstrap CIs, consistency (pass^k), calibration (ECE/Brier), drift."""
from __future__ import annotations

import random
from collections import defaultdict


def bootstrap_ci(values: list[float], n_boot: int = 2000, alpha: float = 0.05, seed: int = 7) -> tuple[float, float]:
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(n_boot))
    lo = means[int((alpha / 2) * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot) - 1]
    return (round(lo, 2), round(hi, 2))


def sample_correct(grade: dict) -> bool:
    """A sample is 'correct' when it has no major/critical automated finding."""
    return grade["auto_severity"] in ("none", "minor")


def consistency(auto_grades: list[dict]) -> dict[str, dict]:
    """pass@1 vs pass^k over cases with k>1 samples, plus answer-stability of key outputs."""
    by = defaultdict(lambda: defaultdict(list))
    for g in auto_grades:
        by[g["model_id"]][g["case_id"]].append(g)
    out = {}
    for model, cases in by.items():
        multi = {c: gs for c, gs in cases.items() if len(gs) > 1}
        if not multi:
            out[model] = {"n_cases": 0, "pass_at_1": None, "pass_hat_k": None, "answer_stability": None}
            continue
        p1 = sum(sum(sample_correct(g) for g in gs) / len(gs) for gs in multi.values()) / len(multi)
        pk = sum(all(sample_correct(g) for g in gs) for gs in multi.values()) / len(multi)
        stable = 0
        for gs in multi.values():
            keys = {(g["numeric"].get("passed"), tuple(g["filing"].get("categories", [])), sample_correct(g)) for g in gs}
            stable += len(keys) == 1
        out[model] = {"n_cases": len(multi), "k": max(len(g) for g in multi.values()),
                      "pass_at_1": round(p1, 3), "pass_hat_k": round(pk, 3), "answer_stability": round(stable / len(multi), 3)}
    return out


def calibration(auto_grades: list[dict], bins: int = 5) -> dict[str, dict]:
    by = defaultdict(list)
    for g in auto_grades:
        if g["sample_index"] == 0 and g.get("stated_confidence") is not None:
            by[g["model_id"]].append((g["stated_confidence"], 1.0 if sample_correct(g) else 0.0, g["auto_severity"]))
    out = {}
    for model, rows in by.items():
        n = len(rows)
        ece = 0.0
        table = []
        for b in range(bins):
            lo, hi = b / bins, (b + 1) / bins
            sel = [r for r in rows if (lo <= r[0] < hi) or (b == bins - 1 and r[0] == 1.0)]
            if not sel:
                continue
            conf = sum(r[0] for r in sel) / len(sel)
            acc = sum(r[1] for r in sel) / len(sel)
            ece += len(sel) / n * abs(conf - acc)
            table.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(sel), "mean_confidence": round(conf, 3), "accuracy": round(acc, 3)})
        brier = sum((r[0] - r[1]) ** 2 for r in rows) / n
        over = sum(1 for r in rows if r[0] >= 0.8 and r[2] in ("major", "critical"))
        out[model] = {"n": n, "ece": round(ece, 3), "brier": round(brier, 3),
                      "overconfident_errors": over, "reliability_table": table}
    return out


def drift(current: dict[str, dict], baseline: dict[str, dict], thresholds: dict) -> dict[str, dict]:
    out = {}
    for model, cur in current.items():
        base = baseline.get(model)
        if not base:
            out[model] = {"baseline": None, "alert": False, "note": "no baseline run"}
            continue
        d_pass = round(cur["pass_rate"] - base["pass_rate"], 3)
        d_score = round(cur["mean_final_score"] - base["mean_final_score"], 2)
        alert = (-d_pass >= thresholds["pass_rate"]) or (-d_score >= thresholds["mean_final_score"])
        out[model] = {"baseline_version": base.get("model_version"), "baseline_run": base.get("run_date"),
                      "delta_pass_rate": d_pass, "delta_mean_final_score": d_score, "alert": alert}
    return out
