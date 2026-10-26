"""DA-T056 / DA-AT-056: the offline export bundle is deterministic, hash-listed and carries the run's decisions and
records, never vendor inputs, raw prompts, reasoning or secrets; it opens no network connection."""
import json
import socket
import zipfile

import pytest
from forge_factory.offline import export as X


def _ws(root, wo="WO-0009B-STM32N6-IWDG-HAL-x1"):
    ws = root / wo / "workspace"
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / ".forge-run/lrtx/SWE.1").mkdir(parents=True)
    (ws / ".forge-run/advisory").mkdir(parents=True)
    (ws / ".forge-run/index").mkdir(parents=True)
    (ws / ".forge-run/acp").mkdir(parents=True)
    (ws / "inputs").mkdir()
    (ws / "inspection/SWE.1").mkdir(parents=True)
    (ws / "workproducts").mkdir()
    (ws / ".forge-run/manifest.json").write_text(json.dumps({
        "work_order": wo, "local_profile": {"id": "local-rtx-v2-omniverse2-q36-noreason", "version": 2}}))
    (ws / ".forge-run/model-profile.json").write_text(json.dumps({"default": "qwen3.6:35b-a3b", "api_key": "abc123"}))
    (ws / ".forge-run/gates/gate-log.jsonl").write_text(
        json.dumps({"phase": "SWE.1", "decision": "FROZEN"}) + "\n" + "not json, token=hunter2\n")
    (ws / ".forge-run/lrtx/SWE.1/inspection-record.json").write_text(json.dumps({
        "steps": [{"question": "SWE1-02", "answer": {"answer": "TRUE", "quote": "shall start"},
                   "claims": [{"identity": "c1", "decision": "UPHELD"}],
                   "prompt": "You are an inspector ...", "reasoning": "first I look at ..."}],
        "messages": [{"role": "system", "content": "..."}]}))
    (ws / ".forge-run/lrtx/SWE.1/generated-header.h").write_text("#define X 1\n")
    (ws / ".forge-run/advisory/SWE.1.jsonl").write_text(json.dumps({"phase": "SWE.1", "attempts": {"failed_cycles": 3}}) + "\n")
    (ws / ".forge-run/acp/swe1_inspector.proxy.jsonl").write_text(json.dumps({"event": "usage", "input": 10}) + "\n")
    (ws / ".forge-run/fabro_server.json").write_text(json.dumps({"url": "http://127.0.0.1:1", "storage": "/x"}))
    (ws / ".forge-run/index/RM0486.json").write_text(json.dumps({"section": "vendor text"}))
    (ws / "inputs/RM0486-rev4-ch59-iwdg.md").write_text("vendor reference manual text\n")
    (ws / "inspection/SWE.1/INS-SWE.1-001.json").write_text(json.dumps({"status": "FAIL", "issues": []}))
    (ws / "workproducts/SWE.1-requirements.md").write_text("SWR-001 The driver shall ...\n")
    return ws


def _files(bundle):
    with zipfile.ZipFile(bundle) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


def test_two_exports_of_the_same_runs_are_byte_identical_and_intact(tmp_path):
    a, b = _ws(tmp_path / "a"), _ws(tmp_path / "b", "WO-0008C-ST-RCC-LL-y2")
    r1 = X.build([a, b], tmp_path / "out1/export.zip")
    r2 = X.build([b, a], tmp_path / "out2/export.zip")  # input order does not matter
    assert (tmp_path / "out1/export.zip").read_bytes() == (tmp_path / "out2/export.zip").read_bytes()
    assert r1["sha256"] == r2["sha256"] and r1["runs"] == 2
    assert X.verify(tmp_path / "out1/export.zip") == []
    assert (tmp_path / "out1/export.zip.sha256").read_text().startswith(r1["sha256"])


def test_records_travel_and_vendor_inputs_prompts_reasoning_and_secrets_do_not(tmp_path):
    ws = _ws(tmp_path)
    X.build([ws], tmp_path / "export.zip")
    files = _files(tmp_path / "export.zip")
    m = json.loads(files["MANIFEST.json"])
    run = m["runs"][0]
    assert run["workorder"] == "WO-0009B-STM32N6-IWDG-HAL-x1" and run["model"] == "qwen3.6:35b-a3b"
    assert run["profile"] == "local-rtx-v2-omniverse2-q36-noreason"
    rows = {f["path"]: f for f in run["files"]}
    for rel in ("inputs/RM0486-rev4-ch59-iwdg.md", ".forge-run/index/RM0486.json", ".forge-run/fabro_server.json"):
        assert rows[rel]["content"] == "NEVER_CONTENT" and "exported_sha256" not in rows[rel]
    for rel in ("workproducts/SWE.1-requirements.md", ".forge-run/lrtx/SWE.1/generated-header.h"):
        assert rows[rel]["content"] == "HASH_ONLY"  # development holds the frozen inputs; it checks them by hash
    blob = b"".join(files.values())
    for leaked in (b"vendor reference manual", b"vendor text", b"You are an inspector", b"first I look at", b"abc123",
                   b"hunter2", b'"role": "system"', b"127.0.0.1"):
        assert leaked not in blob
    rec = json.loads(files[f"runs/{run['run_key']}/.forge-run/lrtx/SWE.1/inspection-record.json"])
    assert rec["steps"][0]["question"] == "SWE1-02" and rec["steps"][0]["claims"][0]["decision"] == "UPHELD"
    ins = rows[".forge-run/lrtx/SWE.1/inspection-record.json"]
    assert ins["content"] == "INCLUDED" and ins["stripped_keys"] == 3  # prompt, reasoning, messages: counted
    assert rows[".forge-run/model-profile.json"]["redactions"] == 1
    assert rows[".forge-run/gates/gate-log.jsonl"]["redactions"] == 1  # the unparsable line is redacted text
    assert {".forge-run/advisory/SWE.1.jsonl", "inspection/SWE.1/INS-SWE.1-001.json",
            ".forge-run/acp/swe1_inspector.proxy.jsonl"} <= {p for p, f in rows.items() if f["content"] == "INCLUDED"}
    assert m["totals"]["stripped_keys"] == 3 and m["totals"]["redactions"] == 2


def test_tampering_with_any_exported_file_or_adding_content_is_detected(tmp_path):
    X.build([_ws(tmp_path)], tmp_path / "export.zip")
    files = _files(tmp_path / "export.zip")
    key = json.loads(files["MANIFEST.json"])["runs"][0]["run_key"]
    victim = f"runs/{key}/.forge-run/gates/gate-log.jsonl"

    def rewrite(name, mutate):
        with zipfile.ZipFile(tmp_path / name, "w") as zf:
            for n, d in mutate(dict(files)).items():
                zf.writestr(n, d)
        return X.verify(tmp_path / name)

    assert rewrite("t1.zip", lambda f: {**f, victim: f[victim] + b"{}\n"}) == [f"HASH_MISMATCH:{victim}"]
    smuggled = f"runs/{key}/inputs/RM0486-rev4-ch59-iwdg.md"
    assert rewrite("t2.zip", lambda f: {**f, smuggled: b"vendor"}) == [f"UNLISTED:{smuggled}",
                                                                      f"CONTENT_NOT_ALLOWED:{smuggled}"]


def test_export_opens_no_network_connection(tmp_path, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network use during export")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    r = X.build([_ws(tmp_path)], tmp_path / "export.zip")
    assert r["included"] >= 6 and X.verify(tmp_path / "export.zip") == []


def test_the_same_run_twice_is_refused(tmp_path):
    ws = _ws(tmp_path)
    with pytest.raises(ValueError, match="DUPLICATE_RUN"):
        X.build([ws, ws], tmp_path / "export.zip")
