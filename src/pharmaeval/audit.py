"""ALCOA+-style, tamper-evident audit trail (hash-chained JSONL).

Each entry records who did what, when (UTC), with SHA-256 fingerprints of the
input and output files, and the hash of the previous entry. Any edit, deletion
or re-ordering of past entries breaks the chain and is caught by verify().
This supports, but does not by itself make a system, 21 CFR Part 11 / EU GMP
Annex 11 compliant.
"""
from __future__ import annotations

import getpass
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .utils import REPORTS, ROOT, sha256_file

AUDIT_PATH = REPORTS / "audit_trail.jsonl"
GENESIS = "0" * 64


def _entry_hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _fingerprints(paths) -> dict[str, str]:
    out = {}
    for p in paths or []:
        p = Path(p)
        if p.is_file():
            try:
                key = str(p.resolve().relative_to(ROOT))
            except ValueError:
                key = str(p)
            out[key] = sha256_file(p)
    return out


def log_event(action: str, inputs=None, outputs=None, details: dict | None = None, actor: str | None = None,
              path: Path = AUDIT_PATH) -> dict:
    entries = _read(path)
    try:
        default_actor = getpass.getuser()
    except Exception:  # pragma: no cover
        default_actor = "unknown"
    entry = {
        "seq": len(entries) + 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "actor": actor or default_actor,
        "action": action,
        "inputs": _fingerprints(inputs),
        "outputs": _fingerprints(outputs),
        "details": details or {},
        "prev_hash": entries[-1]["entry_hash"] if entries else GENESIS,
    }
    entry["entry_hash"] = _entry_hash(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def verify(path: Path = AUDIT_PATH) -> dict:
    entries = _read(path)
    prev = GENESIS
    for i, e in enumerate(entries, start=1):
        if e.get("seq") != i:
            return {"valid": False, "entries": len(entries), "error": f"sequence break at entry {i}"}
        if e.get("prev_hash") != prev:
            return {"valid": False, "entries": len(entries), "error": f"chain broken at entry {i}"}
        if _entry_hash(e) != e.get("entry_hash"):
            return {"valid": False, "entries": len(entries), "error": f"entry {i} content altered"}
        prev = e["entry_hash"]
    return {"valid": True, "entries": len(entries), "head": prev}

