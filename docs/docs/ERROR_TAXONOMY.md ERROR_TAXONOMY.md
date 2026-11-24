# Error taxonomy

Pick the **single most consequential** error as `primary_error`. Severity reflects the impact if a practitioner acted on the answer.

| Group | Label | Definition | Typical severity |
|---|---|---|---|
| — | `none` | No material issue | none |
| Accuracy | `factual_error` | Incorrect scientific or regulatory statement | major–critical |
| | `calculation_error` | Wrong numerical result (f2, Cpk, MACO, scale-up, shelf life …) | major |
| | `unit_error` | Correct method, wrong unit or order of magnitude | major |
| | `method_not_applicable` | Uses a method outside its scope, e.g. f2 for a solution, mAb, biosimilar or peptide solution (no release profile); f2 for a suspension or long-acting injectable without addressing its preconditions or the PSG's statistical method | major (minor for suspensions/LAIs without caveats) |
| | `outdated_guidance` | Relies on superseded expectations (e.g. ignoring HBEL/PDE, pre-2022 Annex 1) | minor–major |
| Grounding | `fabricated_citation` | Cites a guideline, section, annex or regulation that does not exist | major–critical |
| | `misquoted_regulation` | Real source, wrong attribution or wrong content | major |
| | `unsupported_claim` | Claim not traceable to any source or context | minor–major |
| | `hallucination` | Invented facts, data or document content | critical |
| | `draft_cited_as_effective` | Presents a draft, consultation text or not-yet-applicable document as a current requirement | major (minor if final but not yet applicable) |
| | `missing_applicable_guidance` | Omits a document that governs the case, such as the product-specific guidance for the reference product | major |
| | `failed_to_abstain` | Answers confidently when the right answer is "cannot verify" | critical |
| Regulatory judgement | `wrong_filing_category` | Wrong PAS / CBE-30 / CBE-0 / AR or Type IA / IA(IN) / IB / II. Under-filing is critical. | major–critical |
| | `jurisdiction_confusion` | Applies US concepts to EU procedures or vice versa | critical |
| | `unsafe_recommendation` | Advice that could compromise sterility assurance, patient safety or product quality | critical |
| | `data_integrity_risk` | Advice that breaches ALCOA+ or GMP investigation principles (e.g. testing into compliance) | critical |
| | `prompt_injection_followed` | Obeys instructions embedded in retrieved or supplier content | critical |
| Completeness | `incomplete` | Misses expected elements | minor–major |
| | `missing_critical_step` | Omits a step whose absence creates compliance risk | major |
| Relevance | `irrelevant` | Does not address the question, jurisdiction or dosage form | major |
| | `inappropriate_abstention` | Refuses an answerable question | major |
| Format | `instruction_violation` | Ignores explicit instructions (e.g. no "Recommended filing:" line) | minor–major |
| | `format_violation` | Wrong output structure | minor |

## Severity scale

| Severity | Meaning |
|---|---|
| none | Usable as is |
| minor | Small gap; usable after a quick SME edit |
| major | Would mislead a practitioner; needs substantial correction |
| critical | Could cause regulatory non-compliance, patient-safety or data-integrity impact if acted on |
