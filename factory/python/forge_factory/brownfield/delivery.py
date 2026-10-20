"""Brownfield intake (US1, FR-001..FR-006): validate the delivery, fingerprint and store it outside the workspace,
resolve the scope to delivered functions, and build-check the in-scope code - all before any agent runs.

The store is `state/workorders/<wo>/delivered/` and mirrors the workspace paths the files will have once injected
(`software/...`, `inputs/vendor/include/...`); every stored file is read-only. Nothing is written into the workspace
here: the code enters only after SWE.1 is frozen (inject.py, FR-007)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, sha256_bytes, state_dir, utc_now
from . import MODES
from . import scope as S

CONTRACT = REPO_ROOT / "specs/008-brownfield-work-orders/contracts/brownfield-workorder.schema.json"
INTAKE_SCHEMA = "forge-c/delivery-intake/0.1"
CODE_DIRS = ("software/ll/", "software/hal/", "software/src/")


class DeliveryBlocked(ValueError):
    """Intake refused the delivery; the message lists the DELIVERY_* issues."""


def store_dir(wo: str) -> Path:
    return state_dir() / "workorders" / wo / "delivered"


def validate(delivery: dict) -> list[str]:
    """Contract errors of a delivery block (empty list: valid)."""
    import jsonschema

    schema = json.loads(CONTRACT.read_text())
    errs = [f"DELIVERY_SPEC_INVALID:{'/'.join(map(str, e.absolute_path)) or '-'}:{e.message[:120]}"
            for e in jsonschema.Draft202012Validator(schema).iter_errors(delivery)]
    if not errs and delivery["code_mode"] not in MODES:
        errs.append(f"DELIVERY_SPEC_INVALID:code_mode:{delivery['code_mode']}")
    return errs


def _resolve_source(src: str, example: Path) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(src))
    p = Path(expanded)
    if not p.is_absolute():
        p = (example / p) if (example / p).exists() else (REPO_ROOT / p)
    return p.resolve()


def _unpack(src: Path, tmp: Path) -> Path:
    """A delivery archive is unpacked into a scratch dir; members that would escape it are refused."""
    if src.is_dir():
        return src
    if src.suffixes[-2:] == [".tar", ".gz"] or src.suffix in (".tgz", ".tar"):
        with tarfile.open(src) as tf:
            for m in tf.getmembers():
                if m.issym() or m.islnk() or Path(m.name).is_absolute() or ".." in Path(m.name).parts:
                    raise DeliveryBlocked(f"DELIVERY_ARCHIVE_UNSAFE_MEMBER:{m.name}")
            tf.extractall(tmp, filter="data")
        return tmp
    raise DeliveryBlocked(f"DELIVERY_SOURCE_UNSUPPORTED:{src.name}")


def _pick(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    if root.resolve() not in p.parents or not p.is_file():
        raise DeliveryBlocked(f"DELIVERY_FILE_MISSING_OR_OUTSIDE_SOURCE:{rel}")
    return p


def build_check(files: dict[str, bytes], style: str, defines: list[str], secure: bool = False) -> dict:
    """Syntax/semantic check of the delivered code with the declared dependencies (FR-004): every delivered .c, and a
    translation unit per delivered header, compiled -fsyntax-only in a scratch copy of the layout. Factory-style code
    is checked with host clang; vendor (CMSIS) code with the target compiler arm-none-eabi-gcc (newlib headers)."""
    clang = shutil.which("clang") if style != "cmsis" else shutil.which("arm-none-eabi-gcc")
    if not clang:
        return {"status": "NOT_RUN", "command": [], "exit_code": None, "log_sha256": None, "warnings": 0,
                "reason": "compiler not found on PATH"}
    with tempfile.TemporaryDirectory(prefix="forge-bf-build-") as td:
        root = Path(td)
        for rel, data in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(data)
        incs = sorted({str((root / rel).parent) for rel in files})
        incs = [str(root / "inputs/vendor/include")] * any(r.startswith("inputs/vendor/include/") for r in files) + incs
        target = (["-mcpu=cortex-m55", "-mthumb"] + (["-mcmse"] if secure else []) if style == "cmsis" else [])
        base = [clang, "-std=c11", "-fsyntax-only", "-Wall", "-Wextra", *target,
                *[f"-I{i}" for i in dict.fromkeys(incs)], *[f"-D{d}" for d in defines]]
        units = []
        for rel in sorted(files):
            if rel.startswith(CODE_DIRS) and rel.endswith(".c"):
                units.append(root / rel)
            elif rel.startswith(CODE_DIRS) and rel.endswith(".h"):
                tu = root / f"_check_{Path(rel).stem}.c"
                tu.write_text(f'#include "{Path(rel).name}"\n')
                units.append(tu)
        log, rc, warnings = [], 0, 0
        for u in units:
            r = subprocess.run([*base, str(u)], capture_output=True, text=True, timeout=120, check=False)
            out = (r.stdout + r.stderr).replace(td, "<delivery>")
            log.append(f"$ clang ... {u.relative_to(root)}\n{out}")
            warnings += len(re.findall(r": warning: ", out))
            rc = rc or r.returncode
        text = "\n".join(log)
        return {"status": "PASS" if rc == 0 else "FAIL", "command": [Path(base[0]).name, *base[1:]],
                "exit_code": rc, "log_sha256": sha256_bytes(text.encode()), "warnings": warnings, "log": text[-6000:]}


def intake(spec: dict, example: Path, wo: str, extra: dict[str, bytes] | None = None) -> dict:
    """Run intake for a work order spec with a `delivery` block. Returns the intake record (status ACCEPTED) and
    leaves the delivery in the read-only store; raises DeliveryBlocked (after writing a BLOCKED record) otherwise.
    `extra`: read-only files the delivery builds against but does not own (e.g. the HAL's provided LL header)."""
    d = spec["delivery"]
    store = store_dir(wo)
    blank = [k for k in ("origin", "licence") if k in d and not str(d[k]).strip()]  # FR-005, named explicitly
    issues = [f"DELIVERY_{k.upper()}_MISSING" for k in blank] + \
        [e for e in validate(d) if not any(e.startswith(f"DELIVERY_SPEC_INVALID:{k}:") for k in blank)]
    if not issues and d["code_mode"] == "FIX_ALLOWED" and not d["licence_allows_modification"]:
        issues.append("DELIVERY_MODE_FORBIDDEN_BY_LICENCE:FIX_ALLOWED")
    files: dict[str, bytes] = {}
    records: list[dict] = []
    resolved: list[dict] = []
    excluded: list[str] = []
    build = {"status": "NOT_RUN", "command": [], "exit_code": None, "log_sha256": None, "warnings": 0}
    if not issues:
        with tempfile.TemporaryDirectory(prefix="forge-bf-src-") as td:
            try:
                root = _unpack(_resolve_source(d["source"], example), Path(td))
                for f in d["files"]:
                    files[f["to"]] = _pick(root, f["from"]).read_bytes()
                    records.append({"path": f["to"], "role": "delivered_code", "origin": d["origin"],
                                    "licence": d["licence"]})
                for dep in d.get("dependencies") or []:
                    droot = _unpack(_resolve_source(dep["source"], example), Path(td) / "dep") \
                        if dep.get("source") else root
                    files[dep["to"]] = _pick(droot, dep["from"]).read_bytes()
                    records.append({"path": dep["to"], "role": "delivered_dependency", "origin": dep["origin"],
                                    "licence": dep["licence"]})
            except (DeliveryBlocked, OSError, tarfile.TarError) as exc:
                issues.append(str(exc) if isinstance(exc, DeliveryBlocked) else f"DELIVERY_SOURCE_UNREADABLE:{exc}")
    if not issues:
        for r in records:
            r["sha256"] = sha256_bytes(files[r["path"]])
            r["bytes"] = len(files[r["path"]])
        defs = [x for r in records if r["role"] == "delivered_code"
                for x in S.index(files[r["path"]].decode("utf-8", errors="replace"), r["path"])]
        by_name: dict[str, S.Definition] = {}
        for x in defs:
            by_name.setdefault(x.name, x)
        for name in d["scope"]["functions"]:
            x = by_name.get(name)
            if x is None:
                issues.append(f"DELIVERY_SCOPE_FUNCTION_NOT_FOUND:{name}")
            else:
                resolved.append({"name": name, "file": x.file, "line": x.line, "kind": x.kind})
        excluded = sorted({x.name for x in defs} - set(d["scope"]["functions"]))
    if not issues:
        build = build_check({**(extra or {}), **files}, d["build"]["style"], d["build"].get("defines") or [],
                            bool(d["build"].get("secure")))
        if build["status"] != "PASS":
            issues.append(f"DELIVERY_BUILD_{build['status']}")
    rec = {"schema": INTAKE_SCHEMA, "work_order": wo, "checked_at": utc_now(),
           "status": "BLOCKED" if issues else "ACCEPTED", "issues": issues, "code_mode": d.get("code_mode"),
           "origin": d.get("origin"), "licence": d.get("licence"), "files": records, "build_check": build}
    if store.exists():
        for p in sorted(store.rglob("*"), reverse=True):  # a re-prepared work order replaces its own store only
            p.chmod(0o755 if p.is_dir() else 0o644)
        shutil.rmtree(store)
    store.mkdir(parents=True)
    (store / "intake.json").write_text(pretty_json(rec))
    (store / "scope.json").write_text(pretty_json({"schema": "forge-c/delivery-scope/0.1", "functions": resolved,
                                                   "excluded": excluded, "excluded_count": len(excluded)}))
    if issues:
        raise DeliveryBlocked(";".join(issues))
    for rel, data in files.items():
        p = store / "files" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        p.chmod(0o444)
    return rec


def stored(wo: str) -> dict[str, bytes]:
    """{workspace path: bytes} of the stored delivery (code and dependencies)."""
    base = store_dir(wo) / "files"
    return {str(p.relative_to(base)): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}
