#!/usr/bin/env python3
"""T071: build the seeded-defect corpus from the accepted run 5 system requirements.

    python3 build_corpus.py      # writes requirements.json and answer-key.json next to this file

Every defect is a small, realistic edit of an accepted requirement, an added requirement, or a removed one. Each edit
asserts the text it replaces, so the corpus cannot silently drift from its base. The answer key is never shown to an
inspector: the evaluation copies only requirements.json into the inspector's working directory.

`gate` in the key says whether a deterministic gate can see the defect at all; the others need the inspector's
judgement. A set-level defect (target SET) lists `match_ids`: a finding counts for it only if it cites one of them.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1] / "evidence/us1-p1-demo/run5-pass4-accepted/hi/sys-req/requirements.json"


def main() -> None:
    base = json.loads(BASE.read_text())
    doc = copy.deepcopy(base)
    items = {i["id"]: i for i in doc["items"]}
    key: list[dict] = []

    def edit(did, iid, cls, what, old, new, gate=False, field="text"):
        it = items[iid]
        assert old in str(it[field]), (did, iid, old)
        it[field] = it[field].replace(old, new) if isinstance(it[field], str) else new
        key.append({"id": did, "target_id": iid, "class": cls, "description": what, "gate": gate})

    def add(did, item, cls, what, after, gate=False):
        doc["items"].insert(next(n for n, i in enumerate(doc["items"]) if i["id"] == after) + 1, item)
        items[item["id"]] = item
        key.append({"id": did, "target_id": item["id"], "class": cls, "description": what, "gate": gate})

    def drop(did, ids, cls, what, match_ids, gate=False):
        doc["items"] = [i for i in doc["items"] if i["id"] not in ids]
        key.append({"id": did, "target_id": "SET", "class": cls, "description": what, "gate": gate,
                    "removed": ids, "match_ids": match_ids})

    def sys(iid, text, sources, method="test"):
        return {"id": iid, "level": "system", "text": text, "sources": [{"kind": "upstream", "id": s} for s in sources],
                "derived": False, "verification_method": method, "status": "proposed"}

    # ambiguity (IQ-03)
    edit("D01", "SYS-WDG-001", "IQ-03", "timeout replaced by 'a suitable timeout' (CON-SUP-106: 100 ms)",
         "with a timeout of 100 ms", "with a suitable timeout", gate=True)
    edit("D02", "SYS-MEM-007", "IQ-03", "budget replaced by 'a small share' (CON-SUP-108: 0.5 ms)",
         "to 0.5 ms per control cycle", "to a small share of each control cycle")
    edit("D03", "SYS-DIAG-013", "IQ-03", "line length replaced by TBD (CON-SUP-138: 32)",
         "at most 32 ASCII characters", "at most TBD ASCII characters", gate=True)
    # wrong value against the inputs (IQ-02)
    edit("D04", "SYS-DIAG-001", "IQ-02", "baud rate 9600 contradicts CON-SUP-007 (115200)", "115200 baud", "9600 baud")
    edit("D05", "SYS-PERF-001", "IQ-02", "25 % contradicts STK-SUP-014 (10 %)", "to 10 % of", "to 25 % of")
    edit("D06", "SYS-WDG-002", "IQ-02", "window 2..40 ms contradicts CON-SUP-106 (6..12 ms)",
         "earlier than 6 ms or later than 12 ms", "earlier than 2 ms or later than 40 ms")
    # incomplete (IQ-04)
    edit("D07", "SYS-SAFE-003", "IQ-04", "the status signal is no longer held low at start-up",
         "hold both control outputs and the status signal low", "hold both control outputs low")
    # non-atomic (IQ-05)
    edit("D08", "SYS-RST-002", "IQ-05", "a second obligation joined with 'and store'",
         "in a start-up message on the diagnostic serial line.",
         "in a start-up message on the diagnostic serial line and store it in the fault history.", gate=True)
    # unverifiable (IQ-06)
    edit("D09", "SYS-SAFE-009", "IQ-06", "replaced by an unverifiable 'never lost under any circumstances'",
         "The system shall keep the latch of the safe state across software resets and watchdog resets.",
         "The system shall ensure that the latched safe state is never lost under any circumstances.")
    edit("D10", "SYS-SAFE-002", "IQ-06", "a 49 ms timing requirement verified by inspection only",
         "test", "inspection", field="verification_method")
    # infeasible (IQ-07)
    edit("D11", "SYS-MEM-006", "IQ-07", "1 MiB at 1 KiB per 10 ms cycle cannot finish in 50 ms (CON-SUP-108: 11 s)",
         "within 11 s", "within 50 ms")
    # design detail (IQ-08)
    edit("D12", "SYS-SAFE-017", "IQ-08", "implementation detail: a uint8_t array indexed by fault code",
         "keep a separate count of detections for each fault code,",
         "keep a separate count of detections for each fault code in a uint8_t array indexed by the fault code,")
    edit("D13", "SYS-DIAG-012", "IQ-08", "implementation detail: ring buffer with head and tail pointers",
         "the system shall discard the oldest held fault report and hold the new one,",
         "the system shall overwrite the oldest entry of its ring buffer by advancing the head and tail pointers,")
    # inconsistent with other items (IQ-09)
    edit("D14", "SYS-SAFE-007", "IQ-09", "latch at five detections contradicts SYS-SAFE-012 and SYS-WDG-007 (third)",
         "reaches three", "reaches five")
    # wrong or dangling source (IQ-12)
    srcs = items["SYS-RST-001"]["sources"]
    assert {"kind": "upstream", "id": "STK-SUP-011"} in srcs
    items["SYS-RST-001"]["sources"] = [dict(s, id="STK-SUP-014") if s.get("id") == "STK-SUP-011" else s for s in srcs]
    key.append({"id": "D15", "target_id": "SYS-RST-001", "class": "IQ-12", "gate": False,
                "description": "source STK-SUP-011 (reset cause) replaced by the unrelated STK-SUP-014 (CPU budget)"})
    items["SYS-TEST-002"]["sources"].append({"kind": "upstream", "id": "STK-SUP-016"})
    key.append({"id": "D16", "target_id": "SYS-TEST-002", "class": "IQ-12", "gate": True,
                "description": "cites STK-SUP-016, which does not exist"})
    # missing unit (IQ-11)
    edit("D17", "SYS-DIAG-003", "IQ-11", "'within 10' without a unit", "within 10 ms of the detection",
         "within 10 of the detection", gate=True)
    # unnecessary, invented (IQ-01)
    add("D18", sys("SYS-DIAG-019", "The system shall encrypt every fault report with AES-128 before it transmits it "
                   "on the diagnostic serial line.", ["STK-SUP-012"]),
        "IQ-01", "invented obligation: no need or constraint asks for encryption", after="SYS-DIAG-018")
    # wrong level: software detail at system level (IQ-10)
    add("D19", sys("SYS-SUP-011", "The function supervisor_cycle() shall be called from the SysTick interrupt handler "
                   "every 10 ms.", ["STK-SUP-001"]),
        "IQ-10", "software-design detail written as a system requirement", after="SYS-SUP-010")
    # a need left uncovered (SQ-01)
    drop("D20", ["SYS-SUP-008", "SYS-SUP-009"], "SQ-01", "program-flow supervision removed: STK-SUP-003 uncovered",
         ["STK-SUP-003"], gate=True)
    # a missing fault reaction (SQ-02)
    drop("D21", ["SYS-MEM-004"], "SQ-02", "no reaction to a configuration CRC mismatch (fault code 6) any more",
         ["fault code 6", "configuration integrity", "configuration CRC", "CRC of the configuration",
          "configuration data block"])
    # a missing invalid-input scenario (SQ-02)
    drop("D22", ["SYS-DIAG-014"], "SQ-02", "no answer to an over-long service request line any more",
         ["SYS-DIAG-014", "longer than 32", "over-long", "overlong", "too long"])
    # a contradictory pair (SQ-05)
    add("D23", sys("SYS-SAFE-030", "When a configuration fault is detected at start-up, the system shall request a "
                   "software reset within 100 ms.", ["STK-SUP-010", "CON-SUP-115"]),
        "SQ-05", "contradicts SYS-SAFE-010 and SYS-SAFE-014 (latched, no software reset)", after="SYS-SAFE-014")
    key[-1].update(target_id="SET", match_ids=["SYS-SAFE-030"])

    doc["baseline_id"] = "SEEDED-1"
    doc["status"] = "draft"
    out = HERE / "requirements.json"
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    classes = sorted({d["class"] for d in key})
    (HERE / "answer-key.json").write_text(json.dumps({
        "schema": "forge-c-hi/seeded-key@1",
        "base": {"path": BASE.relative_to(HERE.parents[1]).as_posix(),
                 "sha256": hashlib.sha256(BASE.read_bytes()).hexdigest()},
        "corpus_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "total": len(key), "classes": classes, "gate_visible": sum(1 for d in key if d["gate"]),
        "defects": key}, indent=1) + "\n")
    print(json.dumps({"defects": len(key), "classes": len(classes), "gate_visible": sum(1 for d in key if d["gate"]),
                      "items": len(doc["items"])}))


if __name__ == "__main__":
    main()
