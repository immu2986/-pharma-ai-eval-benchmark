"""Command-line interface:  python -m pharmaeval <command>"""
from __future__ import annotations

import argparse
import json
import sys

from . import adjudication, agreement, audit, auto_grade, report, scoring, validate
from .utils import DATA, REPORTS, RUBRIC_PATH, KB_PATH


def _inputs():
    return [DATA / "cases.jsonl", RUBRIC_PATH, KB_PATH, *sorted((DATA / "responses").glob("*.jsonl")),
            *sorted((DATA / "annotations").glob("*.jsonl"))]


def cmd_validate(_):
    res = validate.validate_all()
    audit.log_event("validate", inputs=_inputs(), details={"valid": res["valid"], "errors": len(res["errors"])})
    print(json.dumps(res, indent=2))
    return 0 if res["valid"] else 1


def cmd_autograde(_):
    res = auto_grade.run()
    audit.log_event("auto_grade", inputs=_inputs(), outputs=[REPORTS / "auto_grades.jsonl"], details={"graded": len(res)})
    print(f"[auto-grade] {len(res)} responses graded -> reports/auto_grades.jsonl")
    return 0


def cmd_agreement(_):
    s = agreement.run()
    audit.log_event("agreement", inputs=_inputs(), outputs=[REPORTS / "agreement_summary.json"],
                    details={"fleiss_label": s["fleiss_kappa_error_label"], "fleiss_severity": s["fleiss_kappa_severity"]})
    print(f"[agreement] Fleiss kappa label={s['fleiss_kappa_error_label']} severity={s['fleiss_kappa_severity']}")
    return 0


def cmd_queue(_):
    q = adjudication.build_queue()
    audit.log_event("adjudication_queue", outputs=[REPORTS / "adjudication_queue.csv"],
                    details={"flagged": len(q), "pending": sum(r["status"] == "pending" for r in q)})
    print(f"[adjudication] {len(q)} flagged -> reports/adjudication_queue.csv")
    return 0


def cmd_adjudicate(a):
    rec = adjudication.sign_adjudication(a.case_id, a.model_id, a.adjudicator, a.error, a.severity, a.rationale)
    print(f"[adjudication] signed {rec['case_id']}/{rec['model_id']} -> {rec['final_error']}/{rec['final_severity']} "
          f"signature {rec['signature_hash'][:12]}…")
    return 0


def cmd_score(_):
    r = scoring.run()
    audit.log_event("score_and_release_gate", inputs=[REPORTS / "auto_grades.jsonl", *_inputs()],
                    outputs=[REPORTS / "final_scores.jsonl", REPORTS / "model_summary.json", REPORTS / "quality_summary.csv"],
                    details={m: s["release_decision"] for m, s in r["models"].items()})
    for m, s in r["models"].items():
        print(f"[score] {m}: pass {s['pass_rate']:.0%}, mean {s['mean_final_score']} -> {s['release_decision']}")
    return 0


def cmd_report(_):
    report.run()
    audit.log_event("report", inputs=[REPORTS / "model_summary.json"],
                    outputs=[REPORTS / "evaluation_report.md", REPORTS / "dashboard.html"])
    print("[report] reports/evaluation_report.md, reports/dashboard.html")
    return 0


def cmd_watchlist(_):
    from .guidance import evaluation_as_of, load_registry, watchlist
    as_of = evaluation_as_of()
    rows = watchlist(load_registry(), as_of)
    print(f"Guidance watchlist as of {as_of} ({len(rows)} non-effective documents)")
    for r in rows:
        print(f"- [{r['status']}] {r['title']}\n    way forward: {r['way_forward']}")
    return 0


def cmd_audit_verify(_):
    res = audit.verify()
    print(json.dumps(res, indent=2))
    return 0 if res["valid"] else 1


def cmd_run_all(a):
    for step in (cmd_validate, cmd_autograde, cmd_agreement, cmd_queue, cmd_score, cmd_report):
        rc = step(a)
        if rc:
            return rc
    return cmd_audit_verify(a)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pharmaeval", description="Pharmaceutical AI evaluation benchmark")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in (("validate", cmd_validate, "schema + referential integrity checks"),
                            ("autograde", cmd_autograde, "deterministic automated grading"),
                            ("agreement", cmd_agreement, "inter-rater agreement"),
                            ("queue", cmd_queue, "build adjudication queue"),
                            ("score", cmd_score, "final scores, analytics and release gate"),
                            ("report", cmd_report, "markdown report + HTML dashboard"),
                            ("audit-verify", cmd_audit_verify, "verify audit-trail hash chain"),
                            ("watchlist", cmd_watchlist, "list draft, pending and withdrawn guidance with way forward"),
                            ("run-all", cmd_run_all, "run the full pipeline")):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(func=fn)
    sp = sub.add_parser("adjudicate", help="record a signed adjudication decision")
    sp.add_argument("--case-id", required=True)
    sp.add_argument("--model-id", required=True)
    sp.add_argument("--adjudicator", required=True)
    sp.add_argument("--error", required=True)
    sp.add_argument("--severity", required=True, choices=["none", "minor", "major", "critical"])
    sp.add_argument("--rationale", required=True)
    sp.set_defaults(func=cmd_adjudicate)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
