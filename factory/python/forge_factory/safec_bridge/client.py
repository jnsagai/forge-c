"""F011-T007 / F011-T009: bounded invocation of a pinned local SafeC engine and revalidation of what it reports.

    engine identity                                           -> identity handshake (IDENTITY_SCHEMA)
    engine run --request R --result O --evidence-dir E        -> one result, its evidence and artifacts

Order of checks: everything that identifies the engine is checked before any reported result is interpreted.
1. The engine file exists and its SHA-256 equals the pin. Otherwise nothing is executed (REFUSED).
2. The handshake names the pinned source commit, the same binary digest, the requested semantic profile and the frozen
   protocol versions.
3. One run of the engine:
   - argument vector only, no shell;
   - empty environment except PATH/LANG;
   - its own session (the whole process group is killed on timeout or cancellation);
   - CPU, address-space, file-size and open-file limits;
   - bounded stdout/stderr.
4. The result is parsed strictly. Then it must echo the request id, the digest of the exact request bytes and the
   pinned engine identity.
5. The evidence file must hash to `evidence_sha256` and state the same request, input, engine, status, findings and
   artifacts. Every artifact must exist with its stated digest.

Only a PASS that survives all of this is `admissible`, and then only for the operation and intents requested.
Every other outcome carries the issues that block it. A non-zero engine exit is an ERROR whatever the result file
says. Nothing here decides a phase, a work order or a release (ADR-0015).
"""
from __future__ import annotations

import json
import os
import resource
import signal
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..common import pretty_json
from . import contracts as C

EVIDENCE_SCHEMA = "forge-c/safec-bridge-evidence/1"
ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
STREAM_LIMIT = 1024 * 1024


@dataclass(frozen=True)
class EnginePin:
    binary: Path
    binary_sha256: str
    source_commit_sha: str
    semantic_profile: str = "register-io-0.1"

    def expected(self) -> dict:
        return {"source_commit_sha": self.source_commit_sha, "binary_sha256": self.binary_sha256,
                "semantic_profile": self.semantic_profile}


@dataclass(frozen=True)
class Limits:
    timeout_s: float = 60.0
    cpu_s: int = 60
    address_space_bytes: int = 2 * 1024 ** 3
    file_size_bytes: int = 64 * 1024 ** 2
    open_files: int = 256


@dataclass
class Outcome:
    status: str  # one of contracts.STATUSES
    admissible: bool = False
    refused: bool = False  # nothing was executed
    issues: list[str] = field(default_factory=list)
    request_id: str | None = None
    input_sha256: str | None = None
    result: dict | None = None
    exit_code: int | None = None
    measured: dict = field(default_factory=dict)

    def record(self) -> dict:
        return asdict(self)


def _limits(lim: Limits):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (lim.cpu_s, lim.cpu_s + 1))
        resource.setrlimit(resource.RLIMIT_AS, (lim.address_space_bytes, lim.address_space_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (lim.file_size_bytes, lim.file_size_bytes))
        resource.setrlimit(resource.RLIMIT_NOFILE, (lim.open_files, lim.open_files))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


def _execute(argv: list[str], cwd: Path, lim: Limits, cancel: threading.Event | None) -> dict:
    """One bounded engine process; the caller reads stdout/stderr from files whose size is checked."""
    out, err = cwd / "engine.stdout", cwd / "engine.stderr"
    t0 = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    with out.open("wb") as so, err.open("wb") as se:
        p = subprocess.Popen(argv, cwd=cwd, env=ENV, stdin=subprocess.DEVNULL, stdout=so, stderr=se,
                             start_new_session=True, preexec_fn=_limits(lim), close_fds=True)
        reason = None
        while p.poll() is None:
            if time.monotonic() - t0 > lim.timeout_s:
                reason = "TIMEOUT"
            elif cancel is not None and cancel.is_set():
                reason = "CANCELLED"
            if reason:
                try:
                    os.killpg(p.pid, signal.SIGKILL)  # the engine and anything it started
                except ProcessLookupError:
                    pass
                p.wait()
                break
            time.sleep(0.02)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"exit_code": p.returncode, "stopped": reason, "wall_ms": int((time.monotonic() - t0) * 1000),
            "cpu_ms": int(((after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)) * 1000),
            "stdout_bytes": out.stat().st_size, "stderr_bytes": err.stat().st_size,
            "stdout_sha256": C.sha256_path(out), "stderr_sha256": C.sha256_path(err)}


def verify_engine_file(pin: EnginePin) -> list[str]:
    b = Path(pin.binary)
    if not b.is_file():
        return [f"ENGINE_MISSING:{b.name}"]
    if not os.access(b, os.X_OK):
        return [f"ENGINE_NOT_EXECUTABLE:{b.name}"]
    actual = C.sha256_path(b)
    return [] if actual == pin.binary_sha256 else [f"ENGINE_DIGEST_MISMATCH:{actual}"]


def handshake(pin: EnginePin, workdir: Path, lim: Limits | None = None) -> tuple[dict | None, list[str]]:
    workdir.mkdir(parents=True, exist_ok=True)
    run = _execute([str(pin.binary), "identity"], workdir, lim or Limits(timeout_s=10, cpu_s=10), None)
    if run["stopped"] or run["exit_code"] != 0:
        return None, [f"IDENTITY_FAILED:{run['stopped'] or run['exit_code']}"]
    try:
        ident = C.parse_identity((workdir / "engine.stdout").read_bytes())
    except C.ContractError as exc:
        return None, [f"IDENTITY_{exc.code}"]
    eng, issues = ident["engine"], []
    if eng["source_commit_sha"] != pin.source_commit_sha:
        issues.append(f"ENGINE_SOURCE_COMMIT_MISMATCH:{eng['source_commit_sha']}")
    if eng["binary_sha256"] != pin.binary_sha256:
        issues.append("ENGINE_SELF_DIGEST_MISMATCH")
    if pin.semantic_profile not in eng["semantic_profiles"]:
        issues.append(f"PROFILE_NOT_OFFERED:{pin.semantic_profile}")
    return ident, issues


def _revalidate(result: dict, request: dict, input_sha: str, pin: EnginePin, evdir: Path) -> list[str]:
    issues = []
    if result["request_id"] != request["request_id"]:
        issues.append("RESULT_REQUEST_ID_MISMATCH")
    if result["input_sha256"] != input_sha:
        issues.append("RESULT_INPUT_DIGEST_MISMATCH")
    if result["engine"] != pin.expected():
        issues.append("RESULT_ENGINE_MISMATCH")
    ev = evdir / "evidence.json"
    if not ev.is_file():
        return issues + ["EVIDENCE_MISSING"]
    if C.sha256_path(ev) != result["evidence_sha256"]:
        return issues + ["EVIDENCE_DIGEST_MISMATCH"]
    try:
        doc = C.strict_loads(ev.read_bytes(), C.MAX_RESULT_BYTES)
    except C.ContractError as exc:
        return issues + [f"EVIDENCE_{exc.code}"]
    want = {"schema": EVIDENCE_SCHEMA, "request_id": result["request_id"], "input_sha256": input_sha,
            "engine": pin.expected(), "operation": request["operation"], "status": result["status"],
            "findings": result["findings"], "output_artifacts": result["output_artifacts"]}
    issues += [f"EVIDENCE_{k.upper()}_MISMATCH" for k, v in want.items() if doc.get(k) != v]
    for art in result["output_artifacts"]:
        p = evdir / "artifacts" / art["artifact_id"]
        if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(evdir.resolve()):
            issues.append(f"ARTIFACT_MISSING:{art['artifact_id']}")
        elif C.sha256_path(p) != art["sha256"]:
            issues.append(f"ARTIFACT_DIGEST_MISMATCH:{art['artifact_id']}")
    return issues


def invoke(pin: EnginePin, request: dict, raw: bytes, workdir: Path, lim: Limits | None = None,
           cancel: threading.Event | None = None, domain: bytes | None = None) -> Outcome:
    """Run one already-built request (contracts.build_request) and return the normalized outcome. `domain` is the
    exact bytes of the register-io domain document the request is bound to (binding.source_manifest_sha256)."""
    lim = lim or Limits()
    input_sha = C.sha256_bytes(raw)
    base = {"request_id": request.get("request_id"), "input_sha256": input_sha}
    if request.get("expected_engine") != pin.expected():
        return Outcome("STALE", refused=True, issues=["REQUEST_ENGINE_NOT_PIN"], **base)
    if domain is not None and C.sha256_bytes(domain) != request["binding"]["source_manifest_sha256"]:
        return Outcome("STALE", refused=True, issues=["DOMAIN_NOT_BOUND_TO_REQUEST"], **base)
    issues = verify_engine_file(pin)
    if issues:
        return Outcome("STALE" if issues[0].startswith("ENGINE_DIGEST") else "ERROR", refused=True, issues=issues,
                       **base)
    workdir.mkdir(parents=True, exist_ok=False)
    _ident, issues = handshake(pin, workdir / "identity")
    if issues:
        return Outcome("STALE", refused=True, issues=issues, **base)
    req_p, res_p, evdir = workdir / "request.json", workdir / "result.json", workdir / "evidence"
    req_p.write_bytes(raw)
    argv = [str(pin.binary), "run", "--request", str(req_p), "--result", str(res_p), "--evidence-dir", str(evdir)]
    if domain is not None:
        (workdir / "domain.json").write_bytes(domain)
        argv += ["--domain", str(workdir / "domain.json")]
    run = _execute(argv, workdir, lim, cancel)
    measured = {k: run[k] for k in ("wall_ms", "cpu_ms", "stdout_sha256", "stderr_sha256")}
    if run["stopped"]:
        return Outcome("ERROR", issues=[run["stopped"]], exit_code=run["exit_code"], measured=measured, **base)
    issues = [f"STREAM_OVERSIZED:{k}" for k in ("stdout_bytes", "stderr_bytes") if run[k] > STREAM_LIMIT]
    if run["exit_code"] != 0:
        issues.append(f"ENGINE_EXIT:{run['exit_code']}")
    if not res_p.is_file():
        return Outcome("ERROR", issues=issues + ["RESULT_MISSING"], exit_code=run["exit_code"], measured=measured,
                       **base)
    try:
        result = C.parse_result(res_p.read_bytes())
    except C.ContractError as exc:
        return Outcome("ERROR", issues=issues + [f"RESULT_{exc.code}"], exit_code=run["exit_code"],
                       measured=measured, **base)
    issues += _revalidate(result, request, input_sha, pin, evdir)
    status = result["status"]
    if any(i.startswith(("RESULT_INPUT", "RESULT_ENGINE")) for i in issues):
        status = "STALE"
    elif issues:
        status = "ERROR"
    return Outcome(status, admissible=status == "PASS" and not issues, issues=issues, result=result,
                   exit_code=run["exit_code"], measured=measured, **base)


class ResultCache:
    """F011-AT-010: a stored outcome is reused only for the same request bytes and the same pinned engine, and only
    while its evidence directory still hashes as recorded. Any change of request, source manifest, policy or engine
    is a different key; changed evidence is a miss, never a hit."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def key(self, pin: EnginePin, raw: bytes) -> str:
        return C.sha256_bytes(C.canonical_bytes(pin.expected()) + b"\n" + raw)

    def put(self, pin: EnginePin, raw: bytes, outcome: Outcome, workdir: Path) -> None:
        ev = workdir / "evidence"
        files = {str(p.relative_to(ev)): C.sha256_path(p) for p in sorted(ev.rglob("*")) if p.is_file()} \
            if ev.is_dir() else {}
        d = self.root / self.key(pin, raw)
        d.mkdir(parents=True, exist_ok=True)
        (d / "entry.json").write_text(pretty_json({"outcome": outcome.record(), "evidence_dir": str(ev),
                                                   "evidence_files": files}))

    def get(self, pin: EnginePin, raw: bytes) -> Outcome | None:
        p = self.root / self.key(pin, raw) / "entry.json"
        if not p.is_file():
            return None
        e = json.loads(p.read_text())
        ev = Path(e["evidence_dir"])
        now = {str(q.relative_to(ev)): C.sha256_path(q) for q in sorted(ev.rglob("*")) if q.is_file()} \
            if ev.is_dir() else {}
        if now != e["evidence_files"]:
            return None
        return Outcome(**e["outcome"])
