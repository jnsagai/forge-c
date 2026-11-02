"""Feature 016 OB-T005: fact statuses, gaps, canonical hash and package writing."""
import pytest

from forge_factory.onboarding import facts as F

S1 = F.Source("file", "inputs/vendor/include/stm32n657xx.h", line=10, value="0x52001000")
S2 = F.Source("doc", "inputs/rm-memory-map.md", page=180, value="0x52001000")
S3 = F.Source("doc", "inputs/rm-memory-map.md", page=180, value="0x42001000")


def test_fact_statuses():
    assert F.agree("base_address", "m", "q", S1, S2).status == "DERIVED"
    c = F.agree("base_address", "m", "which base?", S1, S3)
    assert c.status == "CONFLICT" and c.value is None and c.owner_question == "which base?"
    with pytest.raises(F.PackageError):
        F.derived("instance", None, "m", S1)
    with pytest.raises(F.PackageError):
        F.derived("instance", "USART1", "m")
    with pytest.raises(F.PackageError):
        F.conflict("base_address", "m", "q", S1, S2)                    # same values: not a conflict


def _pkg(facts, assumptions=(), authored=(), missing=()):
    return F.assemble("WO-T", [{"path": "inputs/a.md", "role": "rm", "sha256": "1" * 64}], "abcdef1", "HAL_STANDALONE",
                      list(facts), list(authored), list(assumptions), {"derived_from": {}}, {}, list(missing))


def test_gaps_and_blocking():
    a = F.Assumption("ASM-CLOCK-USART1", "HAL_RCCEx_GetPeriphCLKFreq", "not delivered", ["USART_BRR"])
    p = _pkg([F.agree("base_address", "m", "q", S1, S3), F.not_derived("mm_page", "m", "page?"),
              F.derived("instance", "USART1", "m", F.Source("workorder", "target.instance"))], [a])
    kinds = [(g["id"], g["kind"], g["ref"], g["blocks_approval"]) for g in p["gaps"]]
    assert kinds == [("GAP-OB-001", "CONFLICT", "base_address", True), ("GAP-OB-002", "NOT_DERIVED", "mm_page", False),
                     ("GAP-OB-003", "ASSUMPTION_UNCONFIRMED", "ASM-CLOCK-USART1", True)]
    assert p["status"] == "READY_FOR_OWNER"
    assert _pkg([], missing=[("Inc/x.h", "build")])["status"] == "BLOCKED"


def test_hash_is_stable_and_sensitive(tmp_path):
    f = [F.derived("instance", "USART1", "m", F.Source("workorder", "target.instance")),
         F.derived("time_base", "HAL_GetTick", "m", F.Source("file", "a.c", line=3))]
    p1, p2 = _pkg(f), _pkg(list(reversed(f)))
    assert p1["sha256"] == p2["sha256"] and p1["created_at"] != "" and F.canonical_hash(p1) == p1["sha256"]
    p3 = _pkg([f[0], F.derived("time_base", "HAL_GetTick", "m", F.Source("file", "a.c", line=4))])
    assert p3["sha256"] != p1["sha256"]
    F.write_package(tmp_path, p1)
    assert F.read_package(tmp_path)["sha256"] == p1["sha256"] and F.value(p1, "instance") == "USART1"
    p1["facts"][0]["value"] = "USART2"                                   # edited after hashing
    with pytest.raises(F.PackageError, match="HASH_MISMATCH"):
        F.write_package(tmp_path, p1)
    with pytest.raises(F.PackageError, match="INVALID"):
        F.write_package(tmp_path, {**_pkg(f), "status": "MAYBE"})
