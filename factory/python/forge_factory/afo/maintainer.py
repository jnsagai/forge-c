"""AFO M5 (AFO-T045..T051; AFO-FR-049..057; AT-043..051) - Factory Maintainer proposals.

A verified FACTORY_CODE_DEFECT may get a *candidate* patch prepared by the `afo-factory-maintainer` agent in an
isolated worktree. Everything after the agent is deterministic and owned by this module (no model):

  prepare  -> detached git worktree of the baseline under the sandbox data volume; every path outside the allowlist
              (or protected by the 004 CRE policy) is made read-only at OS level; one frozen case file
  agent    -> forge-maintainer-mcp only: canonical allowlisted writes in that worktree, candidate-owned tests run as
              the sandbox UID `maintainer` (network off, no credentials, source read-only), submit
  submit   -> broker commit (fixed identity), git-diff veto, the candidate's reproducer sealed OUTSIDE the repo
  triage   -> the reproducer must fail on the baseline (else REJECTED: an unsupported claim); 004 CAPA opened/linked
  evaluate -> the existing independent 004 promotion runner (staged reproducer + frozen prevention/golden/holdout);
              at best ELIGIBLE_FOR_OFFLINE_REVIEW
  publish  -> a local proposal branch and, only if policy maintenance.allow_proposal_pr, a DRAFT pull request made
              with the broker's own credentials; merge/rebase/force/main pushes are refused by an argv guard

Nothing here merges, deploys, edits main or touches the factory revision production runs use (AFO-FR-053/056).
Rejected or unsafe candidates are quarantined: no branch, worktree discarded, append-only record kept (AFO-FR-055).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from ..common import REPO_ROOT, sha256_bytes, sha256_file, state_dir, utc_now
from ..reliability import isolation
from ..reliability.protect import _match

MAX_SOURCE_READ_BYTES = 4 * 1024 * 1024
CANDIDATE_TESTS = "factory/python/tests/afo_candidate/"
ALLOW = ["factory/python/forge_factory/**", CANDIDATE_TESTS + "**"]
DENY = [  # inside ALLOW, still never the maintainer's: the deciders, the grants and the other repair identities
    "factory/python/forge_factory/afo/**",          # Conductor, AFO policy/authz, this broker
    "factory/python/forge_factory/reliability/**",  # independent CRE evaluator, CAPA registry, sandbox identities
    "factory/python/forge_factory/registry/**",     # role and MCP grants (no self-granting)
    "factory/python/forge_factory/mcp/sdk.py",      # MCP authorization
    "factory/python/forge_factory/mcp/servers/maintainer.py",
    "factory/python/forge_factory/repair/**",       # 002 infra fabric-repair
    "factory/python/forge_factory/supervisor/**",   # 002 model-free supervisor
    "factory/python/forge_factory/release/**",      # release packaging / archives
    "factory/python/forge_factory/policy/**",
]
MAX_PATHS, MAX_ADDED_LINES, MAX_FILE_BYTES, MAX_EXCERPT = 12, 600, 65536, 1500
CREDENTIAL = re.compile(r"auth\.json|\.ssh/|id_(?:rsa|ed25519|ecdsa)\b|\.netrc|\.git-credentials|GITHUB_TOKEN|GH_TOKEN|"
                        r"FABRO_[A-Z_]*TOKEN|_API_KEY|codex-home|keyring|/proc/(?:self|\d+)/environ", re.I)
SELF_MERGE = re.compile(r"\bgh\s+pr\s+merge\b|\bgit\s+(?:push|merge|rebase|reset)\b|auto_promote|auto_merge|"
                        r"allowed_auto_deployment", re.I)
SCRUB = re.compile(r"TOKEN|KEY|SECRET|PASSWORD|PASSWD|AUTH|CREDENTIAL|COOKIE|^GH_|^GITHUB_|^SSH_|^GIT_|^GPG|^CODEX|"
                   r"^OPENAI|^ANTHROPIC|^DEEPSEEK|^FORGE_|^FABRO|^VAULT", re.I)
PID = re.compile(r"^mnt-[a-z0-9-]{4,60}$")
IDENTITY = ["-c", "user.name=afo-factory-maintainer", "-c", "user.email=afo-maintainer@forge-c.invalid",
            "-c", "commit.gpgsign=false"]


class MaintainerDenied(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}:{detail}"[:300])
        self.code, self.detail = code, detail


def protected_globs() -> list[str]:
    from ..reliability.policy import load

    return list(load().get("security.protected_path_globs"))


def path_issue(rel: str, globs: list[str]) -> str | None:
    if not rel or rel.startswith(("/", "~")) or "\\" in rel or ".." in Path(rel).parts or "\x00" in rel:
        return "PATH_TRAVERSAL"
    if _match(rel, globs):
        return "PROTECTED_PATH"
    if _match(rel, DENY):
        return "MAINTAINER_DENIED_PATH"
    if not _match(rel, ALLOW):
        return "NOT_ALLOWLISTED"
    return None


def _git(*args: str, cwd: Path = REPO_ROOT, check: bool = True) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check, timeout=120).stdout


def veto(base: str, cand: str, repo: Path = REPO_ROOT, globs: list[str] | None = None) -> list[str]:
    """Git decides what changed (never the agent's claim): allowlist, protected paths, symlinks, size, credential
    access and self-merge/deploy text in added lines. Any finding = the candidate is unsafe (quarantine)."""
    globs = protected_globs() if globs is None else globs
    out: list[str] = []
    if subprocess.run(["git", "merge-base", "--is-ancestor", base, cand], cwd=repo, capture_output=True).returncode:
        out.append("NOT_DESCENDANT_OF_BASELINE")
    raw = _git("diff", "--raw", "--no-renames", "-z", base, cand, cwd=repo).split("\x00")
    paths = []
    for meta, path in zip(raw[0::2], raw[1::2], strict=False):
        if not meta.startswith(":"):
            continue
        new_mode, status = meta.split()[1], meta.split()[4]
        paths.append(path)
        issue = path_issue(path, globs)
        if issue:
            out.append(f"{issue}:{status}:{path}")
        if new_mode == "120000":
            out.append(f"SYMLINK:{path}")
        elif new_mode == "160000":
            out.append(f"SUBMODULE:{path}")
        elif new_mode == "100755" and status == "A":
            out.append(f"EXECUTABLE_FILE:{path}")
    if not paths:
        out.append("EMPTY_CANDIDATE")
    if len(paths) > MAX_PATHS:
        out.append(f"TOO_MANY_PATHS:{len(paths)}>{MAX_PATHS}")
    added = sum(int(x.split("\t")[0]) for x in _git("diff", "--numstat", base, cand, cwd=repo).splitlines()
                if x.split("\t")[0].isdigit())
    if added > MAX_ADDED_LINES:
        out.append(f"TOO_LARGE:{added}>{MAX_ADDED_LINES} added lines")
    cur = None
    for line in _git("diff", "-U0", "--no-renames", base, cand, cwd=repo).splitlines():
        if line.startswith("+++ "):
            cur = line[6:] if line.startswith("+++ b/") else line[4:]
        elif line.startswith("+") and cur:
            if CREDENTIAL.search(line):
                out.append(f"CREDENTIAL_ACCESS:{cur}")
            if SELF_MERGE.search(line):
                out.append(f"SELF_MERGE_OR_DEPLOY:{cur}")
    return sorted(set(out))[:20]


# -- isolated candidate worktree (T046) ---------------------------------------------------------------------------
def case_dir(pid: str) -> Path:
    if not PID.match(pid):
        raise MaintainerDenied("BAD_PROPOSAL_ID", pid)
    return state_dir() / "afo/maintainer" / pid


def prepare(pid: str, base: str, incident: dict, repo: Path = REPO_ROOT, *, retained_rework: dict | None = None) -> dict:
    """Detached worktree of `base`; everything the maintainer may not change is read-only (OS); one frozen case."""
    d = case_dir(pid)
    if (d / "case.json").exists():
        raise MaintainerDenied("CASE_EXISTS", pid)
    root = isolation.new_dir(f"afo-{pid}")
    src = root / "src"
    base_rev = _git("rev-parse", base, cwd=repo).strip()
    _git("worktree", "add", "--detach", str(src), base_rev, cwd=repo)
    globs = protected_globs()
    hardened = 0
    for dirpath, dirs, files in os.walk(src):
        dirs[:] = [x for x in dirs if x != ".git"]
        for name in files:
            p = Path(dirpath) / name
            if path_issue(p.relative_to(src).as_posix(), globs) and not p.is_symlink():
                p.chmod(p.stat().st_mode & 0o555)
                hardened += 1
    d.mkdir(parents=True, exist_ok=True)
    case = {"proposal_id": pid, "base": base_rev, "src": str(src), "root": str(root), "repo": str(repo),
            "incident": {k: str(v)[:400] for k, v in incident.items()}, "allow": ALLOW, "deny": DENY,
            "hardened_files": hardened, "isolation": isolation.level(), "created_utc": utc_now()}
    if retained_rework is not None:
        case["retained_rework"] = retained_rework
        if len(json.dumps(case).encode()) > 65536:
            subprocess.run(["git", "worktree", "remove", "--force", str(src)], cwd=repo, capture_output=True)
            isolation.discard(root)
            raise MaintainerDenied("REWORK_CASE_TOO_LARGE")
    if retained_rework is not None:
        from .durable import immutable_json

        immutable_json(d / "case.json", case)
    else:
        (d / "case.json").write_text(json.dumps(case, indent=2, sort_keys=True))
        (d / "case.json").chmod(0o400)
    return case


def load_case(pid: str) -> dict:
    return json.loads((case_dir(pid) / "case.json").read_text())


def safe_path(src: Path, rel: str, globs: list[str], *, write: bool) -> Path:
    issue = path_issue(rel, globs)
    if issue and (write or issue in ("PATH_TRAVERSAL", "PROTECTED_PATH")):  # reads: code yes, protected/holdout no
        raise MaintainerDenied(issue, rel)
    cur = src
    for part in Path(rel).parts:
        cur = cur / part
        if cur.is_symlink():
            raise MaintainerDenied("SYMLINK", rel)
    p = src / rel
    if src.resolve() not in p.resolve().parents:
        raise MaintainerDenied("PATH_TRAVERSAL", rel)
    return p



def work_unit(case: dict) -> dict:
    """Trusted task metadata from Git facts; incident/source prose never becomes an instruction."""
    src = Path(case["src"])
    names = _git("diff", "--name-only", "-z", case["base"], cwd=src).split("\0")
    names += _git("ls-files", "--others", "--exclude-standard", "-z", cwd=src).split("\0")
    paths = sorted({p for p in names if p})
    if len(paths) > MAX_PATHS:
        raise MaintainerDenied("REWORK_SCOPE_TOO_LARGE")
    files = []
    globs = protected_globs()
    for rel in paths:
        if not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", rel) or path_issue(rel, globs):
            raise MaintainerDenied("REWORK_SCOPE_PATH_INVALID", rel)
        p = safe_path(src, rel, globs, write=False)
        if not p.is_file() or p.stat().st_size > MAX_SOURCE_READ_BYTES:
            raise MaintainerDenied("REWORK_SCOPE_SOURCE_INVALID", rel)
        files.append({"path": rel, "sha256": sha256_file(p), "bytes": p.stat().st_size})
    return {"schema": "forge-c/maintenance-work-unit/1", "base": case["base"],
            "proposal_id": case["proposal_id"],
            "kind": "REWORK_RETAINED_CANDIDATE" if files else "REPAIR_BASELINE", "files": files}


SOURCE_ROOTS = ("factory/python/forge_factory", "factory/python/tests", "config/factory/profiles")


def source_inventory(case: dict, prefix: str = "factory/python/forge_factory") -> dict:
    """Names/hashes of existing readable Git/candidate files; no shell/glob permissions."""
    if (prefix != "." and (not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", prefix)
                           or ".." in Path(prefix).parts or prefix.startswith("/"))):
        raise MaintainerDenied("SOURCE_INVENTORY_PREFIX_INVALID")
    prefix = "" if prefix == "." else prefix.rstrip("/")
    if prefix and not any(prefix == root or prefix.startswith(root + "/") for root in SOURCE_ROOTS):
        raise MaintainerDenied("SOURCE_INVENTORY_OUT_OF_SCOPE", prefix)
    src = Path(case["src"])
    globs = protected_globs()
    with _case_lock(case):
        names = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard", cwd=src).split("\0")
        if len(names) > 20000:
            raise MaintainerDenied("SOURCE_INVENTORY_TOO_LARGE")
        entries = []
        for rel in sorted(set(names)):
            if not any(rel.startswith(root + "/") for root in SOURCE_ROOTS):
                continue
            if prefix and rel != prefix and not rel.startswith(prefix + "/"):
                continue
            if (not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", rel)
                    or path_issue(rel, globs) in ("PATH_TRAVERSAL", "PROTECTED_PATH")):
                continue
            try:
                p = safe_path(src, rel, globs, write=False)
            except MaintainerDenied:
                continue  # a symlink never becomes a discoverable source
            if p.is_file():
                entries.append({"path": rel, "bytes": p.stat().st_size, "sha256": sha256_file(p)})
    return {"schema": "forge-c/maintenance-source-inventory/1", "base": case["base"],
            "roots": list(SOURCE_ROOTS), "prefix": prefix or ".", "entries": entries,
            "count": len(entries), "write_authority": "UNCHANGED"}


def read_source(case: dict, rel: str, max_bytes: int = MAX_EXCERPT * 2) -> str:
    p = safe_path(Path(case["src"]), rel, protected_globs(), write=False)
    if not p.is_file():
        raise MaintainerDenied("NOT_FOUND", rel)
    with p.open("rb") as stream:
        return stream.read(max_bytes).decode("utf-8", errors="replace")


@contextmanager
def _case_lock(case: dict, *, wait: bool = False):
    import fcntl

    path = case_dir(case["proposal_id"]) / ".submission.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError as exc:
            raise MaintainerDenied("SOURCE_EDIT_BUSY") from exc
        yield


def _unsealed(case: dict) -> None:
    directory = case_dir(case["proposal_id"])
    if (directory / "submission-intent.json").exists() or (directory / "submission.json").exists():
        raise MaintainerDenied("CASE_ALREADY_SUBMITTED", case["proposal_id"])


def _write_source(case: dict, rel: str, text: str) -> str:
    if len(text.encode()) > MAX_FILE_BYTES:
        raise MaintainerDenied("FILE_TOO_LARGE", rel)
    p = safe_path(Path(case["src"]), rel, protected_globs(), write=True)
    if p.exists() and not os.access(p, os.W_OK):
        raise MaintainerDenied("OS_READ_ONLY", rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = text.encode("utf-8")
    mode = p.stat().st_mode & 0o777 if p.exists() else 0o644
    fd, temporary = tempfile.mkstemp(prefix=".afo-source-", dir=p.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, p)
        parent = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return sha256_file(p)


def write_source(case: dict, rel: str, text: str) -> str:
    with _case_lock(case):
        _unsealed(case)
        return _write_source(case, rel, text)


def edit_source(case: dict, rel: str, expected_sha256: str, old_text: str, new_text: str) -> str:
    """One exact bounded replacement; stale/ambiguous requests never mutate source."""
    if (not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or not old_text or old_text == new_text
            or max(len(old_text.encode()), len(new_text.encode())) > 8192):
        raise MaintainerDenied("SOURCE_EDIT_INVALID")
    with _case_lock(case):
        _unsealed(case)
        p = safe_path(Path(case["src"]), rel, protected_globs(), write=True)
        if not p.is_file() or p.stat().st_size > MAX_FILE_BYTES:
            raise MaintainerDenied("SOURCE_EDIT_FILE_INVALID", rel)
        raw = p.read_bytes()
        if sha256_bytes(raw) != expected_sha256:
            raise MaintainerDenied("SOURCE_EDIT_STALE", rel)
        before = old_text.encode("utf-8")
        if raw.count(before) != 1:
            raise MaintainerDenied("SOURCE_EDIT_ANCHOR_NOT_UNIQUE", rel)
        replacement = raw.replace(before, new_text.encode("utf-8"), 1)
        try:
            text = replacement.decode("utf-8")
        except UnicodeError as exc:
            raise MaintainerDenied("SOURCE_EDIT_NOT_UTF8", rel) from exc
        return _write_source(case, rel, text)


def clean_env(src: Path, scratch: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not SCRUB.search(k)}
    env.update({"PYTHONPATH": str(src / "factory/python"), "FORGE_REPO_ROOT": str(src), "HOME": str(scratch),
                "FORGE_STATE_DIR": str(scratch / "state"), "FORGE_EVENTS_DIR": str(scratch / "events"),
                "PYTHONDONTWRITEBYTECODE": "1"})
    return env


def run_tests(case: dict, tests: list[str], timeout: int = 540) -> dict:
    """Candidate-owned tests only, as the sandbox UID `maintainer`: source mounted read-only, network off, HOME and
    state in a private scratch dir, credential-like variables removed."""
    src = Path(case["src"])
    if not tests or len(tests) > 5:
        raise MaintainerDenied("TESTS_REQUIRED", "1..5 candidate test files")
    for t in tests:
        if not (t.startswith(CANDIDATE_TESTS) and t.endswith(".py")):
            raise MaintainerDenied("NOT_A_CANDIDATE_TEST", t)
        safe_path(src, t, protected_globs(), write=False)
    scratch = isolation.new_dir("afo-mnt-test")
    isolation.hand_over("maintainer", scratch)
    try:
        p = isolation.execute("maintainer", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                             "--rootdir", str(src), *[str(src / t) for t in tests]],
                              cwd=scratch, env=clean_env(src, scratch), writable=[scratch], readable=[src],
                              timeout=timeout)
    finally:
        isolation.discard(scratch)
    out = p.stdout + b"\n--- stderr ---\n" + p.stderr
    return {"exit_code": p.returncode, "passed": p.returncode == 0, "output_sha256": sha256_bytes(out),
            "excerpt": out.decode(errors="replace")[-MAX_EXCERPT:], "isolation": isolation.level()}


# -- submit: broker commit + veto + sealed reproducer (T047) ------------------------------------------------------
def submit(case: dict, summary: str, reproducer: str, signature: str) -> dict:
    """Serialize one submission; recover a lost commit acknowledgement from its frozen tree/parent."""
    with _case_lock(case, wait=True):
        return _submit(case, summary, reproducer, signature)


def _submit(case: dict, summary: str, reproducer: str, signature: str) -> dict:
    from .durable import digest, immutable_bytes, immutable_json, strict_json

    src, pid = Path(case["src"]), case["proposal_id"]
    if not (reproducer.startswith(CANDIDATE_TESTS) and reproducer.endswith(".py")):
        raise MaintainerDenied("REPRODUCER_NOT_CANDIDATE_OWNED", reproducer)
    if not re.fullmatch(r"[\w .:,/()'-]{8,160}", signature):
        raise MaintainerDenied("BAD_SYMPTOM_SIGNATURE", signature[:60])
    d = case_dir(pid)
    frozen = d / "case.json"
    if digest(strict_json(frozen.read_bytes(), 65536)) != digest(case):
        raise MaintainerDenied("FROZEN_CASE_CHANGED")
    request = digest({"case_sha256": sha256_file(frozen), "summary": summary,
                      "reproducer": reproducer, "signature": signature})
    intent_path = d / "submission-intent.json"
    if intent_path.exists():
        intent = strict_json(intent_path.read_bytes(), 65536)
        if intent["request_sha256"] != request:
            raise MaintainerDenied("SUBMISSION_REPLAY_CHANGED")
    else:
        _git("add", "-A", cwd=src)
        if not _git("status", "--porcelain", cwd=src).strip():
            raise MaintainerDenied("EMPTY_CANDIDATE")
        intent = {"request_sha256": request, "case_sha256": sha256_file(frozen),
                  "parent": _git("rev-parse", "HEAD", cwd=src).strip(),
                  "tree": _git("write-tree", cwd=src).strip(), "submitted_utc": utc_now(),
                  "message": f"AFO maintainer candidate {pid}: {' '.join(summary.split())[:200]}".rstrip(" ")}
        immutable_json(intent_path, intent)
    if (d / "submission-receipt.json").exists():
        return submission(case, require_receipt=True)[0]
    head = _git("rev-parse", "HEAD", cwd=src).strip()
    if head == intent["parent"]:
        if _git("write-tree", cwd=src).strip() != intent["tree"]:
            raise MaintainerDenied("SUBMISSION_TREE_CHANGED")
        _git(*IDENTITY, "commit", "-q", "--no-verify", "-m", intent["message"], cwd=src)
        head = _git("rev-parse", "HEAD", cwd=src).strip()
    # A crash after commit but before receipt must adopt precisely that effect, never commit again.
    actual = _git("show", "-s", "--format=%P%n%T%n%B", head, cwd=src).strip().split("\n", 2)
    # Git strips trailing ASCII spaces from a commit message. Adopt legacy effects
    # only under that exact normalization; parent, tree and all other message bytes stay bound.
    if actual != [intent["parent"], intent["tree"], intent["message"].rstrip(" ")]:
        raise MaintainerDenied("SUBMISSION_COMMIT_MISMATCH")
    cand = head
    issues = veto(case["base"], cand, Path(case["repo"]))
    staged = None
    if not issues:
        text = _git("show", f"{cand}:{reproducer}", cwd=src)  # the committed content, not the live file
        repro_dir = case_dir(pid) / "reproducer"
        repro_dir.mkdir(parents=True, exist_ok=True)
        script = repro_dir / "reproducer.py"
        # read-only for everyone: the CRE verifier runs it as its sandbox UID (r: 0o400 was "Permission denied" in
        # the M5 drill); integrity is the sha256 in the sealed manifest, and no sandbox UID can write here
        immutable_bytes(script, text.encode(), 0o444)
        rid = "AFO-" + pid
        man = {"reproducers": [{"id": rid, "script": script.name, "sha256": sha256_file(script),
                                "symptom_signature": signature, "observed_in": case["incident"].get("order_id", ""),
                                "baseline_revision": case["base"], "fix_revision": cand,
                                "source_path": reproducer}]}
        # JSON is valid YAML; use immutable publication for the existing CRE manifest reader.
        immutable_json(repro_dir / "manifest.yaml", man)
        staged = {"id": rid, "manifest": str(repro_dir / "manifest.yaml"), "sha256": man["reproducers"][0]["sha256"]}
    sub = {"proposal_id": pid, "candidate": cand, "veto": issues, "staged": staged, "summary": summary[:300],
           "submitted_utc": intent["submitted_utc"]}
    sub_hash = immutable_json(d / "submission.json", sub)
    receipt = {"schema_version": "1.0", "case_sha256": intent["case_sha256"],
               "request_sha256": request, "submission_sha256": sub_hash, "candidate": cand,
               "manifest_sha256": sha256_file(Path(staged["manifest"])) if staged else None,
               "reproducer_sha256": staged["sha256"] if staged else None}
    immutable_json(d / "submission-receipt.json", receipt)
    return sub


def submission(case: dict, *, require_receipt: bool = False) -> tuple[dict, dict | None]:
    """Read durable candidate evidence; a receipt proves submission, never product correctness."""
    from .durable import digest, strict_json

    d = case_dir(case["proposal_id"])
    sub = strict_json((d / "submission.json").read_bytes(), 65536)
    path = d / "submission-receipt.json"
    if not path.exists() and not require_receipt and not (d / "submission-intent.json").exists():
        return sub, None  # legacy M5 submissions retain their independent validation path
    receipt = strict_json(path.read_bytes(), 65536)
    if (receipt["case_sha256"] != sha256_file(d / "case.json")
            or digest(strict_json((d / "case.json").read_bytes(), 65536)) != digest(case)
            or receipt["submission_sha256"] != sha256_file(d / "submission.json")
            or receipt["candidate"] != sub["candidate"] or sub["proposal_id"] != case["proposal_id"]):
        raise MaintainerDenied("SUBMISSION_RECEIPT_MISMATCH")
    if sub["staged"]:
        manifest = Path(sub["staged"]["manifest"])
        if (manifest != d / "reproducer/manifest.yaml" or manifest.is_symlink()
                or receipt["manifest_sha256"] != sha256_file(manifest)
                or (manifest.parent / "reproducer.py").is_symlink()
                or receipt["reproducer_sha256"] != sha256_file(manifest.parent / "reproducer.py")):
            raise MaintainerDenied("SUBMISSION_REPRODUCER_CHANGED")
    return sub, receipt


def changed_paths(base: str, cand: str, repo: Path) -> list[str]:
    return sorted(set(_git("diff", "--name-only", "--no-renames", base, cand, cwd=repo).split()))


def record(store, case: dict, sub: dict, outcome: str, status: str, *, capa_id: str | None = None,
           promotion_id: str = "NOT_EVALUATED", tests_ref: str = "NOT_RUN", branch: str | None = None,
           pr_url: str | None = None, evidence: list[str] = ()) -> dict:
    repo = Path(case["repo"])
    rec = {"schema_version": "1.0", "proposal_id": case["proposal_id"],
           "source_incident_id": case["incident"].get("incident_id") or case["incident"].get("order_id") or "unknown",
           "capa_id": capa_id, "reproducer_id": (sub.get("staged") or {}).get("id") or "NONE",
           "baseline_commit": case["base"], "candidate_commit": sub["candidate"],
           "changed_paths": changed_paths(case["base"], sub["candidate"], repo), "tests_ref": tests_ref,
           "cre_promotion_id": promotion_id, "outcome": outcome, "auto_deployment_allowed": False,
           "branch_ref": branch, "pr_url": pr_url, "authorization_ref": None,
           "evidence_refs": sorted({*evidence, *(f"veto:{v}"[:200] for v in sub.get("veto", []))}) or ["none"]}
    if not sub.get("veto"):
        rec["protected_changes_count"] = 0
    store.record_proposal(rec, status, case["incident"].get("order_id"))
    return rec


def quarantine(case: dict) -> None:
    """Unsafe/rejected: the worktree is discarded (its commit stays only as an unreferenced object), no branch."""
    root = Path(case["root"])
    subprocess.run(["git", "worktree", "remove", "--force", case["src"]], cwd=case["repo"], capture_output=True)
    if root.exists():
        isolation.discard(root)


# -- triage with 004 CAPA linkage (T047) and independent evaluation (T048) ----------------------------------------
def _next_capa(reg) -> str:
    n = max([int(c["capa_id"].split("-")[1]) for c in reg.all()] or [0])
    return f"CAPA-{n + 1:03d}"


def triage(case: dict, sub: dict, cre_store, policy, *, capa_id: str | None = None, fingerprints=()) -> dict:
    """The reproducer must show the symptom on the UNCHANGED baseline (runner record, verifier UID) before any
    candidate is evaluated; the defect is then linked to an existing CAPA or a new one (cause = HYPOTHESIS)."""
    from ..reliability import reproduce as RR
    from ..reliability.capa import CapaRegistry

    staged = sub["staged"]
    reps, issues = RR.load_manifest(Path(staged["manifest"]))
    if issues or staged["id"] not in reps:
        return {"ok": False, "reason": "STAGED_REPRODUCER_INVALID:" + ",".join(issues)[:120]}
    with RR.WorktreePool(Path(case["repo"])) as pool:
        b = RR.run(cre_store, policy, staged["id"], case["base"], "BASELINE", pool, reps)
    if b["verdict"] != "SYMPTOM_PRESENT":
        return {"ok": False, "reason": f"REPRODUCER_DOES_NOT_FAIL_ON_BASELINE:{b['verdict']}", "baseline_run": b}
    reg = CapaRegistry(cre_store, policy)
    linked_cases = [c['capa_id'] for c in reg.all() if case['proposal_id'] in reg.links(c['capa_id'], 'AFO_PROPOSAL')]
    if len(linked_cases) > 1:
        raise MaintainerDenied("AMBIGUOUS_CAPA_LINK")
    if capa_id and reg.get(capa_id):
        linked = capa_id
    elif linked_cases:
        linked = linked_cases[0]  # recover independent verification without a duplicate CAPA
    else:
        linked = _next_capa(reg)
        observed = (case["incident"].get("incident_id") or case["incident"].get("source_order_id")
                    or case["incident"].get("order_id") or "afo-proposal:" + case['proposal_id'])
        reg.open(linked, [observed], list(fingerprints),
                 f"AFO maintainer {case['proposal_id']}: {sub['summary']}"[:1000])
        reg.triage(linked, f"maintainer hypothesis (unverified): {sub['summary']}"[:1500], None,
                   "AGENT (afo-factory-maintainer)")
    reg.link(linked, "AFO_PROPOSAL", case["proposal_id"])
    reg.link(linked, "AFO_STAGED_REPRODUCER", staged["id"])
    return {"ok": True, "capa_id": linked, "baseline_run": b}


def evaluate(case: dict, sub: dict, cre_store, policy, evaluator=None) -> dict:
    from ..reliability import promotion

    ev = evaluator or promotion.evaluate
    return ev(sub["candidate"], case["base"], cre_store, policy, reproducers=[sub["staged"]["id"]], kind="FIX",
              repo=Path(case["repo"]), staged_manifest=Path(sub["staged"]["manifest"]))


def process(store, pid: str, cre_store, policy, *, capa_id: str | None = None, fingerprints=(),
            tests_ref: str = "NOT_RUN", evaluator=None, binding_ref: dict | None = None) -> dict:
    """Submission -> veto -> triage -> CRE evaluation -> append-only record. Never publishes or deploys."""
    case = load_case(pid)
    sub, _ = submission(case)
    binding_evidence = []
    if binding_ref is not None:
        from .maintenance_binding import bound_submission

        sub = bound_submission(store, case, sub, binding_ref)
        binding_evidence = ["administrative-binding:" + binding_ref["binding_id"]]
        previous = store.proposal(pid)
        if previous and binding_evidence[0] in previous['record']['evidence_refs']:
            return previous['record']  # historical independently evaluated binding, no repeat effect
    if sub["veto"]:
        rec = record(store, case, sub, "QUARANTINED", "QUARANTINED", tests_ref=tests_ref)
        quarantine(case)
        return rec
    t = triage(case, sub, cre_store, policy, capa_id=capa_id, fingerprints=fingerprints)
    if not t["ok"]:
        rec = record(store, case, sub, "REJECTED", "REJECTED", promotion_id="NOT_EVALUATED:" + t["reason"][:80],
                     tests_ref=tests_ref, evidence=[*binding_evidence, f"triage:{t['reason']}"[:200]])
        quarantine(case)
        return rec
    d = evaluate(case, sub, cre_store, policy, evaluator)
    outcome = {"ELIGIBLE_FOR_OFFLINE_REVIEW": "ELIGIBLE_FOR_OFFLINE_REVIEW", "INCONCLUSIVE": "INCONCLUSIVE"}.get(
        d["decision"], "REJECTED")
    if d.get("allowed_auto_deployment") is not False:
        outcome = "QUARANTINED"  # an evaluator claiming deployment rights is itself a fault
    rec = record(store, case, sub, outcome, outcome, capa_id=t["capa_id"], promotion_id=d["decision_id"],
                 tests_ref=tests_ref, evidence=[*binding_evidence, f"promotion-decision:{d['decision_id']}",
                                                f"reproducer-run:{t['baseline_run']['run_id']}"])
    if outcome != "ELIGIBLE_FOR_OFFLINE_REVIEW":
        quarantine(case)
    return rec


# -- deterministic broker (T049/T050) -----------------------------------------------------------------------------
FORCE = {"--force", "-f", "--force-with-lease", "--admin", "--auto", "--merge", "--squash", "--rebase", "--delete"}


def guard(argv: list[str]) -> None:
    """The broker can create a branch and a DRAFT pull request; it can never merge, rebase, force or touch main."""
    a = [str(x) for x in argv]
    if a[:3] == ["gh", "pr", "merge"] or a[:2] in (["git", "merge"], ["git", "rebase"], ["git", "reset"]) \
            or a[:3] in (["gh", "pr", "ready"], ["gh", "api", "-X"]) or FORCE & set(a):
        raise MaintainerDenied("BROKER_FORBIDDEN", " ".join(a)[:120])
    if a[:2] == ["git", "push"] and any(re.search(r"(^|:)(refs/heads/)?(main|master)$", x) for x in a[2:]):
        raise MaintainerDenied("BROKER_FORBIDDEN", "push to main")
    if a[:3] == ["gh", "pr", "create"] and "--draft" not in a:
        raise MaintainerDenied("BROKER_FORBIDDEN", "pull request must be a draft")


def publish(store, pid: str, eff, *, runner=None, remote: str = "origin", base_branch: str = "main") -> dict:
    """ELIGIBLE_FOR_OFFLINE_REVIEW -> local branch afo/proposal/<pid> (+ draft PR when the policy allows). The
    agent never runs this and never sees the broker's environment/credentials."""
    cur = store.proposal(pid)
    if cur is None or cur["status"] not in ("ELIGIBLE_FOR_OFFLINE_REVIEW", "PUBLISHED"):
        raise MaintainerDenied("NOT_ELIGIBLE", (cur or {}).get("status", "none"))
    if not eff.get("maintenance.enable_factory_maintainer"):
        raise MaintainerDenied("MAINTAINER_DISABLED_BY_POLICY")
    case = load_case(pid)
    sub, _ = submission(case)
    if sub["candidate"] != cur["record"]["candidate_commit"]:
        raise MaintainerDenied("PUBLICATION_SUBMISSION_MISMATCH")
    rec, repo = cur["record"], Path(case["repo"])
    again = veto(rec["baseline_commit"], rec["candidate_commit"], repo)
    if again:
        raise MaintainerDenied("VETO_ON_PUBLISH", ";".join(again)[:200])
    run = runner or (lambda argv: subprocess.run(argv, cwd=repo, capture_output=True, text=True, timeout=300))

    def call(argv: list[str]):
        guard(argv)
        return run(argv)

    branch = f"afo/proposal/{pid}"
    have = _git("rev-parse", "--verify", "-q", f"refs/heads/{branch}", cwd=repo, check=False).strip()
    if have and have != rec["candidate_commit"]:
        raise MaintainerDenied("BRANCH_EXISTS_DIFFERENT", branch)
    if not have:
        call(["git", "branch", branch, rec["candidate_commit"]])
    pr_url = None
    if eff.get("maintenance.allow_proposal_pr"):
        p = call(["git", "push", remote, f"refs/heads/{branch}:refs/heads/{branch}"])
        if getattr(p, "returncode", 1):
            raise MaintainerDenied("PUSH_FAILED", str(getattr(p, "stderr", ""))[-120:])
        body = (f"AFO Factory Maintainer proposal {pid} (candidate {rec['candidate_commit'][:12]}).\n\n"
                f"CAPA: {rec['capa_id']}; reproducer: {rec['reproducer_id']}; CRE decision: {rec['cre_promotion_id']} "
                "(ELIGIBLE_FOR_OFFLINE_REVIEW).\nOffline human review only: no automatic merge or deployment.")
        existing = call(['gh', 'pr', 'list', '--head', branch, '--base', base_branch,
                         '--state', 'all', '--json', 'url,isDraft,headRefOid'])
        try:
            matches = json.loads(existing.stdout) if existing.returncode == 0 else None
        except (ValueError, AttributeError):
            matches = None
        if matches is None:
            raise MaintainerDenied('PR_RECONCILIATION_UNKNOWN', branch)
        if matches:
            if (len(matches) != 1 or matches[0].get('isDraft') is not True
                    or matches[0].get('headRefOid') != rec['candidate_commit']):
                raise MaintainerDenied('PR_RECONCILIATION_CONFLICT', branch)
            pr_url = matches[0]['url']
        else:
            pr_url = None
        p = None if pr_url else call(["gh", "pr", "create", "--draft", "--base", base_branch, "--head", branch,
                  "--title", f"AFO proposal {pid}: {rec['capa_id']}", "--body", body])
        if p is not None and getattr(p, "returncode", 1):
            raise MaintainerDenied("PR_FAILED", str(getattr(p, "stderr", ""))[-120:])
        if p is not None:
            pr_url = str(p.stdout).strip().splitlines()[-1]
    return record(store, case, sub, "ELIGIBLE_FOR_OFFLINE_REVIEW", "PUBLISHED", capa_id=rec["capa_id"],
                  promotion_id=rec["cre_promotion_id"], tests_ref=rec["tests_ref"], branch=branch, pr_url=pr_url,
                  evidence=[x for x in rec["evidence_refs"] if x != "none"])


def open_cases(store, eff, repo: Path = REPO_ROOT) -> list[str]:
    """Conductor hook (cheap, PILOT/ACTIVE only): a case per order waiting for an external factory change, when the
    owner enabled the maintainer. Running the agent and the (long) evaluation are separate steps outside the cycle."""
    if not eff.get("maintenance.enable_factory_maintainer"):
        return []
    out = []
    for o in store.orders(("WAITING_EXTERNAL_CHANGE",)):
        from . import bundle, runtime

        attempts = store.attempts(o["order_id"])
        pid = f"mnt-{o['order_id'].removeprefix('afo-')[:16]}-a{len(attempts)}"
        if not (case_dir(pid) / "case.json").exists():
            ws = runtime.workspace_of(attempts[-1])
            failure = bundle.build(ws, o["order_id"], attempts[-1]["attempt_id"]) if ws.is_dir() else None
            incident = {"order_id": o["order_id"], "reason": o.get("terminal_reason") or ""}
            if failure:
                incident.update({k: failure[k] for k in ("phase", "fingerprint", "error_code", "redacted_summary")})
            revision = attempts[-1]["record"].get("factory_revision", "")
            prepare(pid, revision if re.fullmatch(r"[0-9a-f]{40}", revision) else "HEAD", incident, repo)
            out.append(pid)
    return out
