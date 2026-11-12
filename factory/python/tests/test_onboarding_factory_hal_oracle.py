"""Feature 016 OB-T068 (owner decision 2026-11-11): the generated WWDG and CRC factory-HAL texts are compared with the
hand-written overlays (wwdg.yaml/crc.yaml `hal_*`, `semantic_required_operations`); every difference is listed in
config/factory/onboarding/factory-hal-oracle-exceptions.yaml with a reason - no unlisted difference, no stale entry."""
import pytest
from forge_factory import onboarding as OB
from forge_factory.onboarding import oracle as O
from forge_factory.peripheral import load
from onboarding_util import factory_hal_example, need_inputs


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    load.cache_clear()
    yield tmp_path
    load.cache_clear()


@pytest.mark.parametrize("pid", ["wwdg", "crc"])
def test_every_difference_from_the_hand_factory_hal_texts_is_explained(pid, state):
    need_inputs()
    ex = factory_hal_example(state, pid)
    pkg = OB.derive(ex, ex.name, author_missing=False)
    assert pkg["driver_style"] == "HAL_ON_LL" and pkg["status"] == "READY_FOR_OWNER"
    diffs = {d["key"] for d in O.factory_hal_compare(pkg, pid)}
    listed = {k for (p, k) in O.factory_hal_exceptions() if p == pid}
    assert diffs - listed == set(), f"unexplained differences: {sorted(diffs - listed)}"
    assert listed - diffs == set(), f"stale exceptions (now equal): {sorted(listed - diffs)}"


def test_the_exceptions_file_is_complete_and_the_compare_sees_a_planted_change(state):
    exc = O.factory_hal_exceptions()
    assert all(e["reason"].strip() and e["reviewed_by"].strip() for e in exc.values())
    assert {k for (_p, k) in exc} <= set(O.FACTORY_HAL_KEYS)
    need_inputs()
    ex = factory_hal_example(state, "crc")
    pkg = OB.derive(ex, ex.name, author_missing=False)
    assert "hal_reset_example" not in {d["key"] for d in O.factory_hal_compare(pkg, "crc")}  # equal to the hand text
    pkg["texts"]["prompt"]["hal_reset_example"]["text"] += " changed"
    assert "hal_reset_example" in {d["key"] for d in O.factory_hal_compare(pkg, "crc")}
