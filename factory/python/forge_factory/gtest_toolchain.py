"""Pinned GoogleTest/GoogleMock toolchain (owner decision 2026-11-03: SWE.4 requirement-based unit tests are GoogleTest
TEST()s against the C driver, GoogleMock where a design seam must be mocked).

The factory never uses a system libgtest: it uses the 1.11.0 build made by scripts/build_googletest.sh with the pinned
LLVM 19 clang++ into `$FORGE_DATA_ROOT/toolchains/googletest-1.11.0` (override: FORGE_GTEST_ROOT). The build record
`forge-toolchain.json` is checked on every use: version, licence, source-tree sha256 (the pin below; identical on loop10
and Omniverse2) and the sha256 of each static library (a library changed after the build is refused).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .common import data_root, sha256_file

VERSION = "1.11.0"
LICENSE = "BSD-3-Clause"
# sha256 over the sorted (path, sha256) list of /usr/src/googletest (Debian googletest 1.11.0-3), see the build script
SOURCE_TREE_SHA256 = "20f0358aad458d6d85beb7fb9348fa0c279d9eb5522befd66c4489bcce95e238"
LIBS = ("libgtest.a", "libgmock.a")


class GtestToolchainError(ValueError):
    pass


def root() -> Path:
    return Path(os.environ.get("FORGE_GTEST_ROOT") or data_root() / "toolchains" / f"googletest-{VERSION}")


def load(base: Path | None = None) -> dict:
    """The verified toolchain: include dir, library paths, extra clang++ flags and the build record."""
    base = Path(base or root())
    rec_p = base / "forge-toolchain.json"
    if not rec_p.is_file():
        raise GtestToolchainError(f"GTEST_TOOLCHAIN_MISSING:{base} (run scripts/build_googletest.sh <toolchains dir>)")
    rec = json.loads(rec_p.read_text())
    if rec.get("version") != VERSION:
        raise GtestToolchainError(f"GTEST_VERSION_MISMATCH:{rec.get('version')} (pinned {VERSION})")
    if rec.get("license") != LICENSE or rec.get("source_tree_sha256") != SOURCE_TREE_SHA256:
        raise GtestToolchainError("GTEST_SOURCE_NOT_PINNED (source tree sha256 or licence differs from the pin)")
    libs = {}
    for n in LIBS:
        p = base / "lib" / n
        want = (rec.get("libraries_sha256") or {}).get(n)
        if not p.is_file() or sha256_file(p) != want:
            raise GtestToolchainError(f"GTEST_LIB_HASH_MISMATCH:{n}")
        libs[n] = str(p)
    return {"root": str(base), "include": str(base / "include"), "gtest": libs["libgtest.a"],
            "gmock": libs["libgmock.a"], "cxx_flags": list(rec.get("cxx_flags") or []), "record": rec,
            "record_sha256": sha256_file(rec_p)}


def build(c_compiler: str, c_args: list[str], c_sources: list[str], test_cpp: str, exe: str, *, flags: list[str],
          includes: list[str], workdir: str):
    """Build a GoogleTest program for the verifiers that compile in-process (EASA coverage/mutation): the C sources
    with `c_compiler` (as C), the test with clang++ (C++17), linked with the pinned gtest/gmock + gtest_main.
    Returns a subprocess.CompletedProcess-like object of the first failing step (or the link)."""
    import subprocess

    t = load()
    objs = []
    for i, src in enumerate(c_sources):
        o = str(Path(workdir) / f"gt_c{i}.o")
        b = subprocess.run([c_compiler, *c_args, *flags, *includes, "-c", src, "-o", o], capture_output=True, text=True)
        if b.returncode:
            return b
        objs.append(o)
    o = str(Path(workdir) / "gt_test.o")
    b = subprocess.run(["clang++", "-std=c++17", "-O0", "-w", *t["cxx_flags"], *flags, *includes, "-isystem",
                        t["include"], "-c", test_cpp, "-o", o], capture_output=True, text=True)
    if b.returncode:
        return b
    main = str(Path(t["gtest"]).with_name("libgtest_main.a"))
    return subprocess.run(["clang++", *t["cxx_flags"], *flags, o, *objs, t["gmock"], t["gtest"], main, "-lpthread",
                           "-o", exe], capture_output=True, text=True)


def c_name(symbol: str) -> str:
    """The C identifier of an llvm-cov function record: '<file>:<name>' for a static function of a C unit, and the
    Itanium-mangled internal-linkage name ('t.cpp:_ZL14LL_IWDG_Enablev') of a static inline driver function compiled in
    a GoogleTest (C++) translation unit."""
    import re

    n = symbol.split(":")[-1]
    m = re.match(r"_ZL(\d+)", n)
    return n[m.end():m.end() + int(m.group(1))] if m else n
