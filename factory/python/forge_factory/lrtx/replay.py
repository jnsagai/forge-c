"""LRTX-T016 (replay part): triage of every rejection the QWEN-TRIAL GPU runs recorded at SWE.1/SWE.2, against the
source requirements and tool behaviour, and the feature-010 mechanism that now catches or prevents it.

    python -m forge_factory.lrtx.replay --out <report.json>

A gate rejection is not automatically a model defect: each code carries its classification and the evidence for it.
Codes without a mapping are reported UNTRIAGED (the report then fails) - nothing is silently assumed fixed.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, utc_now

RUNS = REPO_ROOT / "evidence/v0.4/runs/QWEN-TRIAL/gpu"
# code -> (classification, evidence, mechanism, test that exercises the mechanism)
TRIAGE = {
    "CONTRACT_FIELD_NOT_IN_SWR": (
        "MODEL_CONTENT", "the effect names a field its requirement statement does not name (the contract rule is stated "
        "in the SWE.1 prompt)", "per-task validation: an effect field must be named by its statement; local repair",
        "test_lrtx_swe1.py::test_uncovered_field_is_repaired_locally_and_only_that_task_reruns"),
    "CONTRACT_SWR_NOT_COVERED": (
        "MODEL_OMISSION", "a requirement that sets/clears a field had no effect entry in a 20-30 requirement document",
        "per-task validation (one register per task) + coverage inventory of every key-section field",
        "test_lrtx_swe1.py::test_uncovered_field_is_repaired_locally_and_only_that_task_reruns"),
    "CONTRACT_MISSING": (
        "MODEL_OMISSION", "register_effects.json not written in the agent session", "deterministic assembly always "
        "writes the contract from validated effects", "test_lrtx_swe1.py::test_visit_assembles_work_products_the_"
        "unchanged_gate_freezes"),
    "MISSING_REQUIRED_OUTPUT": (
        "MODEL_OMISSION", "required output file absent", "deterministic assembly of every SWE.1 output",
        "test_lrtx_swe1.py::test_visit_assembles_work_products_the_unchanged_gate_freezes"),
    "SAFETY_SCOPE": (
        "MODEL_INSTRUCTION_FOLLOWING", "the prompt prescribes the PENDING-allocation statement for an ASIL scope; the "
        "model wrote the QM statement", "safety statement rendered from the manifest's allocation status",
        "test_lrtx_swe1.py::test_visit_assembles_work_products_the_unchanged_gate_freezes"),
    "SWE1:STARTUP_INVARIANT_ON_HOST_TEST": (
        "MODEL_INSTRUCTION_FOLLOWING", "the prompt maps 'While no ... after reset' requirements to the Robot suite",
        "verified_by validated per requirement; requirements_to_tests.csv rendered from it",
        "test_lrtx_swe1.py::test_visit_assembles_work_products_the_unchanged_gate_freezes"),
    "ARCH:SWR_NOT_ALLOCATED": (
        "MODEL_OMISSION", "budget/reset SWRs (component-level constraints) never allocated in the diagram note",
        "'Allocated:' note rendered with every SWR; component-level SWRs allocated to the SWC, not to new functions",
        "test_lrtx_swe2.py::test_component_level_requirement_needs_no_function_and_unallocated_swr_is_repaired"),
    "ARCH:INTERFACE_WITHOUT_ID": (
        "MODEL_FORMAT", "connections without IF-nn labels", "static view rendered with IF-01/IF-02",
        "test_lrtx_swe2.py::test_swe2_renders_an_architecture_the_unchanged_gate_freezes"),
    "ARCH:NO_INTERFACES": (
        "MODEL_FORMAT", "no labelled connection in the static view", "static view rendered",
        "test_lrtx_swe2.py::test_swe2_renders_an_architecture_the_unchanged_gate_freezes"),
    "ARCH:SWC_COUNT": (
        "MODEL_FORMAT", "SWC_LL missing or not stereotyped", "exactly one <<SWC>> SWC_LL rendered",
        "test_lrtx_swe2.py::test_swe2_renders_an_architecture_the_unchanged_gate_freezes"),
    "ARCH:LAYER_NOT_SEPARATE": (
        "MODEL_FORMAT", "an extra IWDG <<SWC>> element (the register block is hardware)", "register block rendered as "
        "a rectangle, never an SWC", "test_lrtx_swe2.py::test_swe2_renders_an_architecture_the_unchanged_gate_freezes"),
    "VIEWS:SYNTAX": (
        "MODEL_FORMAT", "PlantUML syntax errors", "views rendered from validated data; PlantUML check before reply",
        "test_lrtx_swe2.py::test_swe2_renders_an_architecture_the_unchanged_gate_freezes"),
    "CONTRACT_CALL_WITHOUT_CASE": (
        "MODEL_FORMAT", "api_calls keys not equal to the SWE.1 case ids", "calls validated against the SWE.1 cases; "
        "api_calls.json rendered from them", "test_lrtx_swe2.py::test_wrong_write_argument_and_compliance_claim_are_findings"),
    "CONTRACT_CASE_WITHOUT_CALL": (
        "MODEL_OMISSION", "SWE.1 cases without a call", "every case must have a call of an allocated function",
        "test_lrtx_swe2.py::test_wrong_write_argument_and_compliance_claim_are_findings"),
}


def code_of(issue: str) -> str:
    s = str(issue)
    for k in sorted(TRIAGE, key=len, reverse=True):
        if s.startswith(k):
            return k
    return re.split(r"[:( ]", s)[0]


def replay(runs: Path = RUNS) -> dict:
    seen: Counter = Counter()
    where: dict[str, set] = {}
    for f in sorted(runs.glob("*/gate-log.jsonl")):
        for line in f.read_text().splitlines():
            d = json.loads(line)
            if d.get("phase") not in ("SWE.1", "SWE.2") or d.get("result") not in ("REJECTED", "FAIL"):
                continue
            for i in d.get("issues") or []:
                c = code_of(i)
                seen[(d["phase"], c)] += 1
                where.setdefault(c, set()).add(f.parent.name)
    rows = []
    for (phase, c), n in sorted(seen.items()):
        t = TRIAGE.get(c)
        rows.append({"phase": phase, "code": c, "occurrences": n, "runs": sorted(where[c]),
                     **({"classification": t[0], "evidence": t[1], "mechanism": t[2], "test": t[3]} if t else
                        {"classification": "UNTRIAGED"})})
    untriaged = [r["code"] for r in rows if r["classification"] == "UNTRIAGED"]
    factory = [r["code"] for r in rows if r["classification"].startswith("FACTORY")]
    return {"schema": "forge-c/lrtx-replay/1", "generated_at": utc_now(), "source": str(runs.relative_to(REPO_ROOT)),
            "rows": rows, "untriaged": untriaged, "factory_defects": factory,
            "status": "PASS" if not untriaged else "FAIL",
            "note": "Replay of recorded rejections against the new mechanisms; it is not a fresh model trial. Whether "
                    "Qwen now produces passing work products is measured by fresh local runs (LRTX-T016 second part)."}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    rep = replay()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(pretty_json(rep))
    print(json.dumps({"status": rep["status"], "codes": len(rep["rows"]), "untriaged": rep["untriaged"]}))
    return 0 if rep["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
