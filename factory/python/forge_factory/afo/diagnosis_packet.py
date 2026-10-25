"""DA-002/003/004/032/033: complete evidence indexes and coherent obligation packets.

The old FailureBundle stays immutable and remains a routing summary. This index
retains full findings and primary hashes. A summary is never a completeness oracle.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..common import sha256_file, state_dir
from ..events.redact import redact_text
from .durable import Refused, canonical, digest, immutable_json

PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")
SCHEMA = "forge-c/diagnosis-packet/1"
MAX_FILE_BYTES = 4 * 1024 * 1024
TECHNIQUES = {
    "align-contract": "Repair a mismatch against the authoritative contract",
    "repair-implementation": "Repair implementation against a counterexample",
    "repair-traceability": "Repair missing or incorrect obligation-to-artifact links",
    "rebuild-specification": "Repair the owning specification from authoritative inputs",
    "qualified-alternative": "Use an already qualified and authorized local configuration",
}


def scoped_path(workspace: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative:
        raise Refused("EVIDENCE_PATH_INVALID")
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise Refused("EVIDENCE_PATH_ESCAPE")
    root = workspace.resolve()
    path = root / rel
    if root not in path.resolve().parents or any(
        p.is_symlink() for p in [path, *path.parents] if p != root and root in p.parents
    ):
        raise Refused("EVIDENCE_PATH_ESCAPE")
    return path


def source_phase(relative: str) -> str | None:
    return next((p for p in PHASES if p in Path(relative).parts), "SWE.3" if relative.startswith("software/") else None)


def seal(
    workspace: Path,
    bundle: dict,
    findings: list[dict],
    artifacts: list[dict],
    *,
    missing=(),
    dependencies: dict | None = None,
    prior_strategies=(),
    required_obligations=(),
) -> dict:
    phase = bundle["phase"]
    if phase not in PHASES:
        raise Refused("PACKET_PHASE_INVALID")
    inventory, missing = [], list(missing)
    for item in artifacts:
        rel = item["path"]
        p = scoped_path(workspace, rel)
        ph = item.get("phase") or source_phase(rel)
        if ph and PHASES.index(ph) > PHASES.index(phase):
            raise Refused("DOWNSTREAM_EVIDENCE_FORBIDDEN", rel)
        expected = item.get("sha256")
        if not p.is_file():
            missing.append(f"MISSING:{rel}")
            continue
        actual = sha256_file(p)
        if expected and expected != actual:
            missing.append(f"STALE:{rel}")
        if p.stat().st_size > MAX_FILE_BYTES:
            missing.append(f"OVERSIZED:{rel}")
        inventory.append(
            {
                "ref": f"artifact:{actual}:{digest(rel)[:16]}",
                "path": rel,
                "sha256": expected or actual,
                "bytes": p.stat().st_size,
                "phase": ph,
                "roles": ["afo-recovery-planner"],
            }
        )
    full, obligations = [], {}
    for i, finding in enumerate(findings):
        value = json.loads(redact_text(canonical(finding).decode())[0])
        fid = "finding:" + digest([finding.get("source_ref"), finding.get("id"), i, value])[:24]
        refs = re.findall(r"\b(?:SWR-\d{3}|USPEC-[A-Za-z0-9-]+|SWU-[A-Za-z0-9-]+)\b", canonical(value).decode())
        oid = value.get("obligation_id") or (refs[0] if refs else "OBL-" + digest(fid)[:20])
        full.append({**value, "ref": fid, "obligation_id": oid})
        unit = obligations.setdefault(
            oid, {"id": oid, "finding_refs": [], "evidence_refs": [], "dependencies": list((dependencies or {}).get(oid, []))}
        )
        unit["finding_refs"].append(fid)
        unit["evidence_refs"] = [x["ref"] for x in inventory]
    if not full:
        missing.append("NO_PRIMARY_FINDINGS")
    packet = {
        "schema": SCHEMA,
        "workspace": str(workspace.resolve()),
        "binding": {k: bundle[k] for k in ("bundle_id", "order_id", "attempt_id", "phase", "fingerprint")},
        "role": "afo-recovery-planner",
        "findings": full,
        "artifacts": inventory,
        "obligations": obligations,
        "required_obligations": sorted(set(required_obligations) | set(obligations)),
        "global_constraints": ["preserve_authoritative_inputs", "independent_verification", "all_native_gates"],
        "prior_strategies": list(prior_strategies),
        "techniques": dict(TECHNIQUES),
        "tests": {f"gate:{phase}:route=PASS": {"expected_result": "PASS", "phase": phase}},
        "complete": not missing,
        "missing": sorted(set(missing)),
        "truncated": False,
    }
    ref = digest(packet)
    immutable_json(state_dir() / "afo/diagnosis-packets" / f"{ref}.json", packet)
    return {"sha256": ref, "path": f"afo/diagnosis-packets/{ref}.json", "complete": packet["complete"]}


def build(workspace: Path, bundle: dict, *, prior_strategies=()) -> dict:
    phase = bundle["phase"]
    files, findings, missing = {}, [], []
    patterns = [
        ".forge-run/manifest.json",
        ".forge-run/gates/gate-log.jsonl",
        "verification/*.json*",
        "evidence/tool-results.jsonl",
    ]
    patterns += [f"workproducts/{p}/**/*" for p in PHASES[: PHASES.index(phase) + 1]]
    patterns += [f"inspection/{phase}/INS-*.json"]
    if PHASES.index(phase) >= 2:
        patterns += ["software/ll/**/*", "software/hal/**/*"]
    for pattern in patterns:
        for p in sorted(workspace.glob(pattern)):
            if not p.is_file() or p.suffix not in (".md", ".json", ".jsonl", ".c", ".h", ".txt", ".puml"):
                continue
            rel = p.relative_to(workspace).as_posix()
            files[rel] = {"path": rel}
    for rel, expected in bundle.get("input_digests", {}).items():
        ph = source_phase(rel)
        if ph and PHASES.index(ph) > PHASES.index(phase):
            continue
        files[rel] = {"path": rel, "sha256": expected}
    for rel in list(files):
        p = scoped_path(workspace, rel)
        if not p.is_file() or p.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            if rel.startswith(f"inspection/{phase}/"):
                doc = json.loads(p.read_text())
                findings.extend({**f, "source_ref": rel, "source_sha256": sha256_file(p)} for f in doc.get("findings", []))
                # The complete per-item findings are authoritative; the top-level display list may be capped.
                for item_id, item in (doc.get("items") or {}).items():
                    for index, detail in enumerate(item.get("findings") or []):
                        findings.append(
                            {"id": f"{item_id}:{index}", "detail": detail, "source_ref": rel, "source_sha256": sha256_file(p)}
                        )
            elif rel.endswith(".jsonl"):
                scoped_rows = []
                for line in p.read_text().splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    row_phase = row.get("phase") or (row.get("result") or {}).get("phase")
                    if row_phase not in PHASES or PHASES.index(row_phase) > PHASES.index(phase):
                        continue
                    scoped_rows.append(row)
                    result = row.get("result") or row.get("gate") or {}
                    if isinstance(result, dict):
                        for n, issue in enumerate(result.get("issues") or result.get("findings") or []):
                            findings.append(
                                {
                                    "id": f"{row.get('op', row.get('step', 'diagnostic'))}:{n}",
                                    "detail": issue,
                                    "source_ref": rel,
                                    "source_sha256": sha256_file(p),
                                }
                            )
                # Serve an immutable phase-safe primary view, retaining the original full-file hash as provenance.
                del files[rel]
                view = {"source_path": rel, "source_sha256": sha256_file(p), "maximum_phase": phase, "rows": scoped_rows}
                view_rel = f".forge-run/diagnosis-evidence/{phase}/{digest(view)}.json"
                immutable_json(workspace / view_rel, view)
                files[view_rel] = {"path": view_rel, "phase": phase}
                for f in findings:
                    if f.get("source_ref") == rel:
                        f.update(source_ref=view_rel, source_sha256=sha256_file(workspace / view_rel))
        except (ValueError, UnicodeError, TypeError):
            missing.append(f"UNREADABLE_PRIMARY:{rel}")
    req = workspace / "workproducts/SWE.1/software_requirements.md"
    required = re.findall(r"\bSWR-\d{3}\b", req.read_text()) if req.is_file() else []
    return seal(
        workspace,
        bundle,
        findings,
        list(files.values()),
        missing=missing,
        prior_strategies=prior_strategies,
        required_obligations=required,
    )


def load(ref: dict) -> dict:
    p = (state_dir() / ref["path"]).resolve()
    root = (state_dir() / "afo/diagnosis-packets").resolve()
    if root not in p.parents or p.is_symlink() or not p.is_file():
        raise Refused("PACKET_REFERENCE_INVALID")
    value = json.loads(p.read_text())
    if digest(value) != ref["sha256"] or value.get("schema") != SCHEMA:
        raise Refused("PACKET_HASH_MISMATCH")
    return value


def evidence(packet: dict, ref: str, *, role: str, phase: str | None) -> str:
    if role != packet["role"] or phase not in (None, packet["binding"]["phase"]):
        raise Refused("EVIDENCE_ROLE_PHASE_DENIED")
    finding = next((f for f in packet["findings"] if f["ref"] == ref), None)
    if finding:
        return canonical(finding).decode()
    art = next((a for a in packet["artifacts"] if a["ref"] == ref), None)
    if art is None or role not in art["roles"]:
        raise Refused("EVIDENCE_REFERENCE_NOT_IN_CASE")
    p = scoped_path(Path(packet["workspace"]), art["path"])
    if not p.is_file() or p.stat().st_size > MAX_FILE_BYTES or sha256_file(p) != art["sha256"]:
        raise Refused("EVIDENCE_MISSING_OR_CHANGED", art["path"])
    return redact_text(p.read_text(encoding="utf-8"))[0]


def measure_request(body: dict, counter=None) -> dict:
    raw = canonical(body)
    # Conservative byte bound is explicitly distinct from an installed tokenizer/native measurement.
    n = counter(raw) if counter else len(raw) + 128
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise Refused("INVALID_TOKEN_MEASUREMENT")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "serialized_bytes": len(raw),
        "input_tokens": n,
        "method": "qualified_tokenizer" if counter else "utf8_byte_upper_bound",
        "native_measured": counter is not None,
    }


def partition(
    packet: dict, *, max_bytes: int, instructions: str = "", skill: str = "", tool_schema: dict | None = None
) -> list[dict]:
    """Topological coherent obligations; dependency/global inventories are never silently sliced."""
    units, pending, done = [], dict(packet["obligations"]), set()
    while pending:
        ready = [k for k, o in pending.items() if set(o["dependencies"]) <= done]
        if not ready:
            raise Refused("OBLIGATION_DEPENDENCY_MISSING_OR_CYCLIC")
        for oid in sorted(ready):
            obligation = pending.pop(oid)
            view = {
                "binding": packet["binding"],
                "obligation": obligation,
                "findings": [f for f in packet["findings"] if f["ref"] in obligation["finding_refs"]],
                "primary_evidence": packet["artifacts"],
                "global_constraints": packet["global_constraints"],
                "required_obligations": packet["required_obligations"],
                "techniques": packet["techniques"],
                "tests": packet["tests"],
                "prior_strategies": packet["prior_strategies"],
                "complete": packet["complete"],
                "missing": packet["missing"],
            }
            body = {"instructions": instructions, "skill": skill, "tool_schema": tool_schema or {}, "case": view}
            if len(canonical(body)) > max_bytes:
                raise Refused("COHERENT_OBLIGATION_EXCEEDS_CONTEXT", oid)
            units.append(
                {"obligation_id": oid, "packet_sha256": digest(packet), "body": body, "accounting": measure_request(body)}
            )
            done.add(oid)
    if done != set(packet["obligations"]):
        raise Refused("OBLIGATION_COVERAGE_INCOMPLETE")
    return units


def checkpoint(packet: dict, completed: dict[str, dict]) -> dict:
    for oid, receipt in completed.items():
        if oid not in packet["obligations"] or receipt.get("packet_sha256") != digest(packet):
            raise Refused("CHECKPOINT_REFERENCE_MISMATCH")
    value = {
        "schema": "forge-c/obligation-checkpoint/1",
        "packet_sha256": digest(packet),
        "completed": completed,
        "remaining": sorted(set(packet["obligations"]) - set(completed)),
    }
    return {**value, "sha256": digest(value)}
