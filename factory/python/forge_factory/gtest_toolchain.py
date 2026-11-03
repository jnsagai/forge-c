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
