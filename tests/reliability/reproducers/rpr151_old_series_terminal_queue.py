"""Actual queue/Records/Placer reconciliation, with a synthetic bound Fabro API (no model/GPU)."""
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

SIG = "terminal old-series Fabro run strands the queue capacity after campaign supersession"


def main():
    from forge_factory.afo import line_orders as LO, line_launcher as LL
    from forge_factory.afo.queue import Store, QueueError
    with tempfile.TemporaryDirectory(prefix="rpr151-") as tmp:
        root = Path(tmp)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "events")
        now = time.time()
        wo, rid = "WO-F014-SWE5-CRCHAL-20261103-L31D", "RPR151-TERMINAL"
        spec = {"schema": LO.ORDER_SCHEMA, "wo": wo, "phase": "SWE.5", "kind": "CHAIN",
                "driver_class": "STM32N6_CRC_HAL", "profile": "local-rtx-v2", "revision": "a" * 40}
        spec["digest"] = LO._digest(spec)
        orders = LO.supervisor_dir() / "line-orders"
        orders.mkdir(parents=True)
        sf = orders / (wo + ".json"); sf.write_text(json.dumps(spec))
        ws = root / "state/workorders" / wo / "workspace"
        run = ws / ".forge-run"; run.mkdir(parents=True)
        (run / "manifest.json").write_text(json.dumps({"work_order": wo, "phase_scope": {"stop_after": "SWE.5"}}))
        (run / "fabro_run_id").write_text(rid)
        (run / "package.json").write_text(json.dumps({"package_status": "BLOCKED", "gaps": []}))
        manifest = root / "campaign.json"; manifest.write_text('{"series":"old"}')
        env = {"schema_version": "1.0", "request_id": wo, "tenant_scope": "line-local",
               "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(), "input_manifest_ref": "campaign.json",
               "approved_by": "owner", "authorization_ref": "AUTH-RPR", "driver_class": spec["driver_class"],
               "target": "CRC", "safety_scope": "ASPICE_ONLY", "model_profile": spec["profile"],
               "submitted_utc": "2026-11-04T00:00:00Z", "priority": "NORMAL", "payload_digest": spec["digest"]}
        line = SimpleNamespace(workspace=lambda w: root / "state/workorders" / w / "workspace",
                               launch_dir=lambda: root / "launch", transcripts=lambda w: [], alive=lambda p, s: False,
                               run_status=lambda r: "failed", verdict=lambda w, ph: {"verdict": "NO"}, LL=LL)
        line.host = SimpleNamespace(fabro_run=lambda r: {"id": rid, "source_directory": str(ws),
                                    "lifecycle": {"status": {"kind": "failed"}}})
        line.ended_run = lambda w, r: LO.RealLine.ended_run(line, w, r)
        pl = LO.Placer(line, line_id="local", dry_run=True)
        store = Store(pl.queue_path)
        oid, _ = store.submit(env, repo=root, max_queued=10, approve=lambda e: (True, "TEST_APPROVED"))
        epoch = store.acquire_lease("line-local", "rpr", 600)
        aid = store.admit(oid, epoch=epoch, scope="line-local", policy_sha256="b" * 64,
                          authorization_id="AUTH-RPR", max_concurrent=1)
        store.attempt_transition(aid, "DISPATCH_PENDING")
        store.attempt_transition(aid, "RUNNING", fabro_run_id=rid)
        store.transition(oid, "RUNNING", "test launched")
        before = store.order(oid)["envelope"], sf.read_bytes(), (run / "manifest.json").read_bytes()
        grant = SimpleNamespace(permit=lambda action, request: SimpleNamespace(allow=True))
        # Removing the old series leaves no planner entries. The old queue row must still settle.
        pl._reconcile([], LO.load_policy(), grant, [], now)
        if store.order(oid)["state"] == "RUNNING":
            print("SYMPTOM_PRESENT:" + SIG); return 1
        assert store.order(oid)["state"] == "BLOCKED"
        assert before == (store.order(oid)["envelope"], sf.read_bytes(), (run / "manifest.json").read_bytes())
        n = len(store.events(oid)); pl._reconcile([], LO.load_policy(), grant, [], now)
        assert n == len(store.events(oid))
        env2 = {**env, "request_id": "WO-NEXT"}
        oid2, _ = store.submit(env2, repo=root, max_queued=10, approve=lambda e: (True, "TEST_APPROVED"))
        store.admit(oid2, epoch=epoch, scope="line-local", policy_sha256="b" * 64,
                    authorization_id="AUTH-RPR", max_concurrent=1)
        print("SYMPTOM_ABSENT"); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        raise SystemExit(2)
