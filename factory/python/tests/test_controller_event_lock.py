import pytest
from forge_factory.events import emit as module


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True, "1", 61])
def test_bounded_event_lock_rejects_bad_limits_before_creating_files(tmp_path, monkeypatch, bad):
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "not-created"))
    with pytest.raises(ValueError):
        module.emit("human", "WARN", "PRIVATE", lock_timeout_s=bad)
    assert not (tmp_path / "not-created").exists()


def test_zero_timeout_uncontended_append_preserves_normal_event_projection(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    record = module.emit("human", "WARN", "PRIVATE_BOUNDED", payload_ref="PRIVATE-ID", lock_timeout_s=0)
    stored = json.loads((tmp_path / "events/factory-events.jsonl").read_text())
    assert stored == record and stored["payload_ref"] == "PRIVATE-ID"
    assert "lock_timeout_s" not in stored


def test_real_held_event_lock_times_out_and_closes_own_descriptor(tmp_path, monkeypatch):
    import fcntl
    import os
    import time

    directory = tmp_path / "events"
    directory.mkdir()
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(directory))
    fd = os.open(directory / "factory-events.jsonl", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    start = time.monotonic()
    try:
        with pytest.raises(module.EventLockTimeout):
            module.emit("human", "WARN", "PRIVATE_LOCKED", lock_timeout_s=0.05)
        assert time.monotonic() - start < 0.5
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    module.emit("human", "WARN", "PRIVATE_RESTORED", lock_timeout_s=0)
