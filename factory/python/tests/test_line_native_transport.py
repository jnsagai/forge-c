"""Measured request identity cannot become inferred authority or role competence."""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from forge_factory.afo import line_native_transport as T
from forge_factory.afo.durable import Refused


@pytest.fixture
def measured(tmp_path, monkeypatch):
    from forge_factory import common, workorder
    from forge_factory.lrtx import profile

    revision = {"commit": "a" * 40, "dirty": False, "branch": "qualified-run", "basis": "recorded_at_launch"}
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(workorder, "factory_revision", lambda: copy.deepcopy(revision))
    prof = {"id": "fixture-profile", "_sha256": "b" * 64, "models": {"allowed": {"author": {}, "inspector": {}}},
            "runtime": {"fabro_max_output_tokens": 16384}}
    monkeypatch.setattr(profile, "load", lambda _: prof)
    adapters = {}
    for relative in T.ADAPTERS:
        path = tmp_path / "factory/python/forge_factory" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture adapter " + relative)
        adapters[relative] = T._sha(path)
    binary = tmp_path / "fixture-fabro"
    binary.write_text("fixture binary")
    native = "01M6KFRJB2PA9ZTN3K2M42V19H"
    proof = {"schema": T.SCHEMA, "scope": T.SCOPE, "verdict": "PASS", "production_mutations": False,
             "source_tracked_dirty": False, "source_revision": revision["commit"], "profile": prof["id"],
             "profile_sha256": prof["_sha256"], "binary_sha256": T._sha(binary), "launch_returncode": 0,
             "terminal_status": "SUCCEEDED", "labels_match": True, "fixture_terminal_confirmed": True,
             "own_server_stopped": True, "all_headers_equal_actual_run_id": True,
             "adapter_sha256": adapters, "harness_sha256": "c" * 64, "settings_sha256": "d" * 64,
             "graph_sha256": "e" * 64, "native_run_id": native, "request_count": 2,
             "requests": [{"path": "/v1/chat/completions", "x_session_id": native, "model": model,
                           "stream": True, "max_tokens": 16384, "max_completion_tokens": None}
                          for model in prof["models"]["allowed"]],
             "identity_controls": {k: {"pass": True, "accepted": value} for k, value in T.CONTROLS.items()}}
    path = tmp_path / "measurement.json"
    job = {"profile": prof["id"], "factory_revision": copy.deepcopy(revision)}
    cfg = SimpleNamespace(fabro_bin=str(binary))

    def run(value=proof, *, ref_hash=None):
        raw = json.dumps(value).encode()
        path.write_bytes(raw)
        return T.require({"path": str(path), "sha256": ref_hash or hashlib.sha256(raw).hexdigest()}, job=job, cfg=cfg)

    return proof, job, cfg, run


def test_transport_proof_reports_facts_without_qualification(measured):
    proof, _, _, run = measured
    result = run()
    assert result["role_qualification"] is False
    assert result["max_tokens"] == 16384
    assert result["source_revision"] == proof["source_revision"]


@pytest.mark.parametrize("field,value", [
    ("schema", "unknown"), ("scope", "ROLE_QUALIFIED"), ("verdict", "NOT_RUN"),
    ("production_mutations", True), ("source_tracked_dirty", True), ("source_revision", "f" * 40),
    ("profile", "different"), ("profile_sha256", "0" * 64), ("binary_sha256", "0" * 64),
    ("launch_returncode", 1), ("terminal_status", "RUNNING"), ("labels_match", False),
    ("fixture_terminal_confirmed", False), ("own_server_stopped", False),
    ("all_headers_equal_actual_run_id", False), ("adapter_sha256", {}),
    ("harness_sha256", None), ("native_run_id", "stage-session-id"), ("request_count", 1),
    ("requests", []), ("identity_controls", {}),
])
def test_identity_outcome_or_measurement_drift_refuses(measured, field, value):
    proof, _, _, run = measured
    proof[field] = value
    with pytest.raises(Refused):
        run()


@pytest.mark.parametrize("field,value", [("x_session_id", "01M00000000000000000000000"),
                                        ("model", "undeclared-helper"), ("max_tokens", 999),
                                        ("stream", False), ("path", "/other"), ("max_completion_tokens", 10)])
def test_actual_request_fields_must_match_not_only_summary(measured, field, value):
    proof, _, _, run = measured
    proof["requests"][0][field] = value
    with pytest.raises(Refused):
        run()


def test_false_negative_control_and_changed_job_refuse(measured):
    proof, job, _, run = measured
    proof["identity_controls"]["foreign_nonce"]["accepted"] = True
    with pytest.raises(Refused):
        run()
    proof["identity_controls"]["foreign_nonce"]["accepted"] = False
    job["factory_revision"]["dirty"] = True
    with pytest.raises(Refused):
        run()


def test_hash_mismatch_and_changed_binary_refuse(measured):
    _, _, cfg, run = measured
    with pytest.raises(Refused):
        run(ref_hash="0" * 64)
    from pathlib import Path
    Path(cfg.fabro_bin).write_text("changed binary")
    with pytest.raises(Refused):
        run()
