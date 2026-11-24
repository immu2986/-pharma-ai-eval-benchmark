"""Markdown report and self-contained HTML dashboard."""
from __future__ import annotations

import csv
import html
from collections import defaultdict

from .audit import verify
from .utils import REPORTS, load_json, load_jsonl

DOMAIN_NAMES = {"tech_transfer": "Technology transfer", "regulatory_fda": "USFDA regulatory", "regulatory_ema": "EU / EMA regulatory"}
DISCLAIMER = ("All cases, model responses and evaluator annotations in this demo are SYNTHETIC. Results show how the "
              "framework works; they say nothing about any real AI product.")


def _load():
    summary = load_json(REPORTS / "model_summary.json")
    finals = load_jsonl(REPORTS / "final_scores.jsonl")
    autos = load_jsonl(REPORTS / "auto_grades.jsonl")
    agreement = load_json(REPORTS / "agreement_summary.json")
    queue = []
    qp = REPORTS / "adjudication_queue.csv"
    if qp.exists():
        with qp.open(encoding="utf-8") as fh:
            queue = list(csv.DictReader(fh))
    return summary, finals, autos, agreement, queue


def citation_stats(autos: list[dict]) -> dict[str, dict]:
    out = defaultdict(lambda: {"total": 0, "verified": 0, "fabricated": 0})
    for g in autos:
        if g["sample_index"]:
            continue
        s = out[g["model_id"]]
        s["total"] += len(g["citations"])
        s["verified"] += sum(c["verified"] for c in g["citations"])
        s["fabricated"] += sum(1 for f in g["findings"] if f["error"] == "fabricated_citation")
    return dict(out)


def guidance_data(autos: list[dict]):
    wl_path = REPORTS / "guidance_watchlist.json"
    wl = load_json(wl_path) if wl_path.exists() else {"evaluation_as_of": "n/a", "documents": []}
    rows = []
    for g in autos:
        if g["sample_index"]:
            continue
        for c in g.get("guidance_citations", []):
            if c["presented_as"] != "requirement":
                rows.append({"case_id": g["case_id"], "model_id": g["model_id"], **c})
    return wl, rows


def _pct(x) -> str:
    return "n/a" if x is None else f"{x:.0%}"


# ----------------------------------------------------------------------------- Markdown
def markdown(summary, finals, autos, agreement, queue) -> str:
    L = ["# Pharmaceutical AI Evaluation Report",
         "", f"Run date: {summary['run_date']} · Rubric v{summary['rubric_version']}", "", f"> {DISCLAIMER}", "",
         "## Release decision (fitness for intended use)", ""]
    for m, s in summary["models"].items():
        L += [f"### {m} (v{s['model_version']}): **{s['release_decision']}**", ""]
        L += [f"- {r}" for r in s["release_reasons"]] + [""]
    L += ["## Leaderboard", "",
          "| Model | Pass rate | Mean final score (95% CI) | Human | Auto | Critical | Major | pass^k | ECE |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m, s in summary["models"].items():
        lo, hi = s["mean_final_score_ci95"]
        L.append(f"| {m} | {_pct(s['pass_rate'])} | {s['mean_final_score']} ({lo}–{hi}) | {s['mean_human_score']} | "
                 f"{s['mean_auto_score']} | {s['critical_findings']} | {s['major_findings']} | "
                 f"{s['consistency'].get('pass_hat_k')} | {s['calibration'].get('ece')} |")
    L += ["", "## Results by domain", "", "| Model | Domain | n | Pass rate | Mean score |", "|---|---|---|---|---|"]
    for m, s in summary["models"].items():
        for d, v in s["by_domain"].items():
            L.append(f"| {m} | {DOMAIN_NAMES.get(d, d)} | {v['n']} | {_pct(v['pass_rate'])} | {v['mean_final_score']} |")
    L += ["", "## Critical and major findings", "", "| Case | Model | Severity | Error | Evidence |", "|---|---|---|---|---|"]
    for f in finals:
        if f["final_severity"] in ("critical", "major"):
            ev = "; ".join(f["findings"][:2]).replace("|", "/")
            L.append(f"| {f['case_id']} | {f['model_id']} | {f['final_severity']} | {f['final_error']} | {ev} |")
    L += ["", "## Evaluator agreement", "",
          f"Fleiss' kappa: error label {agreement['fleiss_kappa_error_label']} ({agreement['fleiss_error_label_interpretation']}), "
          f"severity {agreement['fleiss_kappa_severity']} ({agreement['fleiss_severity_interpretation']}).", "",
          "| Pair | Label agreement | Label kappa | Severity agreement | Severity QW kappa |", "|---|---|---|---|---|"]
    for p in agreement["pairwise"]:
        L.append(f"| {p['pair']} | {_pct(p['error_label_agreement'])} | {p['error_label_kappa']} | "
                 f"{_pct(p['severity_agreement'])} | {p['severity_qw_kappa']} |")
    pend = sum(1 for q in queue if q["status"] == "pending")
    L += ["", "## Adjudication", "", f"{len(queue)} item(s) flagged; {len(queue) - pend} signed, {pend} pending.", ""]
    cs = citation_stats(autos)
    L += ["## Citation verification", "", "| Model | Citations | Verified | Fabricated |", "|---|---|---|---|"]
    for m, s in cs.items():
        L.append(f"| {m} | {s['total']} | {s['verified']} | {s['fabricated']} |")
    wl, grows = guidance_data(autos)
    L += ["", f"## Guidance status (as of {wl['evaluation_as_of']})", "",
          "Only guidance in force on the evaluation date is accepted as a requirement. Drafts must be labelled and carry a way "
          "forward to adoption; withdrawn or superseded documents may only be cited as historical.", "",
          "| Model | Guidance-status errors | Drafts / pending labelled correctly |", "|---|---|---|"]
    for m, s in summary["models"].items():
        L.append(f"| {m} | {s.get('guidance_status_errors', 0)} | {s.get('drafts_labelled_correctly', 0)} |")
    L += ["", "### Draft, pending and withdrawn guidance watchlist", "", "| Document | Issuer | Status | Way forward to adoption |", "|---|---|---|---|"]
    for d in wl["documents"]:
        L.append(f"| [{d['title']}]({d['url']}) | {d['issuer']} | {d['status']} | {d['way_forward'].replace('|', '/')} |")
    L += ["", "### Non-effective documents cited in model answers", "", "| Case | Model | Document | Status | Presented as | OK |", "|---|---|---|---|---|---|"]
    for r in grows:
        L.append(f"| {r['case_id']} | {r['model_id']} | {r['title']} | {r['status_as_of']} | {r['presented_as']} | {'yes' if r['ok'] else 'NO'} |")
    a = verify()
    L += ["", "## Audit trail", "", f"Hash chain {'VALID' if a['valid'] else 'BROKEN'} · {a['entries']} entries.", "",
          "## Methodology and limitations", "",
          "Scores blend SME evaluation (60%) with deterministic automated checks (40%). Pass thresholds and the maximum "
          "tolerated severity depend on model risk (model influence x decision consequence). Any critical automated finding "
          "fails the item unless overruled by a signed adjudication. The knowledge base is a curated starter set and must be "
          "maintained under change control. Regex-based checks can miss paraphrased content; human review remains required.", ""]
    return "\n".join(L)


# ----------------------------------------------------------------------------- HTML
CSS = """
:root{--ink:#14213d;--muted:#5c677d;--line:#e3e7ee;--bg:#f7f8fb;--ok:#1b7f5b;--warn:#b7791f;--bad:#b42318;--accent:#2f5aa8}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 -apple-system,Segoe UI,Inter,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{background:var(--ink);color:#fff;padding:28px 32px}header h1{margin:0;font-size:22px}header p{margin:6px 0 0;color:#c9d3e6}
main{max-width:1180px;margin:0 auto;padding:24px}section{background:#fff;border:1px solid var(--line);border-radius:10px;padding:20px 22px;margin:0 0 18px}
h2{font-size:17px;margin:0 0 12px}.note{background:#fff7e6;border:1px solid #f3d9a4;padding:10px 14px;border-radius:8px;color:#7a5200;margin-bottom:18px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}.card{border:1px solid var(--line);border-radius:10px;padding:16px}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-weight:600;font-size:12px;color:#fff}
.fit{background:var(--ok)}.cond{background:var(--warn)}.notfit{background:var(--bad)}
.kpis{display:flex;gap:18px;margin:10px 0}.kpi b{display:block;font-size:20px}.kpi span{color:var(--muted);font-size:12px}
ul.reasons{margin:8px 0 0;padding-left:18px}ul.reasons li{font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600}.sev-critical{color:var(--bad);font-weight:600}.sev-major{color:var(--warn);font-weight:600}
.bar{height:10px;background:#e9edf5;border-radius:5px;overflow:hidden}.bar i{display:block;height:100%;background:var(--accent)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:800px){.grid2{grid-template-columns:1fr}}
small{color:var(--muted)}
"""


def _badge(decision: str) -> str:
    cls = "fit" if decision.startswith("FIT") else "cond" if decision.startswith("CONDITIONALLY") else "notfit"
    return f'<span class="badge {cls}">{html.escape(decision)}</span>'


def _bar(x: float) -> str:
    return f'<div class="bar"><i style="width:{max(0, min(1, x)) * 100:.0f}%"></i></div>'


def dashboard(summary, finals, autos, agreement, queue) -> str:
    e = html.escape
    H = [f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Pharma AI Evaluation Dashboard</title><style>{CSS}</style></head><body>",
         f"<header><h1>Pharmaceutical AI Evaluation Dashboard</h1><p>Technology transfer · USFDA · EU/EMA regulatory filing · "
         f"run {e(summary['run_date'])} · rubric v{e(summary['rubric_version'])}</p></header><main>",
         f"<div class='note'>{e(DISCLAIMER)}</div>",
         "<section><h2>Release decision: fitness for intended use</h2><div class='cards'>"]
    for m, s in summary["models"].items():
        lo, hi = s["mean_final_score_ci95"]
        H.append(f"<div class='card'><div><b>{e(m)}</b> <small>v{e(str(s['model_version']))}</small></div>"
                 f"<div style='margin:8px 0'>{_badge(s['release_decision'])}</div>"
                 f"<div class='kpis'><div class='kpi'><b>{_pct(s['pass_rate'])}</b><span>pass rate</span></div>"
                 f"<div class='kpi'><b>{s['mean_final_score']}</b><span>mean score (95% CI {lo}–{hi})</span></div>"
                 f"<div class='kpi'><b>{s['critical_findings']}</b><span>critical</span></div></div>"
                 "<ul class='reasons'>" + "".join(f"<li>{e(r)}</li>" for r in s["release_reasons"]) + "</ul></div>")
    H.append("</div></section>")

    H.append("<section><h2>Leaderboard</h2><table><tr><th>Model</th><th>Pass rate</th><th>Mean final</th><th>Human</th>"
             "<th>Automated</th><th>Critical</th><th>Major</th><th>pass^k</th><th>Answer stability</th><th>ECE</th><th>Drift</th></tr>")
    for m, s in summary["models"].items():
        d = s["drift"]
        drift_txt = "n/a" if d.get("baseline_version") is None else (
            f"{'ALERT ' if d['alert'] else ''}{d['delta_pass_rate']:+.0%} pass, {d['delta_mean_final_score']:+} pts vs v{d['baseline_version']}")
        H.append(f"<tr><td>{e(m)}</td><td>{_pct(s['pass_rate'])}{_bar(s['pass_rate'])}</td><td>{s['mean_final_score']}</td>"
                 f"<td>{s['mean_human_score']}</td><td>{s['mean_auto_score']}</td><td>{s['critical_findings']}</td>"
                 f"<td>{s['major_findings']}</td><td>{s['consistency'].get('pass_hat_k')}</td>"
                 f"<td>{s['consistency'].get('answer_stability')}</td><td>{s['calibration'].get('ece')}</td><td>{e(drift_txt)}</td></tr>")
    H.append("</table></section>")

    H.append("<section class='grid2'><div><h2>Pass rate by domain</h2><table><tr><th>Domain</th>" +
             "".join(f"<th>{e(m)}</th>" for m in summary["models"]) + "</tr>")
    domains = sorted({d for s in summary["models"].values() for d in s["by_domain"]})
    for d in domains:
        H.append(f"<tr><td>{e(DOMAIN_NAMES.get(d, d))}</td>" + "".join(
            f"<td>{_pct(s['by_domain'][d]['pass_rate'])}{_bar(s['by_domain'][d]['pass_rate'])}</td>" for s in summary["models"].values()) + "</tr>")
    H.append("</table></div><div><h2>Pass rate by model-risk tier</h2><table><tr><th>Risk tier</th>" +
             "".join(f"<th>{e(m)}</th>" for m in summary["models"]) + "</tr>")
    for t in ("high", "medium", "low"):
        H.append(f"<tr><td>{t}</td>" + "".join(
            f"<td>{_pct(s['by_risk_tier'][t]['pass_rate']) if t in s['by_risk_tier'] else 'n/a'}"
            f" <small>(n={s['by_risk_tier'].get(t, {}).get('n', 0)})</small></td>" for s in summary["models"].values()) + "</tr>")
    H.append("</table></div></section>")

    H.append("<section><h2>Critical and major findings</h2><table><tr><th>Case</th><th>Model</th><th>Severity</th><th>Error</th>"
             "<th>Label source</th><th>Evidence from automated checks</th></tr>")
    for f in finals:
        if f["final_severity"] in ("critical", "major"):
            H.append(f"<tr><td>{e(f['case_id'])}</td><td>{e(f['model_id'])}</td><td class='sev-{f['final_severity']}'>{f['final_severity']}</td>"
                     f"<td>{e(f['final_error'])}</td><td><small>{e(f['label_source'])}</small></td>"
                     f"<td>{'<br>'.join(e(x) for x in f['findings'][:3])}</td></tr>")
    H.append("</table></section>")

    errs = defaultdict(dict)
    for m, s in summary["models"].items():
        for k, v in s["error_distribution"].items():
            errs[k][m] = v
    H.append("<section class='grid2'><div><h2>Error distribution</h2><table><tr><th>Error</th>" +
             "".join(f"<th>{e(m)}</th>" for m in summary["models"]) + "</tr>")
    for k in sorted(errs, key=lambda x: -sum(errs[x].values())):
        H.append(f"<tr><td>{e(k)}</td>" + "".join(f"<td>{errs[k].get(m, 0)}</td>" for m in summary["models"]) + "</tr>")
    H.append("</table></div><div><h2>Citation verification</h2><table><tr><th>Model</th><th>Citations</th><th>Verified</th><th>Fabricated</th></tr>")
    for m, s in citation_stats(autos).items():
        H.append(f"<tr><td>{e(m)}</td><td>{s['total']}</td><td>{s['verified']}</td><td>{s['fabricated']}</td></tr>")
    H.append("</table><p><small>ICH IDs, 21 CFR parts/sections, CTD Module 3 sections and EU GMP annexes are checked against the curated knowledge base.</small></p></div></section>")

    H.append(f"<section><h2>Evaluator agreement</h2><p>Fleiss' kappa: error label <b>{agreement['fleiss_kappa_error_label']}</b> "
             f"({e(agreement['fleiss_error_label_interpretation'])}), severity <b>{agreement['fleiss_kappa_severity']}</b> "
             f"({e(agreement['fleiss_severity_interpretation'])}).</p><table><tr><th>Pair</th><th>Label agreement</th><th>Cohen's kappa</th>"
             "<th>Severity agreement</th><th>Severity QW kappa</th><th>Accuracy-dimension QW kappa</th></tr>")
    for p in agreement["pairwise"]:
        H.append(f"<tr><td>{e(p['pair'])}</td><td>{_pct(p['error_label_agreement'])}</td><td>{p['error_label_kappa']}</td>"
                 f"<td>{_pct(p['severity_agreement'])}</td><td>{p['severity_qw_kappa']}</td>"
                 f"<td>{p['dimensions']['scientific_regulatory_accuracy']['qw_kappa']}</td></tr>")
    H.append("</table></section>")

    pend = sum(1 for q in queue if q["status"] == "pending")
    H.append(f"<section><h2>Adjudication queue</h2><p>{len(queue)} flagged · {len(queue) - pend} signed · {pend} pending</p>"
             "<table><tr><th>Case</th><th>Model</th><th>Reasons</th><th>Status</th><th>Final decision</th></tr>")
    for q in queue:
        dec = f"{q['final_error']} / {q['final_severity']} (signed by {q['adjudicator']})" if q["status"] == "adjudicated" else "—"
        H.append(f"<tr><td>{e(q['case_id'])}</td><td>{e(q['model_id'])}</td><td><small>{e(q['reasons'])}</small></td>"
                 f"<td>{e(q['status'])}</td><td>{e(dec)}</td></tr>")
    H.append("</table></section>")

    H.append("<section class='grid2'><div><h2>Calibration (stated confidence vs correctness)</h2><table><tr><th>Model</th><th>ECE</th>"
             "<th>Brier</th><th>Over-confident errors</th></tr>")
    for m, s in summary["models"].items():
        c = s["calibration"]
        H.append(f"<tr><td>{e(m)}</td><td>{c.get('ece')}</td><td>{c.get('brier')}</td><td>{c.get('overconfident_errors')}</td></tr>")
    H.append("</table></div><div><h2>Consistency across repeated samples</h2><table><tr><th>Model</th><th>Cases</th><th>k</th>"
             "<th>pass@1</th><th>pass^k</th></tr>")
    for m, s in summary["models"].items():
        c = s["consistency"]
        H.append(f"<tr><td>{e(m)}</td><td>{c.get('n_cases')}</td><td>{c.get('k')}</td><td>{c.get('pass_at_1')}</td><td>{c.get('pass_hat_k')}</td></tr>")
    H.append("</table></div></section>")

    wl, grows = guidance_data(autos)
    H.append(f"<section><h2>Guidance status: effective vs draft (as of {e(wl['evaluation_as_of'])})</h2>"
             "<p>Only guidance in force on the evaluation date is accepted as a requirement. Drafts and pending texts must be labelled "
             "and carry a way forward to adoption; withdrawn or superseded documents may only be cited as historical.</p>"
             "<table><tr><th>Model</th><th>Guidance-status errors</th><th>Drafts / pending labelled correctly</th></tr>")
    for m, s in summary["models"].items():
        H.append(f"<tr><td>{e(m)}</td><td class='{'sev-major' if s.get('guidance_status_errors') else ''}'>{s.get('guidance_status_errors', 0)}</td>"
                 f"<td>{s.get('drafts_labelled_correctly', 0)}</td></tr>")
    H.append("</table><h2 style='margin-top:18px'>Draft, pending and withdrawn guidance watchlist</h2><table><tr><th>Document</th><th>Issuer</th>"
             "<th>Status</th><th>Way forward to adoption</th></tr>")
    for d in wl["documents"]:
        H.append(f"<tr><td><a href='{e(d['url'])}'>{e(d['title'])}</a><br><small>verified {e(str(d.get('verified_on')))}</small></td>"
                 f"<td>{e(d['issuer'])}</td><td>{e(d['status'])}</td><td><small>{e(d['way_forward'])}</small></td></tr>")
    H.append("</table><h2 style='margin-top:18px'>Non-effective documents cited in model answers</h2><table><tr><th>Case</th><th>Model</th>"
             "<th>Document</th><th>Status</th><th>Presented as</th><th>Correct?</th></tr>")
    for r in grows:
        H.append(f"<tr><td>{e(r['case_id'])}</td><td>{e(r['model_id'])}</td><td>{e(r['title'])}</td><td>{e(r['status_as_of'])}</td>"
                 f"<td>{e(r['presented_as'])}</td><td class='{'' if r['ok'] else 'sev-critical'}'>{'yes' if r['ok'] else 'NO'}</td></tr>")
    H.append("</table></section>")
    a = verify()
    H.append(f"<section><h2>Data integrity</h2><p>Audit trail hash chain: <b>{'VALID' if a['valid'] else 'BROKEN: ' + e(a.get('error', ''))}</b> "
             f"· {a['entries']} entries. Each pipeline step records actor, UTC timestamp and SHA-256 fingerprints of inputs and "
             "outputs (ALCOA+). Adjudications carry an e-signature manifest (signer, date/time, meaning).</p></section>")
    H.append("<section><h2>Methodology</h2><p>Final score = 60% SME rubric score (7 weighted dimensions) + 40% deterministic "
             "automated score (required-point coverage, independent recalculation of f2 / Cpk / MACO / scale-up values, filing-category "
             "and jurisdiction checks, citation verification, forbidden-claim and prompt-injection detection, abstention probes). "
             "Pass thresholds tighten with model risk (model influence x decision consequence, after FDA's 2025 draft AI credibility "
             "framework). Any critical automated finding fails the item unless overruled by a signed adjudication.</p></section>")
    H.append("</main></body></html>")
    return "".join(H)


def run() -> None:
    data = _load()
    (REPORTS / "evaluation_report.md").write_text(markdown(*data), encoding="utf-8")
    (REPORTS / "dashboard.html").write_text(dashboard(*data), encoding="utf-8")


if __name__ == "__main__":
    run()
    print("wrote reports/evaluation_report.md and reports/dashboard.html")
