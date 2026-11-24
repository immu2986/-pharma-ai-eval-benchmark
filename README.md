# Pharma AI Evaluation Benchmark

[![CI](https://github.com/immu2986/pharma-ai-eval-benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/immu2986/pharma-ai-eval-benchmark/actions/workflows/ci.yml)


An evaluation framework for AI models used in **pharmaceutical technology transfer** and **regulatory filing for drug products (USFDA and EU/EMA)**.

It combines deterministic, domain-aware automated checks with structured SME evaluation, inter-rater agreement, signed adjudication, risk-tiered pass/fail, a release (fitness-for-use) gate and a tamper-evident audit trail. It runs fully offline with no paid API.

> **All shipped cases, model responses and annotations are synthetic.** They show how the framework works; they are not results for any real AI product. The regulatory knowledge base is a starter set and must be maintained under change control before use in GxP decisions.

## What an evaluator can do with it

| Capability | How |
|---|---|
| Evaluate tech-transfer answers | f2 similarity, Cpk, MACO (dose- and PDE-based), impeller scale-up are **recalculated independently** and compared with the model's number, including unit/magnitude slips |
| Evaluate USFDA regulatory answers | Checks the recommended supplement (PAS / CBE-30 / CBE-0 / Annual Report) against 21 CFR 314.70. Under-filing is critical; over-filing is major. Also checks ANDA 505(j) and Q1/Q2 points and eCTD Module 3 placement. |
| Evaluate EU/EMA regulatory answers | Checks Type IA / IA(IN) / IB / II / extension under Regulation (EC) No 1234/2008, procedure timetables, default classification, grouping vs worksharing |
| Apply only effective guidance | A dated guidance registry (25 documents: ICH, FDA, EMA/EC, Health Canada) computes each document's status on the evaluation date. Drafts must be labelled as draft with a way forward to adoption; withdrawn or superseded documents (e.g. FDA's 2021 synthetic peptide guidance, EU 2013 "B" variation codes) only as historical; applicable product-specific guidances (PSGs) must be cited |
| Catch hallucinations | Verifies ICH IDs, 21 CFR parts/sections, CTD sections and EU GMP annexes; probes with non-existent guidances to test **abstention** |
| Catch jurisdiction confusion | Flags US categories recommended for EU procedures and vice versa |
| Red-team RAG assistants | Prompt-injection cases hidden in CDMO/supplier documents; context-support (faithfulness) rate |
| Catch unsafe GMP advice | Forbidden-claim library (e.g. "PUPSIT is optional in the EU", retest-into-compliance) |
| Score with SMEs | 7 weighted dimensions, 21-label error taxonomy, severity, confidence, rationale |
| Measure evaluator reliability | Percent agreement, Cohen's kappa, quadratic-weighted kappa, Fleiss' kappa |
| Adjudicate | Automatic disagreement queue (including automated-vs-human critical conflicts); signed adjudication records |
| Decide fitness for use | Risk tier from model influence × decision consequence (after FDA's 2025 draft AI credibility framework). Pass thresholds tighten with risk; the release gate gives FIT / CONDITIONAL / NOT FIT. |
| Quantify reliability | Bootstrap 95% CI, consistency pass^k over repeated samples, calibration (ECE, Brier, over-confident errors), drift against the previous model version |
| Prove data integrity | Hash-chained ALCOA+ audit trail with SHA-256 fingerprints of every input and output; `audit-verify` detects tampering |
| Report | Markdown report + self-contained HTML dashboard |
| Plug in live models | `integrations.py`: adapter to collect responses from a live model, and an optional, advisory LLM-as-judge |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
python scripts/build_synthetic_dataset.py          # writes data/cases.jsonl and data/responses/
python -m pharmaeval autograde
python scripts/generate_synthetic_annotations.py   # writes data/annotations/
python -m pharmaeval run-all            # validate → auto-grade → agreement → queue → score → report → audit-verify
pytest -q
```

Or run `./scripts/run_pipeline.sh` (macOS/Linux) or `.\scripts\run_pipeline.ps1` (Windows).

Open `reports/dashboard.html` in a browser. Each CI run also uploads the reports as a downloadable artifact.

### Individual steps

```bash
python -m pharmaeval validate
python -m pharmaeval autograde
python -m pharmaeval agreement
python -m pharmaeval queue
python -m pharmaeval adjudicate --case-id TT-001 --model-id model_beta --adjudicator qa_adj_01 \
       --error calculation_error --severity major --rationale "Independent recalculation gives f2 = 73.8 ..."
python -m pharmaeval score
python -m pharmaeval report
python -m pharmaeval audit-verify
python -m pharmaeval watchlist        # draft, pending and withdrawn guidance with way forward to adoption
PHARMAEVAL_AS_OF=2026-06-30 python -m pharmaeval run-all   # re-evaluate as of another date
```

## Pipeline

```
cases.jsonl ─┐
responses/ ──┼─► validate ─► auto-grade (calculators · filing · jurisdiction · citations · forbidden claims · injection · abstention)
annotations/ ┘                    │
                                  ├─► agreement (kappa) ─► adjudication queue ─► signed adjudications
                                  ▼
                     final scoring (60% SME + 40% automated, critical override, risk-tiered thresholds)
                                  ▼
          analytics (bootstrap CI · pass^k · calibration · drift) ─► release gate ─► report + dashboard
                                  ▼
                       hash-chained audit trail (every step)
```

## Repository structure

```
data/
  cases.jsonl                    24 cases: 9 tech transfer, 8 USFDA, 7 EU/EMA
  responses/model_*.jsonl        candidate responses (k=3 samples on 4 cases for consistency)
  annotations/evaluator_*.jsonl  SME annotations (3 evaluators)
  adjudications.jsonl            signed adjudication records
  baselines/                     previous-run summary for drift monitoring
knowledge/regulatory_kb.json     ICH, 21 CFR, CTD Module 3, EU GMP annexes, filing categories
knowledge/guidance_registry.json dated status of tracked guidance (effective, draft, withdrawn) with adoption paths
rubrics/evaluation_rubric.json   dimensions, weights, severities, risk matrix, thresholds, release gate
src/pharmaeval/
  schemas.py        Pydantic schemas and the error taxonomy
  guidance.py       guidance-status engine and watchlist
  calculators.py    f2, Cpk, MACO, scale-up reference calculators
  graders/          citations, filing, numeric, content checks
  auto_grade.py     automated grading
  agreement.py      inter-rater statistics
  adjudication.py   disagreement queue and e-signed decisions
  scoring.py        final scores, model summaries, release gate
  analytics.py      bootstrap CI, consistency, calibration, drift
  audit.py          hash-chained audit trail
  report.py         Markdown + HTML dashboard
  integrations.py   live-model adapter and LLM-as-judge (optional)
  cli.py            command-line interface
scripts/            dataset builders and one-command pipeline runners
docs/               METHODOLOGY, ERROR_TAXONOMY, ANNOTATION_GUIDELINES
tests/              53 pytest tests
```

## Maintaining the guidance registry

Add or update an entry in `knowledge/guidance_registry.json` whenever a regulator publishes, finalises, withdraws or replaces a document. Each entry holds regex `patterns` that detect citations, `status` (`final`, `draft`, `concept`, `pending_adoption`), `published` and `effective_date`, `withdrawn_on` / `superseded_on` with `superseded_by`, the official `url`, `verified_on`, and for non-final texts an `adoption_path` (stage, next milestone, expected timing, recommended action). `python -m pharmaeval validate` rejects drafts without an adoption path and broken replacement links. Use `required_guidance` in a case to require a specific document (for example a PSG).

## Adding your own cases

Add a line to `data/cases.jsonl`. Each case needs at least one objective check: `required_points`, `computation`, `expected_filing`, or `expect_abstention`. Cases with `expected_filing` must also require the `Recommended filing:` line. Run `python -m pharmaeval validate` to check schema, regexes and referential integrity.

```json
{"case_id": "FDA-007", "domain": "regulatory_fda", "task_type": "filing_classification",
 "dosage_form": "sterile injectable", "jurisdiction": "FDA",
 "context_of_use": "Draft change-control regulatory assessment",
 "model_influence": "high", "decision_consequence": "high",
 "prompt": "... End with 'Recommended filing: <category>'.",
 "reference_answer": "...",
 "required_points": [{"id": "basis", "description": "Cites 314.70", "any_of": ["314\\.70"]}],
 "expected_filing": {"jurisdiction": "FDA", "category": "PAS"},
 "format_requirements": ["recommended_filing_line"]}
```

## Evaluating a live model

```python
from pharmaeval.integrations import AnthropicAdapter, collect_responses
collect_responses(AnthropicAdapter(model="claude-sonnet-5-5"), model_id="my_model", model_version="1.0", samples=3)
```

Then collect SME annotations into `data/annotations/` and run `python -m pharmaeval run-all`.

## Version history

- **1.1.0 (24 Nov 2026):** guidance-status engine and watchlist; release gate requires zero guidance-status errors; 4 new cases (tirzepatide PSG, biosimilar CES draft, EU Q-code site change, ICH Q1 draft); EMA cases moved to Commission Variations Guidelines C/2025/5045; FDA 2021 synthetic peptide guidance marked withdrawn (28 Jul 2026).
- **1.0.0:** initial release.

## Roadmap

- A larger case bank: stability shelf life (ICH Q1E), tolerance intervals, PPQ sampling plans, Q12 established conditions, biologics comparability (Q5E), nitrosamines (M7)
- Semantic (embedding / NLI) coverage scoring alongside regex
- Sentence-level claim extraction and entailment against retrieved guidance for RAG faithfulness
- Label Studio / Argilla annotation integration; Hugging Face dataset export
- Multilingual cases (EU national competent authority languages)
- Continuous evaluation in CI with drift alerts on every model release

## License

MIT
