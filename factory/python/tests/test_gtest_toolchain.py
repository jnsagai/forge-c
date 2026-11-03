"""Owner 2026-11-03: the pinned GoogleTest/GoogleMock 1.11.0 toolchain is verified on every use."""
import json
import shutil

import pytest

from forge_factory import gtest_toolchain as G


def _fake(tmp_path, **over):
    base = tmp_path / "googletest-1.11.0"
    (base / "lib").mkdir(parents=True)
    (base / "include").mkdir()
    libs = {}
    for n in G.LIBS:
        (base / "lib" / n).write_bytes(n.encode())
        libs[n] = G.sha256_file(base / "lib" / n)
    rec = {"version": G.VERSION, "license": G.LICENSE, "source_tree_sha256": G.SOURCE_TREE_SHA256,
           "libraries_sha256": libs, "cxx_flags": ["--gcc-install-dir=/x"], **over}
    (base / "forge-toolchain.json").write_text(json.dumps(rec))
    return base


def test_verified_toolchain_loads(tmp_path):
    t = G.load(_fake(tmp_path))
    assert t["gtest"].endswith("libgtest.a") and t["cxx_flags"] == ["--gcc-install-dir=/x"]


@pytest.mark.parametrize("over,code", [({"version": "1.12.0"}, "GTEST_VERSION_MISMATCH"),
                                       ({"source_tree_sha256": "0" * 64}, "GTEST_SOURCE_NOT_PINNED"),
                                       ({"license": "MIT"}, "GTEST_SOURCE_NOT_PINNED")])
def test_unpinned_record_refused(tmp_path, over, code):
    with pytest.raises(G.GtestToolchainError, match=code):
        G.load(_fake(tmp_path, **over))


def test_changed_library_refused(tmp_path):
    base = _fake(tmp_path)
    (base / "lib/libgmock.a").write_bytes(b"tampered")
    with pytest.raises(G.GtestToolchainError, match="GTEST_LIB_HASH_MISMATCH:libgmock.a"):
        G.load(base)


def test_missing_toolchain_named(tmp_path):
    with pytest.raises(G.GtestToolchainError, match="GTEST_TOOLCHAIN_MISSING"):
        G.load(tmp_path / "none")


def test_installed_toolchain_is_the_pin():
    if not (G.root() / "forge-toolchain.json").is_file() or shutil.which("clang++") is None:
        pytest.skip("pinned googletest toolchain not installed on this host")
    assert G.load()["record"]["version"] == "1.11.0"
