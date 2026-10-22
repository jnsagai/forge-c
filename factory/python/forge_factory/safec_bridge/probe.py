"""F011-T004: Linux probe of the private SafeC checkout on this host, reported through the public boundary.

    python -m forge_factory.safec_bridge.probe --checkout <safec> --private-out <dir outside Forge-C> [--out <json>]

Runs, in the private checkout:
- the pinned toolchain's `cargo test --workspace --locked --offline --no-fail-fast`, with its own CARGO_HOME and
  target directory next to the private output;
- version and digest queries of the formal backends SafeC records (Kind 2, Z3, Frama-C, Why3, Alt-Ergo, CBMC).

Raw logs stay in `--private-out`. The repository receives only `provenance.public_summary` of counts, versions,
digests and the raw-log digest. A missing tool is MISSING, never assumed; a test failure stays a failure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, sha256_file, utc_now
from .provenance import public_summary

FORMAL_BIN = Path(os.environ.get("FORGE_FORMAL_BIN", "/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/"
                                                      "toolchains/formal/bin"))
TOOLS = ("kind2", "z3", "frama-c", "why3", "alt-ergo", "cbmc", "cvc5")
SUMMARY_KEYS = ("schema", "probed_at", "host", "checkout_head", "checkout_branch", "remote_main", "toolchain",
                "tests_passed", "tests_failed", "tests_ignored", "test_binaries", "cargo_exit", "raw_log_sha256",
                "tools_present", "tools_missing", "tool_versions", "status")


def _run(argv: list[str], cwd: Path, env: dict | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, errors="replace", timeout=timeout)


def tools() -> tuple[list[str], list[str], list[str]]:
    present, missing, versions = [], [], []
    for t in TOOLS:
        p = shutil.which(t) or (str(FORMAL_BIN / t) if (FORMAL_BIN / t).is_file() else None)
        if not p:
            missing.append(t)
            continue
        out = _run([p, "--version"], Path("/"), timeout=30)
        first = (out.stdout or out.stderr).strip().splitlines()[:1]
        present.append(t)
        versions.append(f"{t} {first[0][:80] if first else 'UNKNOWN'} sha256:{sha256_file(Path(p))[:16]}")
    return present, missing, versions


def probe(checkout: Path, private_out: Path) -> dict:
    private_out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "CARGO_HOME": str(private_out.parent / "cargo-home"),
           "CARGO_TARGET_DIR": str(private_out.parent / "target-probe")}
    cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo")
    tc = _run([cargo, "--version"], checkout, env).stdout.strip()
    res = _run([cargo, "test", "--workspace", "--locked", "--offline", "--no-fail-fast"], checkout, env, 3600)
    raw = private_out / "cargo-test.log"
    raw.write_text(res.stdout + "\n--- stderr ---\n" + res.stderr)
    counts = [tuple(map(int, m)) for m in re.findall(r"test result: \w+\. (\d+) passed; (\d+) failed; (\d+) ignored",
                                                     res.stdout)]
    present, missing, versions = tools()
    git = lambda *a: _run(["git", *a], checkout).stdout.strip()  # noqa: E731
    remote = _run(["git", "ls-remote", "origin", "refs/heads/main"], checkout).stdout.split()
    failed = sum(c[1] for c in counts)
    rec = {"schema": "forge-c/safec-linux-probe/1", "probed_at": utc_now(), "host": os.uname().nodename,
           "checkout_head": git("rev-parse", "HEAD"), "checkout_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
           "remote_main": remote[0] if remote else "UNKNOWN", "toolchain": tc,
           "tests_passed": sum(c[0] for c in counts), "tests_failed": failed,
           "tests_ignored": sum(c[2] for c in counts), "test_binaries": len(counts), "cargo_exit": res.returncode,
           "raw_log_sha256": sha256_file(raw), "tools_present": present, "tools_missing": missing,
           "tool_versions": versions, "status": "PASS" if res.returncode == 0 and not failed else "FAIL"}
    (private_out / "probe-private.json").write_text(pretty_json(rec))
    return public_summary(rec, SUMMARY_KEYS, private_root=checkout)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkout", type=Path, required=True)
    ap.add_argument("--private-out", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if a.private_out.resolve().is_relative_to(REPO_ROOT.resolve()):
        raise SystemExit("PRIVATE_OUT_INSIDE_PUBLIC_REPOSITORY")
    s = probe(a.checkout.resolve(), a.private_out.resolve())
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(pretty_json(s))
    print(json.dumps(s))
    return 0 if s["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
