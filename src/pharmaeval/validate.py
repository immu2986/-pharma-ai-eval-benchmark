"""Schema and referential-integrity validation for all pipeline inputs."""
from __future__ import annotations

import re
from collections import Counter

from pydantic import ValidationError

from .schemas import Adjudication, Annotation, EvaluationCase, ModelResponse
from .utils import DATA, load_annotations, load_jsonl, load_responses


def _validate_rows(rows, model, label):
    errors, ok = [], []
    for i, row in enumerate(rows, start=1):
        try:
            ok.append(model.model_validate(row))
        except ValidationError as exc:
            errors.append(f"{label} record {i}: {exc.errors()[0]['loc']} {exc.errors()[0]['msg']}")
    return ok, errors


def validate_all() -> dict:
    errors: list[str] = []
    cases, e = _validate_rows(load_jsonl(DATA / "cases.jsonl"), EvaluationCase, "case")
    errors += e
    case_ids = Counter(c.case_id for c in cases)
    errors += [f"duplicate case_id {cid}" for cid, n in case_ids.items() if n > 1]
    for c in cases:
        for rp in c.required_points:
            for p in rp.any_of:
                try:
                    re.compile(p)
                except re.error as exc:
                    errors.append(f"{c.case_id}/{rp.id}: bad regex {p!r} ({exc})")
        for fc in c.forbidden_claims:
            try:
                re.compile(fc.pattern)
            except re.error as exc:
                errors.append(f"{c.case_id}/{fc.id}: bad regex ({exc})")

    from .guidance import load_registry
    registry = load_registry()
    reg_ids = [d["id"] for d in registry["documents"]]
    errors += [f"duplicate registry id {i}" for i, n in Counter(reg_ids).items() if n > 1]
    for d in registry["documents"]:
        for p in d["patterns"]:
            try:
                re.compile(p)
            except re.error as exc:
                errors.append(f"registry {d['id']}: bad regex ({exc})")
        if d["status"] in ("draft", "concept", "pending_adoption") and not d.get("adoption_path"):
            errors.append(f"registry {d['id']}: non-final document needs an adoption_path")
        if d.get("superseded_by") and d["superseded_by"] not in reg_ids:
            errors.append(f"registry {d['id']}: superseded_by {d['superseded_by']} not in registry")
    from .graders.applicability import classify
    for c in cases:
        if c.computation and c.computation.kind == "f2" and classify(c.model_dump()) == "not_applicable":
            errors.append(f"{c.case_id}: asks for f2 but dosage form '{c.dosage_form}' has no release profile")
    for c in cases:
        errors += [f"{c.case_id}: required_guidance {g} not in registry" for g in c.required_guidance if g not in reg_ids]

    responses, e = _validate_rows(load_responses(), ModelResponse, "response")
    errors += e
    keys = Counter((r.case_id, r.model_id, r.sample_index) for r in responses)
    errors += [f"duplicate response {k}" for k, n in keys.items() if n > 1]
    errors += [f"response for unknown case {r.case_id}" for r in responses if r.case_id not in case_ids]
    models = sorted({r.model_id for r in responses})
    for m in models:
        missing = set(case_ids) - {r.case_id for r in responses if r.model_id == m and r.sample_index == 0}
        errors += [f"{m}: no sample-0 response for {cid}" for cid in sorted(missing)]

    annotations, e = _validate_rows(load_annotations(), Annotation, "annotation")
    errors += e
    resp_keys = {(r.case_id, r.model_id) for r in responses}
    errors += [f"annotation for unknown response {(a.case_id, a.model_id)}" for a in annotations
               if (a.case_id, a.model_id) not in resp_keys]
    akeys = Counter((a.case_id, a.model_id, a.evaluator_id) for a in annotations)
    errors += [f"duplicate annotation {k}" for k, n in akeys.items() if n > 1]

    adj_path = DATA / "adjudications.jsonl"
    adjudications = []
    if adj_path.exists():
        adjudications, e = _validate_rows(load_jsonl(adj_path), Adjudication, "adjudication")
        errors += e

    return {
        "valid": not errors, "errors": errors,
        "counts": {"cases": len(cases), "responses": len(responses), "models": models,
                   "annotations": len(annotations), "evaluators": sorted({a.evaluator_id for a in annotations}),
                   "adjudications": len(adjudications), "registry_documents": len(reg_ids)},
    }


if __name__ == "__main__":
    import json
    import sys
    res = validate_all()
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["valid"] else 1)
