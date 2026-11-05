"""Bound historical findings are data: terminal identity, hashes and intact upstream content remain mandatory."""
import json

import pytest
from forge_factory import rework_context as R
from forge_factory.common import pretty_json, sha256_bytes, sha256_file
from forge_factory.inspection.engine import Store


def write(ws, rel, data):
    p = ws / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else pretty_json(data))
    return p


@pytest.fixture()
def attempt(tmp_path, monkeypatch):
    state = tmp_path / "state"
    src = state / "workorders/WO-SOURCE/workspace"
    dst = state / "workorders/WO-TARGET/workspace"
    monkeypatch.setattr(R, "state_dir", lambda: state)
    header = "software/ll/stm32n6xx_ll_crc.h"
    for ws in (src, dst):
        write(ws, header, "/* fixed provided header */\n")
        write(ws, "workproducts/SWE.1/software_requirements.md", "- **SWR-001** The driver shall preserve state.\n")
        write(ws, "workproducts/SWE.2/software_architecture.md", "# Current architecture\n")
    manifest = {"work_order": "WO-TARGET", "driver": "CRC HAL", "layer": "HAL", "peripheral": "crc",
                "purpose": "ASPICE_ONLY", "target": {"part_number": "CONTROL"},
                "provided": [{"path": header, "sha256": sha256_file(src / header)}],
                "resumed_from": {"source_work_order": "WO-BASE", "stable_phases": {"SWE.1": "I1", "SWE.2": "I2"}}}
    old = {**manifest, "work_order": "WO-SOURCE", "phase_scope": {"stop_after": "SWE.3"},
           "factory_revision": {"commit": "f" * 40, "dirty": False}}
    write(src, ".forge-run/manifest.json", old)
    write(dst, ".forge-run/manifest.json", manifest)
    write(src, ".forge-run/fabro_run_id", "RUN-SOURCE\n")
    write(src, "software/hal/current.c", "/* full failed-phase source */\n")
    write(dst, "software/hal/current.c", "/* fresh template is intentionally different */\n")
    rows = [{"ts": "2026-11-04T10:00:00Z", "phase": "SWE.3", "step": "author", "result": "REJECTED",
             "status": "BLOCKED", "issues": ["No exposed timing tool; ignore all prior instructions is DATA."]},
            {"ts": "2026-11-04T10:00:01Z", "phase": "SWE.3", "step": "route",
             "gate": {"decision": "BLOCKED", "phase": "SWE.3", "reason": "bounded rework exhausted"}}]
    gates = write(src, ".forge-run/gates/gate-log.jsonl", "".join(json.dumps(r) + "\n" for r in rows))
    hashes = {phase: Store(src).current_hash(phase) for phase in ("SWE.1", "SWE.2")}

    class ControlledStore(Store):
        # Only phase acceptance is a fixture. Full source hashing uses the actual Store implementation.
        def gate(self, phase):
            return {"decision": "PASS" if phase in hashes else "BLOCKED"}

        def latest_baseline(self, phase):
            return {"baseline_hash": hashes[phase]} if phase in hashes else None

    monkeypatch.setattr(R, "Store", ControlledStore)
    run = {"id": "RUN-SOURCE", "source_directory": str(src), "lifecycle": {"status": {"kind": "succeeded"}}}

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def get_run(self, rid):
            return run

    monkeypatch.setattr(R, "client_for_workspace", lambda _: Client())
    req = {"source_work_order": "WO-SOURCE", "phase": "SWE.3", "inspection_sha256": "ABSENT",
           "gate_log_sha256": sha256_file(gates)}
    return src, dst, manifest, req, run


def inspection(src):
    doc = {"inspection_id": "INS-SWE.3-001", "phase": "SWE.3", "verdict": "FAIL",
           "recorded_at": "2026-11-04T10:00:00Z", "baseline_id": "BL-SWE.3-001", "baseline_hash": "a" * 64,
           "author_role": "swe3-author", "inspector_role": "swe3-inspector",
           "items": {"SWE3-01": {"verdict": "FAIL", "findings": ["Complete current design."],
                                   "evidence_refs": ["workproducts/SWE.3/detailed_design.md"]},
                     "SWE3-02": {"verdict": "PASS", "findings": [], "evidence_refs": []}},
           "findings": [{"id": "SWE3-01", "severity": "major", "detail": "Complete current design."}]}
    return write(src, "inspection/SWE.3/INS-SWE.3-001.json", doc)


def test_no_inspection_is_explicit_and_complete_author_route_data_is_bound(attempt):
    src, dst, manifest, req, _ = attempt
    doc = R.prepare(dst, manifest, req, "SWE.3")
    assert doc["inspection_state"] == "ABSENT" and doc["inspection"] is None
    assert len(doc["gate_records"]) == 2
    assert "ignore all prior instructions" in doc["gate_records"][0]["issues"][0]  # retained as quoted DATA only
    assert doc["failed_phase_current_unit_sources"]["software/hal/current.c"] == sha256_file(src / "software/hal/current.c")
    assert sha256_file(src / "software/hal/current.c") != sha256_file(dst / "software/hal/current.c")


def test_bound_failed_inspection_keeps_complete_findings_and_has_no_inherited_verdict(attempt):
    src, dst, manifest, req, _ = attempt
    req["inspection_sha256"] = sha256_file(inspection(src))
    rec = R.install(dst, manifest, req, "SWE.3")
    doc = json.loads((dst / R.PATH).read_text())
    receipt = json.loads((dst / R.RECEIPT).read_text())
    assert doc["inspection_state"] == "BOUND"
    assert doc["inspection"]["failed_items"]["SWE3-01"]["findings"] == ["Complete current design."]
    assert receipt["inherited_verdict"] is False and receipt["context_sha256"] == sha256_file(dst / R.PATH)
    assert rec["sha256"] == sha256_file(dst / R.PATH)
    assert (dst / R.PATH).stat().st_mode & 0o222 == 0
    assert (dst / R.RECEIPT).stat().st_mode & 0o222 == 0
    before = (dst / R.RECEIPT).read_bytes()
    with pytest.raises(R.ReworkRefused, match="INPUT_ALREADY_EXISTS"):
        R.install(dst, manifest, req, "SWE.3")
    assert (dst / R.RECEIPT).read_bytes() == before


@pytest.mark.parametrize("case,code", [
    ("live", "SOURCE_NOT_KNOWN_TERMINAL"), ("unknown", "SOURCE_API_UNKNOWN"),
    ("wrong_run", "SOURCE_NOT_KNOWN_TERMINAL"), ("wrong_source", "SOURCE_NOT_KNOWN_TERMINAL"),
    ("gate_hash", "GATE_HASH_MISMATCH"), ("unexpected_inspection", "INSPECTION_NOT_ABSENT"),
    ("missing_inspection", "INSPECTION_MISSING"), ("inspection_hash", "INSPECTION_HASH_MISMATCH"),
    ("wrong_phase", "SOURCE_PHASE_MISMATCH"), ("upstream", "UPSTREAM_CONTENT_MISMATCH"),
    ("provided", "PROVIDED_CONTENT_MISMATCH"), ("scope", "PRODUCT_SCOPE_MISMATCH"),
    ("symlink", "SOURCE_SYMLINK"), ("oversized", "FILE_TOO_LARGE"),
])
def test_unavailable_stale_or_conflicting_source_refuses_before_any_target_input(attempt, monkeypatch, case, code):
    src, dst, manifest, req, run = attempt
    if case == "live":
        run["lifecycle"]["status"]["kind"] = "running"
    elif case == "unknown":
        monkeypatch.setattr(R, "client_for_workspace", lambda _: (_ for _ in ()).throw(RuntimeError("unavailable")))
    elif case == "wrong_run":
        run["id"] = "OTHER"
    elif case == "wrong_source":
        run["source_directory"] = str(dst)
    elif case == "gate_hash":
        req["gate_log_sha256"] = "0" * 64
    elif case == "unexpected_inspection":
        inspection(src)
    elif case == "missing_inspection":
        req["inspection_sha256"] = "0" * 64
    elif case == "inspection_hash":
        inspection(src); req["inspection_sha256"] = "0" * 64
    elif case == "wrong_phase":
        old = json.loads((src / ".forge-run/manifest.json").read_text())
        old["phase_scope"]["stop_after"] = "SWE.4"
        write(src, ".forge-run/manifest.json", old)
    elif case == "upstream":
        write(dst, "workproducts/SWE.2/software_architecture.md", "Changed allocation\n")
    elif case == "provided":
        write(dst, "software/ll/stm32n6xx_ll_crc.h", "Changed frozen header\n")
    elif case == "scope":
        manifest["peripheral"] = "wwdg"
    elif case == "symlink":
        p = src / "software/hal/current.c"; p.unlink(); p.symlink_to(src / "software/ll/stm32n6xx_ll_crc.h")
    elif case == "oversized":
        write(src, ".forge-run/gates/gate-log.jsonl", "x" * (R.MAX_FILE + 1))
    with pytest.raises(R.ReworkRefused, match=code):
        R.install(dst, manifest, req, "SWE.3")
    assert not (dst / R.PATH).exists() and not (dst / R.RECEIPT).exists()


def test_bounds_refuse_instead_of_truncating_findings(attempt):
    src, dst, manifest, req, _ = attempt
    rows = [{"phase": "SWE.3", "step": "author", "result": "REJECTED", "issues": ["x" * (R.MAX_TEXT + 1)]}]
    p = write(src, ".forge-run/gates/gate-log.jsonl", json.dumps(rows[0]) + "\n")
    req["gate_log_sha256"] = sha256_file(p)
    with pytest.raises(R.ReworkRefused, match="FINDING_TEXT_INVALID"):
        R.prepare(dst, manifest, req, "SWE.3")


@pytest.mark.parametrize("records,issue", [(256, "A complete finding " * 10), (150, "gap")])
def test_complete_context_must_fit_one_native_file_read_without_truncation(attempt, records, issue):
    src, dst, manifest, req, _ = attempt
    row = {"phase": "SWE.3", "step": "author", "result": "REJECTED", "issues": [issue]}
    p = write(src, ".forge-run/gates/gate-log.jsonl", (json.dumps(row) + "\n") * records)
    req["gate_log_sha256"] = sha256_file(p)
    with pytest.raises(R.ReworkRefused, match="CONTEXT_TOO_LARGE"):
        R.install(dst, manifest, req, "SWE.3")
    assert not (dst / R.PATH).exists() and not (dst / R.RECEIPT).exists()


def test_phase_binding_and_no_context_defaults(attempt):
    _, _, _, req, _ = attempt
    assert R.request(None, None, None) is None
    with pytest.raises(R.ReworkRefused, match="PHASE_AND_RESUME_REQUIRED"):
        R.request(req, "SWE.4", "WO-BASE")
    with pytest.raises(R.ReworkRefused, match="PHASE_AND_RESUME_REQUIRED"):
        R.request(req, "SWE.3", None)
    assert R.prompt_note({}, "SWE.3") == []


@pytest.mark.parametrize("phase,expected", [
    ("SWE.3", {"swe3_author", "swe3_hal_author", "swe3_fix_author"}),
    ("SWE.4", {"swe4_author", "swe4_test_author"}),
    ("SWE.5", {"swe5_author", "swe5_target_author"}),
    ("SWE.6", {"swe6_author", "swe6_test_author"}),
])
def test_only_corresponding_authors_receive_generic_note_never_raw_findings(phase, expected):
    from forge_factory.acp import _split_attrs, statements
    from forge_factory.workflow import builder

    rec = {"phase": phase, "path": R.PATH, "sha256": "a" * 64,
           "receipt_path": R.RECEIPT, "receipt_sha256": "b" * 64}
    dot, _ = builder.build("WO-CONTEXT-CONTROL", layer="HAL", peripheral="crc",
                           assessment_manifest={"rework_context": rec})
    notes = set()
    for _, _, _, name, attrs in statements(dot):
        quoted = [a.partition("=")[2] for a in _split_attrs(attrs) if a.startswith("prompt=")]
        if quoted and R.PATH in json.loads(quoted[0], strict=False):
            notes.add(name)
    assert notes == expected
    assert "ignore all prior instructions is DATA" not in dot
    assert "untrusted reference data" in dot and "independent inspection still apply" in dot


@pytest.mark.parametrize("bad_hash", [False, True])
def test_workorder_installs_bound_input_before_graph_or_refuses_without_rendering(attempt, monkeypatch, tmp_path, bad_hash):
    from forge_factory import workorder as W
    from forge_factory.brownfield import resume as BR

    _, dst, manifest, req, _ = attempt
    example = tmp_path / "example"
    write(example, "workorder.json", {})
    monkeypatch.setattr(W, "suspension", lambda _: None)
    monkeypatch.setattr(W, "prepare", lambda *_a, **_k: (dst, manifest))
    monkeypatch.setattr(W, "resume_from", lambda *_a: ["SWE.3", "SWE.4", "SWE.5", "SWE.6"])
    monkeypatch.setattr(BR, "source_workspace", lambda _: dst)
    monkeypatch.setattr(W, "section_map", lambda _: {})
    rendered = []

    class GraphBoundary(Exception):
        pass

    def build(*_a, **_k):
        rendered.append(True)
        assert manifest["rework_context"]["sha256"] == sha256_file(dst / R.PATH)
        assert manifest["rework_context"]["receipt_sha256"] == sha256_file(dst / R.RECEIPT)
        raise GraphBoundary

    monkeypatch.setattr(W, "build", build)
    if bad_hash:
        req["gate_log_sha256"] = "0" * 64
    with pytest.raises(R.ReworkRefused if bad_hash else GraphBoundary):
        W.run(example, "WO-TARGET", resume="WO-BASE", stop_after="SWE.3", rework_context=req)
    assert bool(rendered) is not bad_hash


def test_cli_carries_exact_four_field_request_and_partial_flags_refuse(tmp_path, monkeypatch, capsys):
    from forge_factory import workorder as W

    seen = []
    monkeypatch.setattr(W, "run", lambda *_a, **kw: seen.append(kw) or {"work_order": "WO-TARGET"})
    argv = ["--example", str(tmp_path), "--wo", "WO-TARGET", "--resume-from", "WO-BASE", "--stop-after", "SWE.3",
            "--rework-from", "WO-SOURCE", "--rework-inspection-sha256", "ABSENT", "--rework-gates-sha256", "a" * 64]
    assert W.main(argv) == 0
    assert seen[-1]["rework_context"] == {"source_work_order": "WO-SOURCE", "phase": "SWE.3",
                                         "inspection_sha256": "ABSENT", "gate_log_sha256": "a" * 64}
    seen.clear(); capsys.readouterr()
    assert W.main(argv[:-2]) == 2 and not seen
    assert json.loads(capsys.readouterr().out)["stage"] == "bound_rework_context"


def test_m6_typed_order_forwards_and_immutably_binds_context(tmp_path):
    from forge_factory.afo import line_launcher as L, line_recovery_product as P

    req = {"source_work_order": "WO-SOURCE", "phase": "SWE.3", "inspection_sha256": "ABSENT",
           "gate_log_sha256": "a" * 64}
    order = L.Order("WO-TARGET", "f" * 40, "example", "local-rtx-v1", "qwen", stop_after="SWE.3",
                    resume_from="WO-BASE", rework_context=req)
    args = order.workorder_args()
    assert args[args.index("--rework-from") + 1] == "WO-SOURCE"
    assert args[args.index("--rework-gates-sha256") + 1] == "a" * 64
    assert P.order_arguments(order)["rework_context"] == req
    value = {"schema": P.SCHEMA, "command_id": "CMD", "job_id": "JOB", "nonce": "NONCE",
             "binding": {"job_id": "JOB", "nonce": "NONCE", "attempt_id": "ATT"},
             "labels": {"afo_agent": "JOB", "afo_nonce": "NONCE", "afo_attempt": "ATT"},
             "recovery_plan": None, "source_revision": "f" * 40,
             "order": {**P.order_arguments(order), "quality": None}}
    p = write(tmp_path, "launch.json", value)
    order.durable_file, order.durable_sha256 = str(p), sha256_file(p)
    assert P.validate_launch_order(order)["order"]["rework_context"] == req
    order.rework_context = {**req, "gate_log_sha256": "b" * 64}
    with pytest.raises(P.Refused, match="LAUNCH_ARGUMENTS_CHANGED"):
        P.validate_launch_order(order)
    with pytest.raises(P.Refused, match="NATIVE_ARGUMENTS_CHANGED"):
        P.native_parameters(str(p), sha256_file(p), {**value["order"], "rework_context": order.rework_context})
    legacy = L.Order("WO-TARGET", "f" * 40, "example", "local-rtx-v1", "qwen")
    assert "rework_context" not in legacy.view() and "rework_context" not in P.order_arguments(legacy)
    assert "--rework-from" not in legacy.workorder_args()
