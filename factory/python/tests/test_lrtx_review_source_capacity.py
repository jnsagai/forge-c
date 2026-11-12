"""Large primary evidence is loaded whole; complete request and native gates still decide."""
import json

import pytest
from forge_factory.common import sha256_bytes
from forge_factory.inspection.engine import Store
from forge_factory.lrtx import profile, review, runner, swe1
from forge_factory.lrtx import structured as S
from test_lrtx_swe1 import pytestmark, ws  # noqa: F401 - owner-input fixture/precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - real frozen baseline

PROFILE = "local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector"


def select(workspace):
    path = workspace / ".forge-run/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["local_profile"] = {"id": PROFILE}
    path.write_text(json.dumps(manifest))


def test_whole_large_frozen_requirements_and_tail_finding_reach_the_real_gate(ws1, monkeypatch):  # noqa: F811
    from test_lrtx_p3 import Answers, _inspector
    from test_lrtx_swe1 import _scripted

    path = ws1 / swe1.REQS
    tail = "REVIEW_TAIL_DEFECT: conflicting startup contract in the final source section"
    path.write_text(path.read_text() + "\n" + "Large evidence context.\n" * 2400 + tail + "\n")
    assert len(path.read_text()) > review.MAX_FILE_CHARS
    st = Store(ws1)
    st.freeze("SWE.1", "swe1-author")
    with pytest.raises(S.PacketRefused, match="SOURCE_TOO_LARGE"):
        review.evidence(ws1, "SWE.1")
    select(ws1)
    baseline, sources = review.evidence(ws1, "SWE.1")
    primary = next(s for s in sources if s["path"] == swe1.REQS)
    assert primary["text"] == path.read_text() and primary["sha256"] == sha256_bytes(path.read_bytes())
    assert baseline == st.latest_baseline("SWE.1")
    calls = []
    answer = _inspector({"SWE1-03": tail})

    def inspect(packet):
        assert tail in "\n".join(m["content"] for m in packet["_messages"])
        return answer(packet)

    monkeypatch.setattr(S, "call", _scripted(Answers({}, inspect), calls))
    assert runner._call(ws1, review.visit, ws1, "SWE.1", "m")["status"] == "REWORK"
    assert calls and st.gate("SWE.1")["decision"] != "PASS"
    record = st.inspections("SWE.1")[-1]
    assert record["verdict"] == "FAIL" and any(tail in f["detail"] for f in record["findings"])


def test_larger_file_envelope_does_not_enlarge_complete_durable_request_context(ws1, monkeypatch):  # noqa: F811
    select(ws1)
    path = ws1 / swe1.REQS
    path.write_text(path.read_text() + "\n" + "required evidence\n" * 18000)
    st = Store(ws1)
    st.freeze("SWE.1", "swe1-author")
    baseline, sources = review.evidence(ws1, "SWE.1")
    assert len(path.read_text()) < review.source_char_limit(ws1)
    (ws1 / ".forge-run/durable-binding.json").write_text("{}")
    item = next(c for c in st.applicable(st.checklist("SWE.1"))["checks"] if c["id"] == "SWE1-03")
    from forge_factory.lrtx.request_measurement import policy

    selected = profile.load(PROFILE)
    assert policy(selected)
    token = S.RECOVERY_WORKSPACE.set(ws1)
    try:
        pending = review.item_packet(ws1, "SWE.1", item, baseline, sources, "qwen3.8:27b-q8_0")
        assert pending["accounting"]["fits"] is None
        assert pending["accounting"]["admission"] == "PENDING_GATEWAY_NATIVE_MEASUREMENT"
        assert pending["accounting"]["complete_serialized_request"]["method"] == "utf8_byte_upper_bound"
        selected["gateway"].pop("request_measurement")
        monkeypatch.setattr(profile, "load", lambda _: selected)
        with pytest.raises(S.PacketRefused, match="PACKET_TOO_LARGE"):
            review.item_packet(ws1, "SWE.1", item, baseline, sources, "m")
    finally:
        S.RECOVERY_WORKSPACE.reset(token)


@pytest.mark.parametrize("value", [True, 0, -1, 4194305, 2.5, "1000000"])
def test_invalid_profile_source_capacity_refuses_before_model(ws1, monkeypatch, value):  # noqa: F811
    select(ws1)
    monkeypatch.setattr(profile, "load", lambda _: {"structured": {"inspection_max_source_chars": value}})
    monkeypatch.setattr(S, "call", lambda *a, **kw: pytest.fail("invalid source policy cannot call the model"))
    result = review.visit(ws1, "SWE.1", "m")
    assert result["status"] == "FAILED" and "PROFILE_INSPECTION_SOURCE_LIMIT_INVALID" in result["issues"]
    assert not (ws1 / "inspection/SWE.1").exists()
