"""A person's answer to one open point of one stage (`hi answer`), kept in `.hi/answers.json`.

It is for a question about the work of that stage (who performs an analysis, what stays open). A decision about the
product belongs in the project inputs, where every stage is judged against it. An answer holds for the wording of the
open point it was given to, is part of the sealed package, and is never evidence that something was verified."""
from __future__ import annotations

from pathlib import Path

from . import gates
from .config import load_project, stages
from .io import read_json, sha256_bytes, write_json
from .provenance import utc_now

FILE = Path(".hi") / "answers.json"


def _points(root: Path, stage: str) -> dict[str, dict]:
    from . import governance
    p = Path(root) / stages()[stage]["outputs"][0]
    ops = (read_json(p).get("open_points", []) if p.is_file() else []) + governance.open_points(root, stage)
    return {str(o["id"]): o for o in ops if isinstance(o, dict) and o.get("id")}


def _wording(point: dict) -> str:
    return sha256_bytes(str(point.get("text", "")).encode())


def recorded(root: Path) -> list[dict]:
    p = Path(root) / FILE
    return read_json(p).get("answers", []) if p.is_file() else []


def add(root: Path, stage: str, point_id: str, *, by: str, text: str) -> dict:
    if stage not in gates.trace.checked_stages(load_project(root), None):
        raise ValueError(f"{stage} is not a stage of this project")
    point = _points(root, stage).get(point_id)
    if point is None:
        raise ValueError(f"{stage} has no open point {point_id}")
    if point.get("returned_to"):
        raise ValueError(f"{point_id} is returned to {point['returned_to']}: that stage settles it, not a person")
    if not by.strip() or not text.strip():
        raise ValueError("an answer names who gives it (--by) and what it is (--text)")
    rec = {"stage": stage, "open_point": point_id, "question_sha256": _wording(point), "question": point.get("text", ""),
           "answer": text.strip(), "answered_by": by.strip(), "created_utc": utc_now()}
    kept = [a for a in recorded(root) if (a["stage"], a["open_point"], a["question_sha256"])
            != (stage, point_id, rec["question_sha256"])]
    write_json(Path(root) / FILE, {"schema": "forge-c-hi/answers@1", "answers": kept + [rec]})
    return rec


def current(root: Path, stage: str) -> list[dict]:
    """The answers to open points the stage still has in the wording that was answered."""
    ops = _points(root, stage)
    return [{k: a[k] for k in ("open_point", "answer", "answered_by")} for a in recorded(root)
            if a["stage"] == stage and a["open_point"] in ops and a["question_sha256"] == _wording(ops[a["open_point"]])]
