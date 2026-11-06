import json
import zipfile

import pytest
from forge_factory.offline import controller_export as C


def case():
    return dict(
        schema="forge-c/controller-case/1",
        case_id="case-" + "a" * 24,
        classification="CONTROLLER_FAILURE_UNDIAGNOSED",
        native_run="NOT_RECORDED",
        order_id="afo-private",
        attempt_id="afo-private-a1",
        job_id="afo-product-private",
        failure_type="STACK_STOP_FAILED",
        source_revision="b" * 40,
        gaps=["LAUNCH_TRANSCRIPT_MISSING"],
        records={
            "prompt": "NEVER_PROMPT",
            "reasoning": "NEVER_REASON",
            "api_key": "NEVER_SECRET",
            "observed": {"status": "BLOCKED"},
        },
        artifacts=[],
    )


def test_typed_controller_export_is_deterministic_redacted_and_not_a_product_run():
    one = C.render(case())
    two = C.render(case())
    assert one == two
    with zipfile.ZipFile(__import__("io").BytesIO(one["archive"])) as z:
        names = z.namelist()
        raw = b"".join(z.read(n) for n in names)
        assert "REPORT.md" in names and "CASE.json" in names
        for secret in (b"NEVER_PROMPT", b"NEVER_REASON", b"NEVER_SECRET"):
            assert secret not in raw
        manifest = json.loads(z.read("MANIFEST.json"))
        assert manifest["schema"] == "forge-c/controller-export/1"
        assert "runs" not in manifest and b"fabro_run_id" not in raw
        assert manifest["redactions"] == 1 and manifest["stripped_keys"] == 2
    assert C.verify(one["archive"]) == []


@pytest.mark.parametrize("bad", [{}, {"case_id": "../escape"}, {"native_run": "FAKE-NATIVE"}])
def test_bad_controller_identity_refuses(bad):
    value = case()
    value.update(bad) if bad else value.clear()
    with pytest.raises(ValueError):
        C.render(value)


def test_tampered_archive_is_detected():
    out = C.render(case())
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(out["archive"])) as src, zipfile.ZipFile(buf, "w") as dst:
        for name in src.namelist():
            dst.writestr(name, src.read(name) + (b"tamper" if name == "CASE.json" else b""))
    assert C.verify(buf.getvalue())


def test_private_directory_accepts_inherited_setgid_but_not_group_access(tmp_path):
    """The Omniverse2 data tree is setgid, so mkdir(0o700) yields 2700 there. It grants nothing extra."""
    import os
    import stat

    import pytest
    from forge_factory.afo.controller_escalation import _private
    from forge_factory.afo.durable import Refused

    parent = tmp_path / "setgid-parent"
    parent.mkdir()
    parent.chmod(0o2775)
    if not parent.stat().st_mode & stat.S_ISGID:
        pytest.skip("filesystem does not retain setgid")
    created = parent / "controller-exports"
    _private(created, create=True)
    assert stat.S_IMODE(created.stat().st_mode) == 0o2700
    _private(created)
    os.chmod(created, 0o2750)
    with pytest.raises(Refused, match="CONTROLLER_EXPORT_DIRECTORY_UNSAFE"):
        _private(created)
    os.chmod(created, 0o4700)
    with pytest.raises(Refused, match="CONTROLLER_EXPORT_DIRECTORY_UNSAFE"):
        _private(created)


@pytest.mark.parametrize("value", ["Refused", "TimeoutError", "GUARD_FAIL", "WORKORDER_LAUNCH_FAILED"])
def test_recorded_failure_types_are_accepted(value):
    """The first real failure in the canonical store recorded the exception class `Refused`."""
    from forge_factory.afo.controller_escalation import failure_type_ok

    assert failure_type_ok(value)


@pytest.mark.parametrize("value", ["", "1BAD", "two words", "a/b", "x" * 129, None, 7, "REPORT\nINJECT"])
def test_unsafe_failure_types_still_refuse(value):
    from forge_factory.afo.controller_escalation import failure_type_ok

    assert not failure_type_ok(value)


def test_contract_and_capture_agree_on_recorded_failure_types():
    """The check and the contract must not drift: L90's real proof recorded `Refused`."""
    from forge_factory.afo.controller_escalation import failure_type_ok

    for value in ("Refused", "STACK_STOP_FAILED"):
        assert failure_type_ok(value)
        assert C.render({**case(), "failure_type": value})["archive"]
    with pytest.raises(ValueError, match="CONTROLLER_EXPORT_SCHEMA_INVALID"):
        C.render({**case(), "failure_type": "free text"})
