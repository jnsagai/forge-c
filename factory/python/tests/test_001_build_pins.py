"""specs/001-factory T-006 (pinned Fabro/providers/models/sandbox) and T-008 (C11 target + native CMake builds)."""
import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
LIVE = os.environ.get("FORGE_FABRO_LIVE") == "1"


def _sha_objects(build: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(build.rglob("*.o"))}


@pytest.mark.skipif(not all(shutil.which(t) for t in ("cmake", "ninja", "arm-none-eabi-gcc")), reason="toolchain")
def test_t008_reproducible_cortex_m55_target_build_via_cmake(tmp_path):
    shas = []
    for name in ("a", "b"):  # two independent build trees must give bit-identical objects and archive
        b = tmp_path / name
        cfg = subprocess.run(["cmake", "-S", str(REPO), "-B", str(b), "-G", "Ninja", "-DBUILD_TESTING=OFF",
                              "-DCMAKE_BUILD_TYPE=MinSizeRel",
                              f"-DCMAKE_TOOLCHAIN_FILE={REPO / 'cmake/arm-none-eabi-cortex-m55.cmake'}"],
                             capture_output=True, text=True)
        assert cfg.returncode == 0, cfg.stderr[-500:]
        bld = subprocess.run(["cmake", "--build", str(b)], capture_output=True, text=True)
        assert bld.returncode == 0, bld.stdout[-800:]
        objs = _sha_objects(b)
        assert objs, "no target objects"
        lib = next(b.rglob("libforge_rcc_demo.a"))
        shas.append((objs, hashlib.sha256(lib.read_bytes()).hexdigest()))
        attrs = subprocess.run(["arm-none-eabi-readelf", "-A", str(next(b.rglob("*.o")))], capture_output=True,
                               text=True).stdout
        assert re.search(r"Tag_CPU_name: \"?Cortex-M55", attrs, re.I), attrs[:300]
    assert shas[0] == shas[1]  # reproducible


@pytest.mark.skipif(not all(shutil.which(t) for t in ("cmake", "ninja", "clang", "ctest")), reason="toolchain")
def test_t008_native_c11_build_and_tests_via_cmake(tmp_path):
    b = tmp_path / "native"
    assert subprocess.run(["cmake", "-S", str(REPO), "-B", str(b), "-G", "Ninja", "-DCMAKE_C_COMPILER=clang"],
                          capture_output=True).returncode == 0
    assert subprocess.run(["cmake", "--build", str(b)], capture_output=True).returncode == 0
    t = subprocess.run(["ctest", "--test-dir", str(b), "--output-on-failure"], capture_output=True, text=True)
    assert t.returncode == 0 and "100% tests passed" in t.stdout, t.stdout[-500:]


@pytest.mark.skipif(not LIVE, reason="live stack disabled")
def test_t006_pinned_fabro_models_provider_and_sandbox():
    import httpx

    fabro = os.environ["FORGE_FABRO_BIN"]
    v = subprocess.run([fabro, "--version"], capture_output=True, text=True).stdout
    assert "0.362.0" in v, v
    assert httpx.get("http://127.0.0.1:11435/api/version", timeout=5).json()["version"] == "0.34.0"
    tags = {m["name"]: m["digest"] for m in httpx.get("http://127.0.0.1:11435/api/tags", timeout=5).json()["models"]}
    assert tags["qwen3:8b"].startswith("500a1f067a9f") and tags["qwen3-coder:30b"].startswith("06c1097efce0")
    assert httpx.get("http://127.0.0.1:11436/health", timeout=5).json()["status"] == "ok"
    cfg = Path(os.environ["FORGE_FABRO_CONFIG"]).read_text()
    assert 'base_url = "http://127.0.0.1:11436/v1"' in cfg and "reasoning_by_default = false" in cfg  # via gateway
    assert '[server.sandbox.providers.local]' in cfg and 'max_concurrent_runs = 1' in cfg
    assert 'default_model = "qwen3:8b"' in cfg and '127.0.0.1:32290' in cfg  # isolated server, pinned default
