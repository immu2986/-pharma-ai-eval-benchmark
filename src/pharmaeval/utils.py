"""Shared I/O helpers and constants."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
RUBRIC_PATH = ROOT / "rubrics" / "evaluation_rubric.json"
KB_PATH = ROOT / "knowledge" / "regulatory_kb.json"

SEVERITY_RANK = {"none": 0, "minor": 1, "major": 2, "critical": 3}


def load_json(path: Path | str) -> dict:
    with Path(path).open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path | str, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def load_jsonl(path: Path | str) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: line {n} is not valid JSON ({exc})") from exc
    return rows


def write_jsonl(path: Path | str, rows: Iterable[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def max_severity(levels: Iterable[str]) -> str:
    best = "none"
    for lvl in levels:
        if SEVERITY_RANK[lvl] > SEVERITY_RANK[best]:
            best = lvl
    return best


def load_rubric() -> dict:
    return load_json(RUBRIC_PATH)


def load_kb() -> dict:
    return load_json(KB_PATH)


def load_cases(path: Path | str | None = None) -> dict[str, dict]:
    rows = load_jsonl(path or DATA / "cases.jsonl")
    return {r["case_id"]: r for r in rows}


def load_responses(directory: Path | str | None = None) -> list[dict]:
    directory = Path(directory or DATA / "responses")
    rows: list[dict] = []
    for f in sorted(directory.glob("*.jsonl")):
        rows.extend(load_jsonl(f))
    return rows


def load_annotations(directory: Path | str | None = None) -> list[dict]:
    directory = Path(directory or DATA / "annotations")
    rows: list[dict] = []
    for f in sorted(directory.glob("evaluator_*.jsonl")):
        rows.extend(load_jsonl(f))
    return rows


def risk_tier(case: dict, rubric: dict) -> str:
    return rubric["risk_matrix"][case["model_influence"]][case["decision_consequence"]]
