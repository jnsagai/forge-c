"""Feature 020 T036 (FR-029, SC-010): the way-of-working proposal cites a decision-log entry for every rule."""
from __future__ import annotations

import json
import re

import pytest
import yaml

from forge_factory.benchmark import proposal as W

LOG = """# Decision log

| # | Date | Rule | Decided by | Rationale | Evidence | Status |
|---|---|---|---|---|---|---|
| D1 | 2026-11-12 | Functional SWE.1 | owner | level | spec | adopted |
| D2 | 2026-11-12 | Template attributes | factory | template | test_x | adopted (pilot) |
| D3 | 2026-11-12 | Something tried | factory | why | run | rejected |
| D4 | 2026-11-12 | Undecided | factory | why | pending | open |
"""
CLASSES = {"schema": W.CLASSES_SCHEMA, "rules": [
    {"id": "D1", "class": "default", "rule": "SWE.1 states functional behaviour", "ladder_need": "re-run SWE.1"},
    {"id": "D2", "class": "per_order", "rule": "the template is chosen per order"},
]}
COMPARISON = {"schema": "forge-c/benchmark-comparison/1", "rows": [
    {"metric": "requirement_count", "category": "", "pilot": 70, "benchmark": 56},
    {"metric": "by_type", "category": "functional", "pilot": 60, "benchmark": 50}], "not_delivered": ["loopback"]}


def _files(tmp_path, classes=None, log=LOG):
    (tmp_path / "log.md").write_text(log)
    (tmp_path / "classes.yaml").write_text(yaml.safe_dump(classes or CLASSES))
    (tmp_path / "m").mkdir()
    (tmp_path / "m/comparison.json").write_text(json.dumps(COMPARISON))
    return ["--log", str(tmp_path / "log.md"), "--classes", str(tmp_path / "classes.yaml"), "--metrics",
            str(tmp_path / "m"), "--out", str(tmp_path / "proposal.md")]


def test_parse_log_reads_every_entry(tmp_path):
    entries = W.parse_log(LOG)
    assert list(entries) == ["D1", "D2", "D3", "D4"]
    assert entries["D3"]["status"] == "rejected" and entries["D2"]["decided_by"] == "factory"


def test_every_rule_cites_an_existing_entry(tmp_path):
    assert W.main(_files(tmp_path)) == 0
    md = (tmp_path / "proposal.md").read_text()
    sec = md.split("## Entries not proposed")[0]
    bullets = [l for l in sec.splitlines() if l.startswith("- ") and "(no entry)" not in l]
    assert bullets and all(re.search(r"\(D\d+\)$", l) for l in bullets), bullets
    assert {re.search(r"\((D\d+)\)$", l).group(1) for l in bullets} <= set(W.parse_log(LOG))
    assert "## Default rules" in md and "## Per-order settings" in md and "## What the ladder drivers would need" in md
    assert "SWE.1 states functional behaviour (D1)" in md and "re-run SWE.1 (D1)" in md
    assert "| requirement_count |  | 70 | 56 |" in md
    assert "- D3: rejected" in md and "- D4: open" in md  # listed, never proposed as rules


@pytest.mark.parametrize("case,code", [
    ("unclassified", "PROPOSAL_UNCLASSIFIED: D2"),
    ("unknown", "PROPOSAL_UNKNOWN_ENTRY: D9"),
    ("rejected", "PROPOSAL_NOT_ADOPTED: D3"),
    ("no_metrics", "PROPOSAL_METRICS_MISSING"),
])
def test_refusals(tmp_path, case, code, capsys):
    rules = list(CLASSES["rules"])
    if case == "unclassified":
        rules = rules[:1]
    elif case == "unknown":
        rules.append({"id": "D9", "class": "default", "rule": "x"})
    elif case == "rejected":
        rules.append({"id": "D3", "class": "default", "rule": "x"})
    args = _files(tmp_path, {"schema": W.CLASSES_SCHEMA, "rules": rules})
    if case == "no_metrics":
        (tmp_path / "m/comparison.json").unlink()
    assert W.main(args) == 2
    assert code in capsys.readouterr().err
    assert not (tmp_path / "proposal.md").exists()
