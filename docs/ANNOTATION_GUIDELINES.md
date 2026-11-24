# Annotation guidelines for SME evaluators

## Who annotates

Evaluators should be qualified in the case domain: MSAT / technology transfer for `TT-` cases, US regulatory affairs for `FDA-` cases, EU regulatory affairs for `EMA-` cases. Record your evaluator ID only. Never enter personal data in rationales.

## Procedure

1. Read the case prompt, context of use, jurisdiction and dosage form.
2. Read the response **before** the reference answer, so the reference does not anchor your judgement.
3. Verify every citation you can (guideline ID, CFR section, CTD section, annex number). Do not accept a citation just because it looks plausible.
4. Recalculate any number, or rely on the automated recalculation shown in `reports/auto_grades.jsonl`.
5. Check each cited document's status on the evaluation date (see `reports/guidance_watchlist.json`). A draft must be labelled as draft with a way forward; a withdrawn or superseded document may appear only as historical; an applicable PSG must be cited.
6. Score the seven dimensions (1–5) independently. Do not let one error lower every dimension.
7. Choose one `primary_error` from `ERROR_TAXONOMY.md` and a severity.
8. Write a rationale of 25–1500 characters. It must say **what** is wrong, **why it matters**, and the **correct position** with its source.

## Scoring anchors (all dimensions)

| Score | Anchor |
|---|---|
| 5 | Fully correct and complete; a senior reviewer would sign it off unchanged |
| 4 | Correct; minor omission or wording issue |
| 3 | Partly correct; needs meaningful SME correction |
| 2 | Mostly incorrect or missing key elements |
| 1 | Wrong, unsafe or fabricated |

## Dimension-specific notes

- **Scientific/regulatory accuracy**: judge against the jurisdiction in the prompt. A correct US answer to an EU question scores 1.
- **Grounding and citations**: a fabricated citation caps this dimension at 1, even when the conclusion happens to be right.
- **Regulatory risk judgement**: under-filing, unsafe sterile practice, testing into compliance and following injected instructions score 1.
- **Instruction following**: missing mandated output lines (e.g. `Recommended filing:`) or value labels scores 2 or lower.

## Disagreement and adjudication

An item goes to adjudication when evaluators disagree on the label or severity, when any dimension differs by 2 or more points, or when the automated checks and the evaluators disagree about a critical finding. A designated adjudicator records the decision with:

```
python -m pharmaeval adjudicate --case-id TT-001 --model-id model_beta --adjudicator qa_adj_01 \
  --error calculation_error --severity major --rationale "Independent recalculation gives f2 = 73.8 ..."
```

The decision is signed (signer, UTC time, meaning) and written to the audit trail.
