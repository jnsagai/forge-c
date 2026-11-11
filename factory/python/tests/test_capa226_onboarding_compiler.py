"""CAPA-226 (owner lane 2026-11-11, SPI/TIM factory-HAL packages): the onboarding derivation found the Arm compiler
only on PATH. The line launcher's PATH has none, so the package derived at launch would be BLOCKED (file map, base
address, LL API not derived) and could never match the owner-signed package; and two different compilers on PATH give
two different package hashes. The derivation now uses one canonical compiler: FORGE_ONBOARDING_GCC, else the factory's
product toolchain (data root toolchains/sysroot), PATH only as the last resort."""
from forge_factory.onboarding import identity


def test_the_factory_toolchain_is_used_without_any_compiler_on_path(tmp_path, monkeypatch):
    gcc = tmp_path / "toolchains/sysroot/usr/bin/arm-none-eabi-gcc"
    gcc.parent.mkdir(parents=True)
    gcc.write_text("#!/bin/sh\n")
    gcc.chmod(0o755)
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("FORGE_ONBOARDING_GCC", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert identity.compiler() == str(gcc)


def test_the_factory_toolchain_wins_over_another_compiler_on_path(tmp_path, monkeypatch):
    gcc = tmp_path / "toolchains/sysroot/usr/bin/arm-none-eabi-gcc"
    other = tmp_path / "other/bin/arm-none-eabi-gcc"
    for p in (gcc, other):
        p.parent.mkdir(parents=True)
        p.write_text("#!/bin/sh\n")
        p.chmod(0o755)
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("PATH", f"{other.parent}:/usr/bin:/bin")
    assert identity.compiler() == str(gcc)
    monkeypatch.setenv("FORGE_ONBOARDING_GCC", str(other))
    assert identity.compiler() == str(other)
