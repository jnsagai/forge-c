"""DA-T058 / DA-FR-058: signed patch bundles, built in development and imported by the local, offline factory.

    python -m forge_factory.offline.patch build --repo <dev checkout> --base <rev> --target <rev> \
        --regression <test path> [...] --cre-decision <pd-*.json> --approver <principal> --out <patch.zip>
    python -m forge_factory.offline.patch sign <patch.zip> --key <owner key or .pub with --agent>        (owner only)
    python -m forge_factory.offline.patch import <patch.zip> --install-root <dir> --allowed-signers <file> \
        --preflight-cmd "<command run in the staged release>"
    python -m forge_factory.offline.patch rollback --install-root <dir>

The deployment keeps whole releases: <install-root>/releases/<revision>/ and a `current` symlink. A bundle holds
PATCH.json (contracts/patch-bundle.schema.json), the CRE promotion decision for exactly base..target and the new file
contents; the owner's detached signature `<patch.zip>.sig` (namespace `forge-patch-bundle`) covers the canonical
PATCH.json, which hashes everything else. Import activates a patch only when ALL hold, in this order:
  schema; signature by the approver; `current` is the base revision; every content and the CRE decision match their
  hashes; the decision is ELIGIBLE_FOR_OFFLINE_REVIEW for this base and target; no path is protected by the DEPLOYED
  reliability policy; the whole deployed release matches the decision's baseline_sha256 before its policy is read;
  every file to change or delete still has its base content and every new file is new; the whole staged release
  matches candidate_sha256 both before and after truthful local preflight and the declared regression pass.
Releases are clean code-only archives. Dependencies, state and generated outputs live outside releases; local checks
must leave the code tree unchanged. Imported bundles need both CRE tree identities. Changed symlinks and gitlinks are
not supported by this bundle format and fail the exact candidate check. Unchanged symlinks retain their Git identity.
Activation is one atomic `current` switch; the previous release stays for `rollback`. Every outcome, refusals
included, is an import record. Nothing here opens a network connection or promotes anything by itself.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

import yaml

from ..common import REPO_ROOT, canonical_json, utc_now
from ..reliability.protect import _match

SCHEMA_ID = "forge-c/patch-bundle/1"
NAMESPACE = "forge-patch-bundle"
CONTRACT = REPO_ROOT / "specs/014-durable-local-autonomy/contracts/patch-bundle.schema.json"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
ELIGIBLE = "ELIGIBLE_FOR_OFFLINE_REVIEW"


class Refused(Exception):
    def __init__(self, code: str, reason: str = ""):
        super().__init__(f"{code}: {reason}")
        self.code, self.reason = code, reason


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _release_sha256(root: Path) -> str:
    """Reproduce CRE's Git tree-listing digest from a clean, code-only release.

    No ignore rules apply: extra files, executable-bit drift and changed symlink
    text all change the identity. State, dependencies and caches belong outside
    the release. Git metadata and filesystem special files are never admitted.
    """
    escapes = {7: b"\\a", 8: b"\\b", 9: b"\\t", 10: b"\\n", 11: b"\\v", 12: b"\\f", 13: b"\\r",
               34: b'\\"', 92: b"\\\\"}

    def quote(path: bytes) -> bytes:
        if all(32 <= c < 127 and c not in escapes for c in path):
            return path
        return b'"' + b"".join(escapes.get(c, bytes([c]) if 32 <= c < 127 else f"\\{c:03o}".encode())
                                for c in path) + b'"'

    if root.is_symlink() or not root.is_dir():
        raise Refused("PATCH_RELEASE_UNSAFE", "release must be a real directory")
    listing = hashlib.sha256()

    def walk(directory: Path, prefix: bytes = b"") -> None:
        with os.scandir(directory) as scan:
            entries = sorted(scan, key=lambda e: os.fsencode(e.name) +
                             (b"/" if e.is_dir(follow_symlinks=False) else b""))
        for entry in entries:
            path = prefix + os.fsencode(entry.name)
            if entry.name == ".git":
                raise Refused("PATCH_RELEASE_UNSAFE", "Git metadata is not a release artifact")
            st = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(st.st_mode):
                walk(Path(entry.path), path + b"/")
                continue
            if stat.S_ISLNK(st.st_mode):
                mode, data = b"120000", os.fsencode(os.readlink(entry.path))
            elif stat.S_ISREG(st.st_mode):
                mode = b"100755" if st.st_mode & stat.S_IXUSR else b"100644"
                data = Path(entry.path).read_bytes()
            else:
                raise Refused("PATCH_RELEASE_UNSAFE", "unsupported filesystem object")
            # Git uses SHA-1 blob object IDs inside its SHA-256-authenticated tree listing.
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data, usedforsecurity=False).hexdigest()
            listing.update(mode + b" blob " + blob.encode() + b"\t" + quote(path) + b"\n")

    walk(root)
    return listing.hexdigest()


def message(patch: dict) -> bytes:
    return canonical_json(patch)


def schema_errors(patch: dict) -> list[str]:
    import jsonschema

    v = jsonschema.Draft202012Validator(json.loads(CONTRACT.read_text()), format_checker=jsonschema.FormatChecker())
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:160] for e in v.iter_errors(patch)]


# ---------------------------------------------------------------- development side
def build(repo: Path, base: str, target: str, regression: list[str], cre_decision: Path, approver: str,
          out: Path) -> dict:
    def git(*a: str) -> bytes:
        return subprocess.run(["git", *a], cwd=repo, capture_output=True, check=True, timeout=120).stdout

    base, target = git("rev-parse", base).decode().strip(), git("rev-parse", target).decode().strip()
    files, blobs = [], {}
    raw = git("diff", "--name-status", "--no-renames", "-z", base, target).decode().split("\0")[:-1]  # status\0path\0
    for status, path in zip(raw[0::2], raw[1::2], strict=True):
        before = _sha(git("show", f"{base}:{path}")) if status != "A" else None
        if status == "D":
            files.append({"path": path, "op": "delete", "base_sha256": before})
            continue
        data = git("show", f"{target}:{path}")
        mode = git("ls-tree", target, "--", path).decode().split()[0]
        files.append({"path": path, "op": "write", "sha256": _sha(data), "base_sha256": before,
                      "mode": "755" if mode == "100755" else "644"})
        blobs[f"files/{path}"] = data
    dec = cre_decision.read_bytes()
    patch = {"schema": SCHEMA_ID, "patch_id": f"PATCH-{base[:12]}-{target[:12]}", "base_revision": base,
             "target_revision": target, "files": files, "regression": sorted(regression),
             "cre_decision_sha256": _sha(dec), "approver": approver, "created_utc": utc_now()}
    errs = schema_errors(patch)
    if errs:
        raise ValueError(f"PATCH_SCHEMA_INVALID: {errs[:3]}")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in [("PATCH.json", json.dumps(patch, indent=1, sort_keys=True).encode() + b"\n"),
                           ("cre/decision.json", dec), *sorted(blobs.items())]:
            zi = zipfile.ZipInfo(name, FIXED_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o444 << 16
            zf.writestr(zi, data)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue())
    return {"bundle": str(out), "sha256": _sha(buf.getvalue()), "patch_id": patch["patch_id"], "files": len(files)}


def sign(bundle: Path, key: Path, agent: bool = False) -> Path:
    """Owner CLI: write <bundle>.sig over the canonical PATCH.json (--agent: the key file is a .pub in ssh-agent)."""
    patch = json.loads(zipfile.ZipFile(bundle).read("PATCH.json"))
    with tempfile.TemporaryDirectory() as td:
        m = Path(td) / "msg"
        m.write_bytes(message(patch))
        subprocess.run(["ssh-keygen", "-Y", "sign", *(["-U"] if agent else []), "-f", str(key), "-n", NAMESPACE,
                        str(m)], check=True, capture_output=True)
        out = bundle.with_name(bundle.name + ".sig")
        out.write_bytes((Path(td) / "msg.sig").read_bytes())
    return out


# ---------------------------------------------------------------- deployment side
def _current(root: Path) -> str | None:
    cur = root / "current"
    if not cur.is_symlink():
        return None
    revision = Path(os.readlink(cur)).name
    return revision if cur.resolve() == (root / "releases" / revision).resolve() else None


def _switch(root: Path, revision: str) -> None:
    tmp = root / f".current.{os.getpid()}"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    tmp.symlink_to(Path("releases") / revision)
    os.replace(tmp, root / "current")  # atomic


def _record(root: Path, rec: dict) -> dict:
    d = root / "imports"
    d.mkdir(exist_ok=True)
    with (d / "log.jsonl").open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


@contextmanager
def _import_lock(root: Path):
    """Serialize the local import and rollback entry points across processes."""
    (root / "imports").mkdir(exist_ok=True)
    with (root / "imports/.lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def _inside(base: Path, rel: str) -> Path:
    p = base / rel
    for parent in [*reversed(p.relative_to(base).parents), p.relative_to(base)]:
        if parent != Path(".") and (base / parent).is_symlink():
            raise Refused("PATCH_PATH_UNSAFE", f"{rel} crosses a symlink")
    if not p.resolve().is_relative_to(base.resolve()):
        raise Refused("PATCH_PATH_UNSAFE", rel)
    return p


def _checks_default(staged: Path, regression: list[str], preflight_cmd: str) -> list[dict]:
    env = {**os.environ, "PYTHONPATH": str(staged / "factory/python"), "FORGE_REPO_ROOT": str(staged),
           "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    out = []
    for name, cmd in [("preflight", shlex.split(preflight_cmd)),
                      ("regression", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *regression])]:
        r = subprocess.run(cmd, cwd=staged, env=env, capture_output=True, text=True, timeout=3600)
        out.append({"check": name, "exit_code": r.returncode, "tail": (r.stdout + r.stderr).strip()[-300:]})
    return out


def import_patch(bundle: Path, *, install_root: Path, allowed_signers: Path, preflight_cmd: str | None = None,
                 checks: Callable[[Path, list[str]], list[dict]] | None = None, sig: Path | None = None) -> dict:
    with _import_lock(Path(install_root)):
        return _import_patch(bundle, install_root=install_root, allowed_signers=allowed_signers,
                             preflight_cmd=preflight_cmd, checks=checks, sig=sig)


def _import_patch(bundle: Path, *, install_root: Path, allowed_signers: Path, preflight_cmd: str | None,
                  checks: Callable[[Path, list[str]], list[dict]] | None, sig: Path | None) -> dict:
    root, sig = Path(install_root), sig or bundle.with_name(bundle.name + ".sig")
    rec = {"bundle_sha256": _sha(bundle.read_bytes()), "at": utc_now(), "previous": _current(root)}
    staged = None
    try:
        zf = zipfile.ZipFile(bundle)
        names = set(zf.namelist())
        patch = json.loads(zf.read("PATCH.json"))
        rec |= {"patch_id": patch.get("patch_id"), "base": patch.get("base_revision"),
                "target": patch.get("target_revision")}
        errs = schema_errors(patch)
        if errs:
            raise Refused("PATCH_SCHEMA_INVALID", errs[0])
        if not sig.is_file() or not allowed_signers.is_file() or subprocess.run(
                ["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers), "-I", patch["approver"], "-n", NAMESPACE,
                 "-s", str(sig)], input=message(patch), capture_output=True, timeout=30).returncode != 0:
            raise Refused("PATCH_SIGNATURE_INVALID", f"no valid {NAMESPACE} signature by {patch['approver']}")
        base, target = patch["base_revision"], patch["target_revision"]
        if rec["previous"] != base:
            raise Refused("PATCH_BASE_MISMATCH", f"current is {rec['previous']}, the patch needs {base}")
        if (root / "releases" / target).exists():
            raise Refused("PATCH_TARGET_EXISTS", target)
        want = {"PATCH.json", "cre/decision.json"} | {f"files/{f['path']}" for f in patch["files"] if f["op"] == "write"}
        if names != want:
            raise Refused("PATCH_INVENTORY", f"unexpected={sorted(names - want)[:3]} missing={sorted(want - names)[:3]}")
        dec_bytes = zf.read("cre/decision.json")
        if _sha(dec_bytes) != patch["cre_decision_sha256"]:
            raise Refused("PATCH_HASH_MISMATCH", "cre/decision.json")
        for f in patch["files"]:
            if f["op"] == "write" and _sha(zf.read(f"files/{f['path']}")) != f["sha256"]:
                raise Refused("PATCH_HASH_MISMATCH", f["path"])
        dec = json.loads(dec_bytes)
        if dec.get("decision") != ELIGIBLE or dec.get("candidate_revision") != target or \
                dec.get("baseline_revision") != base:
            raise Refused("PATCH_CRE_DECISION", f"{dec.get('decision_id')}: {dec.get('decision')} for "
                                                f"{str(dec.get('baseline_revision'))[:12]}..{str(dec.get('candidate_revision'))[:12]}")
        live = root / "releases" / base
        for name in ("baseline_sha256", "candidate_sha256"):
            value = dec.get(name)
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise Refused("PATCH_CRE_TREE_IDENTITY", f"missing or invalid {name}")
        if _release_sha256(live) != dec["baseline_sha256"]:
            raise Refused("PATCH_BASE_DRIFT", "whole release differs from the reviewed baseline")
        pol = yaml.safe_load((live / "config/factory/reliability-policy.yaml").read_text())
        globs = pol["security"]["protected_path_globs"]
        prot = [f["path"] for f in patch["files"] if _match(f["path"], globs)]
        if prot:
            raise Refused("PATCH_PROTECTED_PATH", ", ".join(prot[:5]))
        for f in patch["files"]:
            p = _inside(live, f["path"])
            if f["base_sha256"] is None:
                if p.exists() or p.is_symlink():
                    raise Refused("PATCH_BASE_DRIFT", f"{f['path']} already exists")
            elif not p.is_file() or _sha(p.read_bytes()) != f["base_sha256"]:
                raise Refused("PATCH_BASE_DRIFT", f["path"])
        staged = root / "releases" / f".staging-{target}"
        if staged.exists():
            shutil.rmtree(staged)
        shutil.copytree(live, staged, symlinks=True)
        for f in patch["files"]:
            p = _inside(staged, f["path"])
            if f["op"] == "delete":
                p.unlink()
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(zf.read(f"files/{f['path']}"))
            p.chmod(0o755 if f["mode"] == "755" else 0o644)
        if _release_sha256(staged) != dec["candidate_sha256"]:
            raise Refused("PATCH_TARGET_DRIFT", "staged release differs from the reviewed candidate")
        if checks is None and not preflight_cmd:
            raise Refused("PATCH_NO_PREFLIGHT", "the local truthful preflight command is not configured")
        results = checks(staged, patch["regression"]) if checks else \
            _checks_default(staged, patch["regression"], preflight_cmd)
        rec["checks"] = results
        if not results or any(r["exit_code"] != 0 for r in results):
            raise Refused("PATCH_CHECKS_FAILED", ", ".join(r["check"] for r in results if r["exit_code"] != 0))
        if _release_sha256(staged) != dec["candidate_sha256"]:
            raise Refused("PATCH_TARGET_DRIFT", "local checks changed the reviewed candidate")
        if _current(root) != base or _release_sha256(live) != dec["baseline_sha256"]:
            raise Refused("PATCH_BASE_DRIFT", "current release changed during local checks")
        staged.rename(root / "releases" / target)
        staged = None
        _switch(root, target)
        return _record(root, rec | {"decision": "ACTIVATED", "code": "PATCH_OK", "current": target})
    except Refused as e:
        return _record(root, rec | {"decision": "REFUSED", "code": e.code, "reason": e.reason[:300],
                                    "current": _current(root)})
    except (KeyError, ValueError, zipfile.BadZipFile) as e:
        return _record(root, rec | {"decision": "REFUSED", "code": "PATCH_MALFORMED", "reason": str(e)[:300],
                                    "current": _current(root)})
    finally:
        if staged is not None and staged.exists():
            shutil.rmtree(staged)


def rollback(install_root: Path) -> dict:
    """Point `current` back to the release that was current before the last activation still in effect."""
    with _import_lock(Path(install_root)):
        return _rollback(install_root)


def _rollback(install_root: Path) -> dict:
    root = Path(install_root)
    log = root / "imports/log.jsonl"
    acts = [json.loads(x) for x in log.read_text().splitlines() if x.strip()] if log.is_file() else []
    cur = _current(root)
    last = next((a for a in reversed(acts) if a.get("decision") == "ACTIVATED" and a.get("current") == cur), None)
    if last is None or not (root / "releases" / str(last["previous"])).is_dir():
        return _record(root, {"decision": "ROLLBACK_REFUSED", "code": "NO_ACTIVATION_TO_UNDO", "current": cur,
                              "at": utc_now()})
    _switch(root, last["previous"])
    return _record(root, {"decision": "ROLLED_BACK", "code": "ROLLBACK_OK", "from": cur, "current": last["previous"],
                          "patch_id": last.get("patch_id"), "at": utc_now()})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.offline.patch", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--repo", type=Path, required=True)
    b.add_argument("--base", required=True)
    b.add_argument("--target", required=True)
    b.add_argument("--regression", action="append", required=True)
    b.add_argument("--cre-decision", type=Path, required=True)
    b.add_argument("--approver", required=True)
    b.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("sign")
    s.add_argument("bundle", type=Path)
    s.add_argument("--key", type=Path, required=True)
    s.add_argument("--agent", action="store_true")
    i = sub.add_parser("import")
    i.add_argument("bundle", type=Path)
    i.add_argument("--install-root", type=Path, required=True)
    i.add_argument("--allowed-signers", type=Path, required=True)
    i.add_argument("--preflight-cmd", required=True)
    r = sub.add_parser("rollback")
    r.add_argument("--install-root", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        res = build(a.repo, a.base, a.target, a.regression, a.cre_decision, a.approver, a.out)
    elif a.cmd == "sign":
        res = {"signature": str(sign(a.bundle, a.key, a.agent))}
    elif a.cmd == "import":
        res = import_patch(a.bundle, install_root=a.install_root, allowed_signers=a.allowed_signers,
                           preflight_cmd=a.preflight_cmd)
    else:
        res = rollback(a.install_root)
    print(json.dumps(res))
    return 0 if res.get("decision") not in ("REFUSED", "ROLLBACK_REFUSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
