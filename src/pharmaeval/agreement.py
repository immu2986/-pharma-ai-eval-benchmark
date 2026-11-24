"""Inter-rater agreement: percent agreement, Cohen's kappa, quadratic-weighted kappa, Fleiss' kappa."""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from .schemas import DIMENSIONS
from .utils import REPORTS, load_annotations, write_json

SEV_ORDER = ["none", "minor", "major", "critical"]


def cohen_kappa(a: list, b: list) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def weighted_kappa(a: list, b: list, categories: list) -> float:
    """Quadratic-weighted Cohen's kappa for ordinal ratings."""
    k, n = len(categories), len(a)
    if n == 0:
        return float("nan")
    idx = {c: i for i, c in enumerate(categories)}
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1
    ra = [sum(row) for row in obs]
    rb = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w = [[((i - j) ** 2) / ((k - 1) ** 2) for j in range(k)] for i in range(k)]
    num = sum(w[i][j] * obs[i][j] for i in range(k) for j in range(k))
    den = sum(w[i][j] * ra[i] * rb[j] / n for i in range(k) for j in range(k))
    return 1.0 if den == 0 else 1 - num / den


def fleiss_kappa(ratings: list[list]) -> float:
    """ratings: one list of category labels per item (same number of raters per item)."""
    items = [r for r in ratings if r]
    if not items:
        return float("nan")
    m = len(items[0])
    cats = sorted({c for r in items for c in r})
    N = len(items)
    p_j = {c: sum(r.count(c) for r in items) / (N * m) for c in cats}
    P_i = [(sum(r.count(c) ** 2 for c in cats) - m) / (m * (m - 1)) for r in items]
    P_bar = sum(P_i) / N
    P_e = sum(v * v for v in p_j.values())
    return 1.0 if P_e == 1 else (P_bar - P_e) / (1 - P_e)


def interpret_kappa(k: float) -> str:
    if k != k:  # NaN
        return "n/a"
    for cut, label in ((0.8, "almost perfect"), (0.6, "substantial"), (0.4, "moderate"), (0.2, "fair"), (0.0, "slight")):
        if k > cut:
            return label
    return "poor"


def group_by_item(annotations: list[dict]) -> dict[tuple, dict[str, dict]]:
    items: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for a in annotations:
        items[(a["case_id"], a["model_id"])][a["evaluator_id"]] = a
    return items


def run() -> dict:
    anns = load_annotations()
    items = group_by_item(anns)
    evaluators = sorted({a["evaluator_id"] for a in anns})
    pairs = []
    for e1, e2 in combinations(evaluators, 2):
        common = [k for k, v in items.items() if e1 in v and e2 in v]
        la = [items[k][e1]["primary_error"] for k in common]
        lb = [items[k][e2]["primary_error"] for k in common]
        sa = [items[k][e1]["severity"] for k in common]
        sb = [items[k][e2]["severity"] for k in common]
        dims = {}
        for d in DIMENSIONS:
            da = [items[k][e1]["scores"][d] for k in common]
            db = [items[k][e2]["scores"][d] for k in common]
            dims[d] = {"qw_kappa": round(weighted_kappa(da, db, [1, 2, 3, 4, 5]), 3),
                       "mean_abs_diff": round(sum(abs(x - y) for x, y in zip(da, db)) / len(common), 3)}
        kl = cohen_kappa(la, lb)
        ks = weighted_kappa(sa, sb, SEV_ORDER)
        pairs.append({
            "pair": f"{e1} vs {e2}", "n_items": len(common),
            "error_label_agreement": round(sum(x == y for x, y in zip(la, lb)) / len(common), 3),
            "error_label_kappa": round(kl, 3), "error_label_kappa_interpretation": interpret_kappa(kl),
            "severity_agreement": round(sum(x == y for x, y in zip(sa, sb)) / len(common), 3),
            "severity_qw_kappa": round(ks, 3), "severity_kappa_interpretation": interpret_kappa(ks),
            "dimensions": dims,
        })
    full = [v for v in items.values() if len(v) == len(evaluators)]
    fk_label = fleiss_kappa([[v[e]["primary_error"] for e in evaluators] for v in full])
    fk_sev = fleiss_kappa([[v[e]["severity"] for e in evaluators] for v in full])
    summary = {
        "evaluators": evaluators, "n_items": len(items), "pairwise": pairs,
        "fleiss_kappa_error_label": round(fk_label, 3), "fleiss_error_label_interpretation": interpret_kappa(fk_label),
        "fleiss_kappa_severity": round(fk_sev, 3), "fleiss_severity_interpretation": interpret_kappa(fk_sev),
    }
    write_json(REPORTS / "agreement_summary.json", summary)
    return summary


if __name__ == "__main__":
    s = run()
    print(f"Fleiss kappa (labels) = {s['fleiss_kappa_error_label']}  (severity) = {s['fleiss_kappa_severity']}")
