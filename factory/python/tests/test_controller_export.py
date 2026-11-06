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
