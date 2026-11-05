"""Replay protected held-out registrations and explicit post-calibration learning transfers.

Review input never defines set membership. Missing or inconsistent registration
evidence fails closed; historical held-out results are never rewritten.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = "evidence/014-durable-local-autonomy/stepwise-inspector-20261026/"
F011 = "evidence/v0.4/runs/F011-T046/testset.json"


def _read(root: Path, name: str, schema: str) -> tuple[dict, str]:
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("DSP_SET_REGISTRY_INVALID: unsafe registration path")
    raw = path.read_bytes()
    doc = json.loads(raw)
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise ValueError("DSP_SET_REGISTRY_INVALID: registration schema")
    return doc, hashlib.sha256(raw).hexdigest()


def _members(rows) -> dict[str, str]:
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4096:
        raise ValueError("DSP_SET_REGISTRY_INVALID: empty or unbounded members")
    result = {}
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("workorder"), str)
                or not row["workorder"] or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("tree_sha256", "")))
                or row["workorder"] in result):
            raise ValueError("DSP_SET_REGISTRY_INVALID: member identity")
        result[row["workorder"]] = row["tree_sha256"]
    return result


def _completed(root: Path, name: str, expected: set[str]) -> None:
    doc, _ = _read(root, ROOT + name, "forge-c/feature014-calibration-runs/1")
    rows = doc.get("runs", [])
    if (not isinstance(rows, list) or len(rows) != len(expected)
            or {row.get("run") for row in rows} != expected
            or any(not any(line.startswith("exit=0 ") for line in row.get("log_lines", [])) for row in rows)):
        raise ValueError("DSP_SET_REGISTRY_INVALID: registered calibration incomplete")


def active_workorders(root: Path) -> set[str]:
    frozen, frozen_sha = _read(root, F011, "forge-c/f011-t046-testset/1")
    f011 = _members(frozen.get("selected"))
    split, split_sha = _read(root, ROOT + "f015-split.json", "forge-c/feature014-f015-split/1")
    f015 = _members(split.get("test_set_2"))
    subset, subset_sha = _read(root, ROOT + "calibration-subset.json", "forge-c/feature014-calibration-subset/1")
    if subset.get("source_testset") != {"path": F011, "sha256": frozen_sha}:
        raise ValueError("DSP_SET_REGISTRY_INVALID: calibration source binding")
    selected_subset = _members(subset.get("subset"))
    if any(f011.get(wo) != sha for wo, sha in selected_subset.items()):
        raise ValueError("DSP_SET_REGISTRY_INVALID: calibration member binding")
    learning2, _ = _read(root, ROOT + "learning-set-2.json", "forge-c/feature014-learning-set-2/1")
    if (learning2.get("source") != {"path": ROOT + "calibration-subset.json", "sha256": subset_sha}
            or _members(learning2.get("learning_set_2")) != selected_subset or subset.get("runs") != 3):
        raise ValueError("DSP_SET_REGISTRY_INVALID: learning transfer binding")
    _completed(root, "calibration-runs.json", {"calibration-s1", "calibration-s2", "calibration-s3"})
    learning4, _ = _read(root, ROOT + "learning-set-4.json", "forge-c/feature014-learning-set-4/1")
    source4 = learning4.get("source") or {}
    if (source4.get("path") != ROOT + "f015-split.json" or source4.get("sha256") != split_sha
            or _members(learning4.get("learning_set_4")) != f015):
        raise ValueError("DSP_SET_REGISTRY_INVALID: refreshed transfer binding")
    _completed(root, "calibration-t2-runs.json", {"calibration-t2-1", "calibration-t2-2", "calibration-t2-3"})
    return (set(f011) - set(selected_subset)) | (set(f015) - set(_members(learning4["learning_set_4"])))
