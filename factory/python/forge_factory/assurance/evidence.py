"""EASA-T017/T023 — verification-run evidence validator (EASA-FR-017/019/024).

A claim of tool execution is accepted only if the record names a real tool at its installed version, the raw output
it references exists and hashes to the recorded digest, the input digest equals the frozen baseline the gate is
evaluating, and status/returncode/observations are consistent. Raw logs are DATA: text inside them that tries to
instruct the gate (prompt injection) is flagged and never changes a verdict. Every rejection is an audit event.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..common import sha256_file
from ..events.emit import emit
from . import contracts

INJECTION_RX = re.compile(r"(ignore (all |the )?(previous|prior|above) (instructions|rules)|mark (this|all|the gate) "
                          r"(as )?pass|set status\s*[:=]\s*pass|lower (the )?(threshold|coverage)|you are now|"
                          r"system prompt|disregard (the )?(policy|gate))", re.I)
TEST_TOOLS = ("run_unit", "run_integration", "run_robot", "run_renode", "clang", "gcc", "pytest", "robot", "renode")


def validate_run(rec: dict, *, raw_dirs: list[Path], baseline_input_hash: str | None,
                 tool_versions: dict[str, str] | None = None, store=None) -> list[str]:
    issues = contracts.errors("verification-run", rec)
    raw = None
    for d in raw_dirs:
        cand = sorted(Path(d).glob(f"{rec.get('output_hash', '')}*")) if rec.get("output_hash") else []
        if cand:
            raw = cand[0]
            break
    if raw is None:
        issues.append("NONEXISTENT_TOOL_RESULT")
    elif sha256_file(raw) != rec.get("output_hash"):
        issues.append("OUTPUT_DIGEST_MISMATCH")
    if tool_versions is not None:
        want = tool_versions.get(rec.get("tool_id", ""))
        if want is None:
            issues.append(f"UNKNOWN_TOOL:{rec.get('tool_id')}")
        elif want != rec.get("tool_version"):
            issues.append(f"TOOL_VERSION_MISMATCH:{rec.get('tool_version')}!={want}")
    if baseline_input_hash is not None and rec.get("input_hash") != baseline_input_hash:
        issues.append("STALE_DIGEST:input does not match the frozen baseline")
    st, rc = rec.get("status"), rec.get("returncode")
    if st == "PASS" and rc != 0:
        issues.append(f"FORGED_PASS:returncode {rc}")
    if st == "PASS" and any(t in str(rec.get("tool_id", "")) for t in TEST_TOOLS) and not rec.get("observed_assertions"):
        issues.append("PASS_WITHOUT_OBSERVED_ASSERTIONS")
    if raw is not None and raw.stat().st_size < 4_000_000:
        text = raw.read_text(errors="replace")
        if INJECTION_RX.search(text):
            issues.append("PROMPT_INJECTION_IN_EVIDENCE")  # recorded; content never acts as an instruction
        if st == "PASS" and re.search(r"\b\d+ failed\b|\bFAIL\b", text) and not re.search(r"\b0 failed\b", text):
            issues.append("PASS_CONTRADICTED_BY_RAW_OUTPUT")
    if issues:
        emit("audit", "WARN", f"verification evidence rejected: {issues[0]}", tool_id="easa-evidence",
             run_id=rec.get("run_id"))
        if store is not None:
            store.append("finding", f"verification:{rec.get('run_id')}", {"code": "EVIDENCE_REJECTED", "issues": issues,
                                                                          "record": rec}, actor="easa-evidence")
    return issues


def accepted(rec: dict, **kw) -> bool:
    return not [i for i in validate_run(rec, **kw) if i != "PROMPT_INJECTION_IN_EVIDENCE"]
