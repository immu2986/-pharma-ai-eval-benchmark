"""Final scoring, risk-tiered pass/fail, model summaries and the release (fitness-for-use) gate."""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import date

from .adjudication import load_adjudications, majority
from .agreement import group_by_item
from .analytics import bootstrap_ci, calibration, consistency, drift
from .schemas import DIMENSIONS
from .utils import (DATA, REPORTS, SEVERITY_RANK, load_annotations, load_cases, load_json, load_jsonl, load_rubric,
                    risk_tier, write_json, write_jsonl)


def weighted_human_score(scores: dict[str, int], rubric: dict) -> float:
    """Map 1-5 dimension scores to a 0-100 weighted score."""
    dims = rubric["dimensions"]
    total_w = sum(d["weight"] for d in dims.values())
    return 100 * sum(dims[d]["weight"] * (scores[d] - 1) / 4 for d in DIMENSIONS) / total_w


def final_item(case: dict, auto: dict, evals: dict[str, dict], adj: dict | None, rubric: dict) -> dict:
    anns = list(evals.values())
    human = sum(weighted_human_score(a["scores"], rubric) for a in anns) / len(anns) if anns else None
    if adj:
        label, sev, source = adj["final_error"], adj["final_severity"], "adjudication"
    elif anns:
        sev = majority([a["severity"] for a in anns], SEVERITY_RANK)
        label = majority([a["primary_error"] for a in anns if a["severity"] == sev] or [a["primary_error"] for a in anns])
        source = "majority_vote"
        # Deterministic critical findings can only be overruled by a signed adjudication
        if auto["auto_severity"] == "critical" and sev != "critical":
            label, sev, source = auto["auto_primary_error"], "critical", "auto_critical_override"
    else:
        label, sev, source = auto["auto_primary_error"], auto["auto_severity"], "automated_only"

    blend = rubric["score_blend"]
    final = auto["auto_score"] if human is None else blend["human_weight"] * human + blend["automated_weight"] * auto["auto_score"]
    tier = risk_tier(case, rubric)
    th = rubric["pass_thresholds"][tier]
    passed = final >= th["min_final_score"] and SEVERITY_RANK[sev] <= SEVERITY_RANK[th["max_allowed_severity"]]
    return {
        "case_id": case["case_id"], "model_id": auto["model_id"], "model_version": auto.get("model_version"),
        "domain": case["domain"], "task_type": case["task_type"], "risk_tier": tier,
        "human_score": None if human is None else round(human, 1), "auto_score": auto["auto_score"],
        "final_score": round(final, 1), "final_error": label, "final_severity": sev, "label_source": source,
        "threshold": th["min_final_score"], "passed": passed,
        "stated_confidence": auto.get("stated_confidence"),
        "findings": [f["detail"] for f in auto["findings"]],
    }


def release_decision(s: dict, gate: dict) -> tuple[str, list[str]]:
    reasons = []
    fit = gate["fit"]
    cons = s["consistency"]["pass_hat_k"]
    ece = s["calibration"]["ece"]
    checks = [
        (s["pass_rate"] >= fit["min_pass_rate"], f"pass rate {s['pass_rate']:.0%} vs >= {fit['min_pass_rate']:.0%}"),
        (s["critical_findings"] <= fit["max_critical_findings"], f"critical findings {s['critical_findings']} vs <= {fit['max_critical_findings']}"),
        (cons is None or cons >= fit["min_consistency"], f"consistency pass^k {cons} vs >= {fit['min_consistency']}"),
        (ece is None or ece <= fit["max_ece"], f"calibration ECE {ece} vs <= {fit['max_ece']}"),
        (s["guidance_status_errors"] <= fit.get("max_guidance_status_errors", 0),
         f"guidance-status errors {s['guidance_status_errors']} vs <= {fit.get('max_guidance_status_errors', 0)} (drafts as requirements, withdrawn/superseded cited as current, applicable guidance missing)"),
    ]
    for ok, msg in checks:
        reasons.append(("PASS " if ok else "FAIL ") + msg)
    if all(ok for ok, _ in checks):
        decision = "FIT FOR INTENDED USE (with human-in-the-loop review)"
    elif s["pass_rate"] >= gate["conditional"]["min_pass_rate"] and s["critical_findings"] <= gate["conditional"]["max_critical_findings"]:
        decision = "CONDITIONALLY FIT (restricted context of use + 100% SME review)"
    else:
        decision = "NOT FIT FOR INTENDED USE"
    if s["pending_adjudications"]:
        reasons.append(f"NOTE {s['pending_adjudications']} item(s) pending adjudication: decision is provisional")
    if s["drift"].get("alert"):
        reasons.append("NOTE performance drift alert versus baseline")
    return decision, reasons


def run() -> dict:
    rubric, cases = load_rubric(), load_cases()
    autos = load_jsonl(REPORTS / "auto_grades.jsonl")
    auto0 = {(g["case_id"], g["model_id"]): g for g in autos if g["sample_index"] == 0}
    items = group_by_item(load_annotations())
    adjs = load_adjudications()

    finals = [final_item(cases[cid], g, items.get((cid, mid), {}), adjs.get((cid, mid)), rubric)
              for (cid, mid), g in sorted(auto0.items())]
    write_jsonl(REPORTS / "final_scores.jsonl", finals)

    # pending adjudications = items in queue without decision
    queue_path = REPORTS / "adjudication_queue.csv"
    pending = Counter()
    if queue_path.exists():
        with queue_path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["status"] == "pending":
                    pending[row["model_id"]] += 1

    cons, cal = consistency(autos), calibration(autos)
    by_model = defaultdict(list)
    for f in finals:
        by_model[f["model_id"]].append(f)

    summaries = {}
    for model, rows in sorted(by_model.items()):
        scores = [r["final_score"] for r in rows]
        dom = defaultdict(list)
        tier = defaultdict(list)
        for r in rows:
            dom[r["domain"]].append(r)
            tier[r["risk_tier"]].append(r)
        summaries[model] = {
            "model_version": rows[0]["model_version"], "n_items": len(rows),
            "pass_rate": round(sum(r["passed"] for r in rows) / len(rows), 3),
            "mean_final_score": round(sum(scores) / len(scores), 1),
            "mean_final_score_ci95": bootstrap_ci(scores),
            "mean_human_score": round(sum(r["human_score"] or 0 for r in rows) / len(rows), 1),
            "mean_auto_score": round(sum(r["auto_score"] for r in rows) / len(rows), 1),
            "critical_findings": sum(r["final_severity"] == "critical" for r in rows),
            "major_findings": sum(r["final_severity"] == "major" for r in rows),
            "by_domain": {d: {"n": len(v), "pass_rate": round(sum(x["passed"] for x in v) / len(v), 3),
                              "mean_final_score": round(sum(x["final_score"] for x in v) / len(v), 1)} for d, v in sorted(dom.items())},
            "by_risk_tier": {t: {"n": len(v), "pass_rate": round(sum(x["passed"] for x in v) / len(v), 3)} for t, v in sorted(tier.items())},
            "error_distribution": dict(Counter(r["final_error"] for r in rows).most_common()),
            "severity_distribution": {s: sum(r["final_severity"] == s for r in rows) for s in SEVERITY_RANK},
            "consistency": cons.get(model, {"pass_hat_k": None}),
            "calibration": cal.get(model, {"ece": None}),
            "pending_adjudications": pending.get(model, 0),
            "guidance_status_errors": sum(1 for g in auto0.values() if g["model_id"] == model
                                          for f in g["findings"] if f.get("check") == "guidance_status" and f["error"] != "incomplete"),
            "drafts_labelled_correctly": sum(1 for g in auto0.values() if g["model_id"] == model
                                             for c in g.get("guidance_citations", []) if c["presented_as"] and "labelled" in c["presented_as"]),
        }

    baseline_path = DATA / "baselines" / "previous_run_summary.json"
    baseline = load_json(baseline_path) if baseline_path.exists() else {}
    dr = drift(summaries, baseline, rubric["release_gate"]["drift_alert_drop"])
    for model, s in summaries.items():
        s["drift"] = dr.get(model, {})
        s["release_decision"], s["release_reasons"] = release_decision(s, rubric["release_gate"])

    from .guidance import evaluation_as_of, load_registry, watchlist
    as_of = evaluation_as_of()
    wl = watchlist(load_registry(), as_of)
    write_json(REPORTS / "guidance_watchlist.json", {"evaluation_as_of": as_of.isoformat(), "documents": wl})
    result = {"run_date": date.today().isoformat(), "evaluation_as_of": as_of.isoformat(),
              "rubric_version": rubric["rubric_version"], "models": summaries}
    write_json(REPORTS / "model_summary.json", result)
    with (REPORTS / "quality_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["model_id", "version", "n", "pass_rate", "mean_final", "ci95_low", "ci95_high", "critical", "major",
                    "pass_hat_k", "ece", "decision"])
        for m, s in summaries.items():
            w.writerow([m, s["model_version"], s["n_items"], s["pass_rate"], s["mean_final_score"], *s["mean_final_score_ci95"],
                        s["critical_findings"], s["major_findings"], s["consistency"].get("pass_hat_k"),
                        s["calibration"].get("ece"), s["release_decision"]])
    return result


if __name__ == "__main__":
    r = run()
    for m, s in r["models"].items():
        print(m, s["pass_rate"], s["mean_final_score"], s["release_decision"])
