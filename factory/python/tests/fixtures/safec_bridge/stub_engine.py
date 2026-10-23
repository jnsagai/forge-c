#!/usr/bin/python3
"""Test double of a SafeC bridge engine (F011-T010). Public, synthetic, no SafeC code.

Behaviour comes from `mode.json` next to this file ({"mode": ..., "marker": <path>}). The default mode is the
honest one: every operation UNSUPPORTED, with consistent evidence. Every other mode reproduces one way an engine
can be wrong, slow, hostile or broken. The client must never turn any of those into an admissible PASS.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONF = json.loads((HERE / "mode.json").read_text()) if (HERE / "mode.json").is_file() else {}
MODE = CONF.get("mode", "unsupported")
COMMIT = CONF.get("commit", "c" * 40)
SELF = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def engine():
    return {"source_commit_sha": "d" * 40 if MODE == "wrong_engine" else COMMIT, "binary_sha256": SELF,
            "semantic_profile": "register-io-0.1"}


def mark():
    if CONF.get("marker"):
        with open(CONF["marker"], "a") as f:
            f.write(f"{sys.argv[1:2]} {sorted(os.environ)}\n")


def identity():
    profiles = [] if MODE == "identity_no_profile" else ["register-io-0.1"]
    commit = "e" * 40 if MODE == "identity_wrong_commit" else COMMIT
    doc = {"schema": "forge-c/safec-bridge-identity/1",
           "engine": {"source_commit_sha": commit, "binary_sha256": SELF, "semantic_profiles": profiles},
           "protocol": {"request": "forge-c/safec-bridge-request/1", "result": "forge-c/safec-bridge-result/1"},
           "operations": {"validate_intents": "UNSUPPORTED", "derive_contracts": "UNSUPPORTED",
                          "derive_tests": "UNSUPPORTED", "verify_candidate": "UNSUPPORTED",
                          "probe_capabilities": "UNSUPPORTED"}}
    print(json.dumps(doc))
    return 0


def run(args):
    a = dict(zip(args[::2], args[1::2], strict=True))
    raw = Path(a["--request"]).read_bytes()
    req = json.loads(raw)
    res_p, ev = Path(a["--result"]), Path(a["--evidence-dir"])
    if MODE == "sleep":
        time.sleep(60)
    if MODE == "spawn_child":
        pid_file = HERE / "child.pid"
        child = subprocess.Popen(["/bin/sleep", "60"])
        pid_file.write_text(str(child.pid))
        time.sleep(60)
    if MODE == "crash":
        os.abort()
    if MODE == "huge_stdout":
        sys.stdout.write("x" * (2 * 1024 * 1024))
    sys.stderr.write("engine diagnostic: PRIVATE-DETAIL-0001\n")
    if MODE == "no_result":
        return 0
    status, findings, arts = "UNSUPPORTED", [{
        "finding_id": "FND-001", "check_id": "OPERATION_SUPPORTED", "target_id": req["operation"],
        "source_fact_ids": [], "message": "operation not implemented by this engine", "severity": "major"}], []
    ev.mkdir(parents=True, exist_ok=True)
    if MODE.startswith(("pass", "forged_pass", "evidence_disagrees", "missing_artifact", "artifact_digest",
                        "contradictory_pass")):
        status, findings = "PASS", []
        (ev / "artifacts").mkdir(exist_ok=True)
        body = b'{"contract":"synthetic"}'
        if MODE != "missing_artifact":
            (ev / "artifacts" / "C-001").write_bytes(body)
        digest = hashlib.sha256(b"other" if MODE == "artifact_digest_mismatch" else body).hexdigest()
        arts = [{"artifact_id": "C-001", "sha256": digest, "kind": "validated_contract"}]
        if MODE == "contradictory_pass":
            findings = [{"finding_id": "FND-9", "check_id": "X", "target_id": "I-001", "source_fact_ids": [],
                         "message": "critical problem", "severity": "critical"}]
    input_sha = hashlib.sha256(raw).hexdigest()
    if MODE == "wrong_input_digest":
        input_sha = "0" * 64
    evidence = {"schema": "forge-c/safec-bridge-evidence/1", "request_id": req["request_id"],
                "input_sha256": input_sha, "engine": engine(), "operation": req["operation"],
                "status": "FAIL" if MODE == "evidence_disagrees" else status, "findings": findings,
                "output_artifacts": arts}
    ev_bytes = json.dumps(evidence, sort_keys=True).encode()
    if MODE != "missing_evidence":
        (ev / "evidence.json").write_bytes(ev_bytes + (b" " if MODE == "tampered_evidence" else b""))
    result = {"schema": "forge-c/safec-bridge-result/1",
              "request_id": "OTHER" if MODE == "wrong_request_id" else req["request_id"],
              "input_sha256": input_sha, "engine": engine(), "status": status, "findings": findings,
              "evidence_sha256": hashlib.sha256(ev_bytes).hexdigest(), "output_artifacts": arts}
    if MODE == "unknown_field":
        result["approved_for_release"] = True
    text = json.dumps(result, sort_keys=True).encode()
    if MODE == "duplicate_keys":
        text = text[:-1] + b',"status":"PASS"}'
    if MODE == "invalid_utf8":
        text = text.replace(b"not implemented", b"not \xff implemented")
    if MODE == "oversized":
        result["limits"] = ["y" * 1000] * 5000
        text = json.dumps(result).encode()
    res_p.write_bytes(text)
    return 1 if MODE == "forged_pass_exit1" else 0


def main():
    mark()
    if sys.argv[1:2] == ["identity"]:
        return identity()
    if sys.argv[1:2] == ["run"]:
        return run(sys.argv[2:])
    return 2


if __name__ == "__main__":
    sys.exit(main())
