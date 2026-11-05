"""Independent normal extension -> next line order scenario; no owner keys, services or refill."""
from __future__ import annotations

import copy
import json
import os
from datetime import UTC, datetime
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

from forge_factory.afo import authz, mission_deadline as D
from forge_factory.afo import line_recovery_product as P
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store
from forge_factory.common import sha256_file

SIG = "owner-signed time-only mission renewal cannot link the next normal line order without re-registering immutable limits"


def main():
    with tempfile.TemporaryDirectory(prefix="rpr172-") as directory:
        root = Path(directory)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ.pop("FORGE_DURABLE_AUTONOMY", None)
        store = Store(root / "state/supervisor/line-queue.sqlite3")
        ledger = MissionLedger(store)
        limits = dict(max_attempts=4, max_jobs=4, max_requests=32, max_tokens=8388608,
                      max_tools=256, max_corrections=4, deadline=time.time()-10)
        ledger.register("retained-mission", "retained-lineage", limits, "CONTROL-INITIAL", authorize=lambda *_: True)
        ledger.execution("retained-mission", "old-unstarted-product", "PRODUCT", reserved_tokens=1048576, imported=True)
        before = ledger.snapshot("retained-mission")
        with store.tx() as c:
            original = c.execute("SELECT record FROM afo_missions").fetchone()[0]
        document = dict(schema=D.SCHEMA, mission_id="retained-mission", snapshot_sha256=digest(before),
                        deadline_epoch=time.time()+1200, authorization_ref="DEADLINE-INDEPENDENT",
                        request=dict(order_id="NEXT-B", driver_class="LL", model="fixture-local"),
                        reason="Independent synthetic time-only continuation; no live authority")
        grant_root = root / "fixture-auth"
        grant_root.mkdir()
        (grant_root / "DEADLINE-INDEPENDENT.json").write_text(json.dumps(dict(
            authorization_id="DEADLINE-INDEPENDENT", expires_utc=datetime.fromtimestamp(time.time()+1800, UTC).isoformat(),
            signed_runbook_ref="mission-deadline-extension-014:"+digest(document))))
        # The external signature leaf alone is substituted. The evaluated normal
        # extension validates its document/runbook/quiescence and writes its own
        # append-only receipt; all queue, accounting and line linkage are real.
        with patch.object(authz, "AUTH_DIR", grant_root), patch.object(authz, "verify", return_value=SimpleNamespace(allow=True)):
            D.extend(store, document, SimpleNamespace(mode="PILOT", sha256="c"*64, get=lambda *_: 1800))
        effective = ledger.snapshot("retained-mission")
        assert effective["initial_authorization_ref"] == "CONTROL-INITIAL"
        assert effective["authorization_ref"] == "DEADLINE-INDEPENDENT"
        for key in ("attempts", "charged_tokens", "usage_unknown", "unique_executions", "jobs", "tools", "requests"):
            assert effective[key] == before[key]
        repo = root / "repo"
        (repo / "afo-manifests").mkdir(parents=True)
        manifest = repo / "afo-manifests/m1.json"
        manifest.write_text('{"example":"isolated-renewal"}')
        envelope = dict(schema_version="1.0", request_id="NEXT-B", tenant_scope="line-local",
                        manifest_sha256=sha256_file(manifest), input_manifest_ref="afo-manifests/m1.json",
                        approved_by="SYNTHETIC_TEST", authorization_ref="CONTROL-INITIAL", driver_class="LL",
                        target="isolated-renewal", safety_scope="TEST_ONLY", model_profile="fixture-local",
                        submitted_utc="2026-11-05T00:00:00Z", priority="NORMAL")
        oid, created = store.submit(envelope, repo=repo, max_queued=4)
        assert created and store.order(oid)["state"] == "QUEUED"
        control = dict(mission=dict(mission_id="retained-mission", lineage="retained-lineage", limits=effective["limits"]),
                       authorization_ref="CONTROL-INITIAL")
        spec = dict(resume_from=None)
        try:
            result = P.link_mission(store, store.order(oid), control, spec)
        except Refused as exc:
            if exc.code != "MISSION_ALLOWANCE_RESET_FORBIDDEN":
                raise
            assert ledger.snapshot("retained-mission") == effective
            print("SYMPTOM_PRESENT:"+SIG)
            return 1
        assert result == effective and ledger.for_order(oid) == "retained-mission"
        assert P.link_mission(store, store.order(oid), control, spec) == effective
        for fault in ("authorization", "capacity", "lineage"):
            changed = copy.deepcopy(control)
            if fault == "authorization":
                changed["authorization_ref"] = "FOREIGN-CONTROL"
            elif fault == "capacity":
                changed["mission"]["limits"]["max_attempts"] += 1
            else:
                changed["mission"]["lineage"] += "-renamed"
            try:
                P.link_mission(store, store.order(oid), changed, spec)
            except Refused:
                pass
            else:
                raise AssertionError("NEGATIVE_CONTROL_ACCEPTED:"+fault)
        with store.tx() as c:
            assert c.execute("SELECT record FROM afo_missions").fetchone()[0] == original
            assert c.execute("SELECT COUNT(*) FROM afo_mission_orders").fetchone()[0] == 1
        assert ledger.snapshot("retained-mission") == effective
        print("SYMPTOM_ABSENT")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
