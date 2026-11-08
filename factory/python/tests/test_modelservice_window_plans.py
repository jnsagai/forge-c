"""Feature 017 T042/T048: what a window does (smoke and qualification plans)."""
import json
import time

import httpx
from forge_factory.modelservice import window_plans as P

A, Q = P.AUTHOR, P.INSPECTOR
CAT = {"models": [{"model": Q, "identity": {"revision_fingerprint": "b" * 64}},
                  {"model": A, "identity": {"revision_fingerprint": "a" * 64}}]}


def _ctx(deadline_s=10_000):
    t = time.monotonic()
    return {"clock": time.monotonic, "deadline": t + deadline_s, "sleep": time.sleep}


def test_smoke_measures_handovers_and_checks_identities(tmp_path):
    loaded = {"m": None}
    outcomes = tmp_path / "outcomes.jsonl"

    def svc(req):
        if req.url.path == "/forge/v1/identity":
            m = req.url.params["model"]
            return httpx.Response(200, json={"revision_fingerprint": ("a" if m == A else "b") * 64})
        m = json.loads(req.content)["model"]
        if loaded["m"] != m:
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            with outcomes.open("a") as f:
                f.write(json.dumps({"kind": "swap", "outcome": "OK", "ts": ts, "from_model": loaded["m"], "to_model": m,
                                    "unload_ms": 300, "load_ms": 9000, "warm": True}) + "\n")
            loaded["m"] = m
        return httpx.Response(200, json={"choices": []}, headers={"x-forge-model-identity": ("a" if m == A else "b") * 16,
                                                                  "x-forge-swap-ms": "9300"})
    r = P.smoke(_ctx(), http=httpx.Client(transport=httpx.MockTransport(svc)), keys={"forge-qual": "K", "sim-neighbour": "N"},
                catalog=CAT, outcomes=outcomes, hand_overs=5, neighbour_s=0, evidence=tmp_path / "ev")
    assert r["identities_pass"] and r["sc009_pass"] and r["calls"] == 10
    assert set(r["swap_s"]) == {f"{A} -> {Q}", f"{Q} -> {A}"} and r["sc011_pass"]  # 9.3 s per swap, both directions
    assert json.loads((tmp_path / "ev/smoke.json").read_text())["sc011_pass"]


def _qset():
    launch = {"example": "examples/0014m-crc-hal", "purpose": "ASPICE_ONLY", "stop_after": "SWE.2",
              "resume_from": "WO-F014-SWE1-CRCHAL-20261103-L27", "provided_from": "WO-F014-SWE6-CRCL-20261103-L24",
              "profile": "local-rtx-v2-omniverse2-ornith-think-author-q38-inspector"}
    return {"phases": [{"phase": "SWE.2", "baseline": {"order": "WO-F014-SWE2-CRCHAL-20261104-L34B", "launch": launch}},
                       {"phase": "SWE.3", "baseline": {"runs": [], "gate_outcome": None}}]}


def test_orders_repeat_the_baseline_launch_with_a_new_id():
    o = P.orders(_qset(), "20261109")
    assert len(o) == 1 and o[0]["wo"] == "WO-F017Q-SWE2-CRCHAL-20261109"
    argv = P.argv_of(o[0])
    assert argv[:3] == ["python", "-m", "forge_factory.workorder"] and "--model" in argv and argv[argv.index("--model") + 1] == A
    assert argv[argv.index("--resume-from") + 1] == "WO-F014-SWE1-CRCHAL-20261103-L27"
    assert argv[argv.index("--stop-after") + 1] == "SWE.2" and "--provided-from" in argv


def test_qualification_seeds_read_only_copies_and_resumes_across_windows(tmp_path):
    import yaml
    owner = tmp_path / "owner"
    for wo in ("WO-F014-SWE1-CRCHAL-20261103-L27", "WO-F014-SWE6-CRCL-20261103-L24"):
        (owner / wo / "workspace").mkdir(parents=True)
        (owner / wo / "workspace/x").write_text(wo)
    before = sorted(p.name for p in owner.rglob("*"))
    qpath = tmp_path / "set.yaml"
    qpath.write_text(yaml.safe_dump(_qset()))
    calls = []

    class Done:
        returncode = 0
    run = lambda argv, **kw: calls.append(argv) or Done()  # noqa: E731
    r1 = P.qualification(_ctx(), qset_path=qpath, owner_workorders=owner, lane_root=tmp_path / "lane", env={}, run=run, stamp="s1")
    r2 = P.qualification(_ctx(), qset_path=qpath, owner_workorders=owner, lane_root=tmp_path / "lane", env={}, run=run, stamp="s1")
    assert r1["ran"] == ["WO-F017Q-SWE2-CRCHAL-s1"] and r2["ran"] == [] and len(calls) == 1  # resumable: never run twice
    assert (tmp_path / "lane/state/workorders/WO-F014-SWE1-CRCHAL-20261103-L27/workspace/x").is_file()
    assert sorted(p.name for p in owner.rglob("*")) == before  # the owner lane's orders are untouched


def test_no_order_starts_without_an_hour_left(tmp_path):
    import yaml
    qpath = tmp_path / "set.yaml"
    qpath.write_text(yaml.safe_dump(_qset()))
    r = P.qualification(_ctx(deadline_s=1800), qset_path=qpath, owner_workorders=tmp_path, lane_root=tmp_path / "lane", env={},
                        run=lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")), stamp="s2")
    assert r["ran"] == [] and r["not_started_for_time"] == ["WO-F017Q-SWE2-CRCHAL-s2"]
