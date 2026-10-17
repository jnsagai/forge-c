"""EASA-T016/T040/T041/T046 — independent oracle provenance and holdout custody.

An oracle (expected results of a test) is INDEPENDENT only if it traces to approved requirement/HSI/manual sources
and none of its inputs is the implementation under test. Contamination is detected from evidence, not declared:
  * an assertion uses a symbol DEFINED by an implementation file (shared source: a wrong generated macro is then
    "verified" by itself — finding F-01 of the r101/r102 audit);
  * an oracle source digest equals an implementation file digest (expected values copied from the code);
  * the oracle author saw the implementation (`implementation_hash_seen`) or has an author role;
  * no approved requirement reference / source digest.
Holdout fixtures live in a vault handed to the verifier OS identity (rootless Podman sub-UID): author processes,
which run as the owner account, are refused by the policy check AND by the kernel.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
from pathlib import Path

from ..common import sha256_bytes, sha256_file, utc_now
from ..events.emit import emit
from ..reliability import isolation
from . import contracts

AUTHOR_ROLES = ("swe1-author", "swe2-author", "swe3-author", "swe4-author", "swe5-author", "swe6-author",
                "repair", "author")
VERIFIER_ROLES = ("easa-verifier", "verifier", "oracle-builder")
ASSERT_RX = re.compile(r"^\s*(?:CHECK|EXPECT\w*|ASSERT\w*|TEST_ASSERT\w*|assert|TCHECK|CHECK_EQ)\s*\((.*)$", re.M)
DEFINE_RX = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)", re.M)


def defined_symbols(texts: dict[str, str]) -> dict[str, str]:
    out = {}
    for path, t in texts.items():
        for m in DEFINE_RX.finditer(t):
            out.setdefault(m.group(1), path)
    return out


def shared_symbols(test_text: str, impl: dict[str, str], oracle_sources: dict[str, str]) -> list[dict]:
    """Implementation-defined symbols used inside assertions and NOT also defined by an independent source."""
    impl_defs = defined_symbols(impl)
    indep = set(defined_symbols(oracle_sources))
    hits: dict[str, dict] = {}
    for m in ASSERT_RX.finditer(test_text):
        for sym in re.findall(r"[A-Za-z_]\w*", m.group(1)):
            if sym in impl_defs and sym not in indep:
                hits.setdefault(sym, {"symbol": sym, "defined_in": impl_defs[sym], "uses": 0})["uses"] += 1
    return sorted(hits.values(), key=lambda h: -h["uses"])


def assess(rec: dict, *, test_text: str = "", impl: dict[str, str] | None = None,
           oracle_sources: dict[str, str] | None = None, approved_digests: set[str] | None = None) -> dict:
    """Return the record with independence_status / contamination_reason derived from the evidence."""
    impl = impl or {}
    reasons = []
    impl_digests = {sha256_bytes(t.encode()) for t in impl.values()}
    if rec.get("implementation_hash_seen"):
        reasons.append(f"ORACLE_AUTHOR_SAW_IMPLEMENTATION:{rec['implementation_hash_seen'][:12]}")
    if str(rec.get("author_role", "")).lower() in AUTHOR_ROLES:
        reasons.append(f"ORACLE_BY_AUTHOR_ROLE:{rec['author_role']}")
    if set(rec.get("source_digests") or []) & impl_digests:
        reasons.append("ORACLE_SOURCE_IS_IMPLEMENTATION")
    if not rec.get("requirement_refs"):
        reasons.append("NO_REQUIREMENT_REFERENCE")
    if approved_digests is not None and not set(rec.get("source_digests") or []) <= approved_digests:
        reasons.append("SOURCE_NOT_APPROVED_BASELINE")
    shared = shared_symbols(test_text, impl, oracle_sources or {}) if test_text else []
    if shared:
        reasons.append("REJECT_ORACLE_CONTAMINATED:shared implementation symbols " +
                       ",".join(f"{s['symbol']}@{Path(s['defined_in']).name}" for s in shared[:5]))
    out = dict(rec, independence_status="CONTAMINATED" if reasons else "INDEPENDENT",
               contamination_reason="; ".join(reasons) or None)
    out["schema_issues"] = contracts.errors("oracle-provenance", {k: v for k, v in out.items() if k != "schema_issues"})
    return out


class HoldoutVault:
    """Holdout fixtures and expected outcomes in custody of the verifier OS identity."""

    def __init__(self, root: Path, store=None):
        self.root, self.store = Path(root), store

    def deposit(self, files: dict[str, bytes]) -> dict[str, str]:
        self.root.mkdir(parents=True, exist_ok=True)
        digests = {}
        for rel, data in files.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            p.chmod(0o400)
            digests[rel] = sha256_bytes(data)
        for d in [self.root, *[p for p in self.root.rglob("*") if p.is_dir()]]:
            d.chmod(stat.S_IRUSR | stat.S_IXUSR)
        isolation.hand_over("verifier", self.root)
        if self.store is not None:
            self.store.append("oracle", f"holdout:{self.root.name}", {"digests": digests, "custody": isolation.level()},
                              actor="oracle-builder")
        return digests

    def read(self, role: str, rel: str) -> bytes:
        """Policy gate in front of the kernel check: only verifier roles may read; every denial is audited."""
        if role not in VERIFIER_ROLES:
            emit("security", "WARN", f"holdout read denied for role {role}", tool_id="easa-holdout")
            if self.store is not None:
                self.store.append("finding", f"holdout:{self.root.name}", {"code": "HOLDOUT_ACCESS_DENIED", "role": role,
                                                                           "path": rel, "at": utc_now()}, actor=role)
            raise PermissionError(f"HOLDOUT_ACCESS_DENIED:{role}")
        return (self.root / rel).read_bytes()

    def os_readable_by_owner(self, rel: str) -> bool:
        try:
            with open(self.root / rel, "rb") as f:
                f.read(1)
            return True
        except PermissionError:
            return False

    def digest_unchanged(self, expected: dict[str, str]) -> list[str]:
        """Tamper check performed by the verifier identity (owner cannot read the files)."""
        if not isolation.available():
            return [rel for rel, h in expected.items() if sha256_file(self.root / rel) != h]
        bad = []
        for rel, h in expected.items():
            r = isolation.execute("verifier", ["sha256sum", str(self.root / rel)], cwd=Path("/"), env=dict(os.environ),
                                  writable=[], readable=[self.root])
            if r.returncode != 0 or r.stdout.decode().split()[:1] != [h]:
                bad.append(rel)
        return bad

    def destroy(self) -> None:
        if isolation.available():
            isolation.remove(self.root)
        else:
            shutil.rmtree(self.root, ignore_errors=True)
