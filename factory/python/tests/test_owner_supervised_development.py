"""Private OS-owner development controls; never production authority/role acceptance."""

import copy
import json
import time
from pathlib import Path

import pytest
from forge_factory.afo import operations, policy
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused, digest, immutable_json
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store
from forge_factory.common import canonical_json, sha256_file

PINNED_ROLE_ENVELOPES_E = dict(D.ROLE_ENVELOPES_E)
DRIVER = D.ORDER_DRIVERS[D.ORDERS[0]]

PRIOR_RECORD = (
    '{"authorization_ref":"AUTH-AFO-REVIEW-20261104-LINE-FINITE","created_at":"2026-11-04T22:50:57.061356Z",'
    '"limits":{"deadline":1793848026.0,"max_attempts":4,"max_corrections":4,"max_jobs":4,"max_requests":32,'
    '"max_tokens":8388608,"max_tools":256},"lineage":"owner-review:local-role-trial-20261104",'
    '"mission_id":"line-local-role-trial-20261104"}'
)


CLOSED_ALLOWANCE_RECORD = (
    '{"authorization_ref":"OWNER-DEVELOPMENT-ALLOWANCE-20261106-NOT-A-GRANT","created_at":"2026-11-06T12:35:53.378181Z",'
    '"limits":{"deadline":1795057626.0,"max_attempts":2,"max_corrections":4,"max_jobs":2,"max_requests":32,'
    '"max_tokens":8388608,"max_tools":256},"lineage":"owner-review:local-role-trial-20261106",'
    '"mission_id":"line-local-role-trial-20261106"}'
)

RAISED_ALLOWANCE_RECORD = (
    '{"authorization_ref":"OWNER-DEVELOPMENT-ALLOWANCE-20261106B-NOT-A-GRANT","created_at":"2026-11-06T15:32:34.487049Z",'
    '"limits":{"deadline":1795057626.0,"max_attempts":1,"max_corrections":4,"max_jobs":2,"max_requests":256,'
    '"max_tokens":16777216,"max_tools":512},"lineage":"owner-review:local-role-trial-20261106b",'
    '"mission_id":"line-local-role-trial-20261106b"}'
)

RETRYING_ALLOWANCE_RECORD = (
    '{"authorization_ref":"OWNER-DEVELOPMENT-ALLOWANCE-20261106C-NOT-A-GRANT","created_at":"2026-11-06T16:54:19.446989Z",'
    '"limits":{"deadline":1795057626.0,"max_attempts":32,"max_corrections":128,"max_jobs":64,"max_requests":8192,'
    '"max_tokens":335544320,"max_tools":16384},"lineage":"owner-review:local-role-trial-20261106c",'
    '"mission_id":"line-local-role-trial-20261106c"}'
)


def seed_retrying_allowance(c, spent=None):
    """Allowance C as it ended: its exact real row and counters (attempts and jobs as executions, the rest as
    imported aggregates on the first execution), usage unknown."""
    spent = dict(D.RETRYING_ALLOWANCE_SPENT if spent is None else spent)
    c.execute(
        "INSERT INTO afo_missions VALUES (?,?,?)",
        (D.RETRYING_ALLOWANCE, json.loads(RETRYING_ALLOWANCE_RECORD)["lineage"], RETRYING_ALLOWANCE_RECORD),
    )
    kinds = ["PRODUCT"] * spent["attempts"] + ["DIAGNOSIS"] * spent["jobs"]
    assert kinds, "allowance C ended with spend"
    share, rest = divmod(spent["charged_tokens"], len(kinds))
    for i, kind in enumerate(kinds):
        identity = "afo-retrying-spent-" + str(i)
        record = dict(
            charge=share + (rest if i == 0 else 0), created_at="2026-11-06T17:00:00Z", evidence_refs=[],
            identity=identity, imported=False, kind=kind, reported_tokens=None,
        )
        if i == 0:
            record.update(requests=spent["requests"], tools=spent["tools"], corrections=spent["corrections"])
        c.execute("INSERT INTO afo_mission_executions VALUES (?,?,?,?)", (identity, D.RETRYING_ALLOWANCE, kind, json.dumps(record)))


def seed_spent_original(store):
    """The exact real rows and spent, unknown-usage attempts the allowance must sit beside."""
    with store.tx() as c:
        c.execute(
            "INSERT INTO afo_missions VALUES (?,?,?)", (D.PRIOR_MISSION, json.loads(PRIOR_RECORD)["lineage"], PRIOR_RECORD)
        )
        for i in range(4):
            identity = "afo-product-spent-" + str(i)
            record = dict(
                charge=1048576, created_at="2026-11-04T22:50:57Z", evidence_refs=[], identity=identity,
                imported=False, kind="PRODUCT", reported_tokens=None,
            )
            c.execute(
                "INSERT INTO afo_mission_executions VALUES (?,?,?,?)",
                (identity, D.PRIOR_MISSION, "PRODUCT", json.dumps(record)),
            )
        c.execute(
            "INSERT INTO afo_missions VALUES (?,?,?)",
            (D.CLOSED_ALLOWANCE, json.loads(CLOSED_ALLOWANCE_RECORD)["lineage"], CLOSED_ALLOWANCE_RECORD),
        )
        spent = dict(
            charge=1048576, created_at="2026-11-06T12:37:49Z", evidence_refs=[], identity="afo-product-spent-e",
            imported=False, kind="PRODUCT", reported_tokens=None,
        )
        c.execute(
            "INSERT INTO afo_mission_executions VALUES (?,?,?,?)",
            ("afo-product-spent-e", D.CLOSED_ALLOWANCE, "PRODUCT", json.dumps(spent)),
        )
        c.execute(
            "INSERT INTO afo_missions VALUES (?,?,?)",
            (D.RAISED_ALLOWANCE, json.loads(RAISED_ALLOWANCE_RECORD)["lineage"], RAISED_ALLOWANCE_RECORD),
        )
        for identity, kind, tokens in (("afo-product-spent-f", "PRODUCT", 8388608), ("afo-agent-spent-f", "DIAGNOSIS", 1048576)):
            spent = dict(
                charge=tokens, created_at="2026-11-06T15:33:00Z", evidence_refs=[], identity=identity,
                imported=False, kind=kind, reported_tokens=None,
            )
            c.execute(
                "INSERT INTO afo_mission_executions VALUES (?,?,?,?)",
                (identity, D.RAISED_ALLOWANCE, kind, json.dumps(spent)),
            )
        for i in range(41):
            row = dict(job_id="afo-product-spent-f", charge=1000, reported_tokens=1000, state="QUIESCENT")
            c.execute(
                "INSERT INTO afo_request_ledger VALUES (?,?,?,?,?)",
                ("spent-" + str(i), D.RAISED_ALLOWANCE, "afo-product-spent-f", "QUIESCENT", json.dumps(row)),
            )
        seed_retrying_allowance(c)


@pytest.fixture
def supervised(tmp_path, monkeypatch):
    from forge_factory.afo import line_recovery_control as C
    from forge_factory.lrtx.profile import load

    private = tmp_path / "private-owner"
    private.mkdir(mode=0o700)
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(private / "intent.json"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_AFO_QUEUE_SCOPE", "line-local")
    operations.Intent().set("RUNNING", actor="PRIVATE-TEST-OWNER", reason="Private control", initialize=True)
    # The private fixture trials stand in for mission E's preflight trials.
    monkeypatch.setattr(D, "ROLE_ENVELOPES_E", dict(D.LEGACY_ROLE_ENVELOPES))
    store = Store(tmp_path / "state/supervisor/line-queue.sqlite3")
    limits = dict(D.CAPS, deadline=time.time() + 300)
    seed_spent_original(store)
    MissionLedger(store).register(D.MISSION, D.LINEAGE, limits, D.ALLOWANCE_REF, authorize=lambda *_: True)
    from forge_factory.common import load_yaml

    fixtures = Path(__file__).parent / "fixtures/owner-supervised-development"
    pol = load_yaml(fixtures / "afo-policy.proposed.yaml")
    runtime = tmp_path / "runtime.yaml"
    runtime.write_bytes((fixtures / "afo-policy.proposed.yaml").read_bytes())
    monkeypatch.setenv("FORGE_AFO_POLICY", str(runtime))
    line = tmp_path / "line.yaml"
    line.write_bytes((fixtures / "line-policy.proposed.yaml").read_bytes())
    prof = load("local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104")
    control = dict(
        schema=C.SCHEMA,
        source_revision="a" * 40,
        policy_sha256=__import__("hashlib").sha256(canonical_json(pol)).hexdigest(),
        authorization_ref=D.INITIAL_AUTHORITY,
        profile=prof["id"],
        profile_sha256=prof["_sha256"],
        operations_intent=str(private / "intent.json"),
        mission=dict(mission_id=D.MISSION, lineage=D.LINEAGE, limits=limits),
        role_capabilities={},
        product_role_trial=None,
        product_role_trials={},
    )
    trials = {}
    for name in ("qwen-trial.json", "ornith-trial.json"):
        trial = json.loads((fixtures / name).read_text())
        trial["source_revision"] = "a" * 40
        trial["deadline_epoch"] = limits["deadline"]
        trial["order_ids"] = D.trial_order_ids()
        for identities in trial["roles"].values():
            for identity in identities:
                identity["adapter_revision"] = "a" * 40
        model = trial["model"]
        allocation = tmp_path / (name + ".PRIVATE-TEST-ALLOCATION.json")
        allocation.write_text(
            json.dumps(
                dict(
                    status="PASS_ALLOCATION_ONLY",
                    provider_context_tokens=262144,
                    model_digest=prof["models"]["allowed"][model]["digest"],
                    precision="Q8_0",
                    provider_slot_count=1,
                    kv_precision="f16",
                )
            )
        )
        trial["context_allocation_ref"] = dict(path=str(allocation), sha256=sha256_file(allocation))
        tr = dict(path=f"afo/product-role-trials/{digest(trial)}.json", sha256=digest(trial))
        immutable_json(tmp_path / "state" / tr["path"], trial)
        trials[model] = tr
    control["product_role_trial"] = trials[D.RUN_MODEL]
    control["product_role_trials"] = trials
    path = tmp_path / "control.json"
    immutable_json(path, control)
    ref = dict(path=str(path), sha256=sha256_file(path))
    monkeypatch.setattr(C, "revision", lambda: dict(commit="a" * 40, dirty=False))
    boot_sample = time.clock_gettime(time.CLOCK_BOOTTIME)
    mono = time.monotonic()
    upper = time.time() + 2
    ticket = dict(
        remote_boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        remote_monotonic=mono,
        remote_boottime=boot_sample,
        fresh_until_monotonic=mono + 60,
        deadline_monotonic=mono + limits["deadline"] - upper,
        external_utc_upper_at_remote_sample=upper,
        RTT_seconds=0.01,
        clock_sync_waived_by_owner=True,
        host_UTC_or_NTP_not_used=True,
        anchor_sha256="f" * 64,
    )
    ticket_path = tmp_path / "PRIVATE-TEST-UTC-TICKET.json"
    ticket_path.write_text(json.dumps(ticket))
    record = D.create(
        store, control_ref=ref, runtime_policy=runtime, line_policy=line, directive=D.DIRECTIVE, expiry_ticket=ticket
    )
    monkeypatch.setenv(D.FILE, record["path"])
    monkeypatch.setenv(D.SHA, record["sha256"])
    yield dict(
        store=store,
        ref=record,
        control=control,
        control_ref=ref,
        runtime=runtime,
        line=line,
        limits=limits,
        ticket=ticket,
        ticket_path=ticket_path,
    )
    D.close_guardian(record)


def test_default_unsigned_production_still_observe(tmp_path, monkeypatch):
    monkeypatch.delenv(D.FILE, raising=False)
    monkeypatch.delenv(D.SHA, raising=False)
    eff = policy.load(auth_base=tmp_path)
    assert eff.mode not in ("PILOT", "ACTIVE", D.MODE)


def test_explicit_owner_context_is_unaccepted_not_auth_ok(supervised):
    eff = policy.load(supervised["runtime"])
    assert eff.mode == D.MODE
    assert eff.issues == ["OWNER_SUPERVISED_DEVELOPMENT_UNACCEPTED"]
    r = D.current(store=supervised["store"])
    assert r["acceptance"] == "UNACCEPTED" and r["qualification_only"] is True
    assert r["control_context"]["authentication"]["method"] == "PRIVATE_INTENT_DIRECTORY_OWNER"
    assert D.permit(
        eff, "recover_workorder", dict(order_id=D.ORDERS[0], driver_class=DRIVER, model=supervised["control"]["profile"])
    )
    assert MissionLedger(supervised["store"]).snapshot(D.MISSION)["charged_tokens"] == 0
    assert MissionLedger(supervised["store"]).snapshot(D.PRIOR_MISSION)["charged_tokens"] == 4194304


@pytest.mark.parametrize(
    "scope_request",
    [
        {},
        dict(order_id="WO-F014-SWE6-AFOQUAL-20261104-L90", driver_class=DRIVER, model="x"),
        dict(order_id=D.ORDERS[0], driver_class="FOREIGN", model="x"),
        dict(order_id=D.ORDERS[-1] + "E", driver_class=DRIVER, model="x"),
    ],
)
def test_empty_old_foreign_and_fifth_scope_refused(supervised, scope_request):
    assert not D.permit(policy.load(supervised["runtime"]), "recover_workorder", scope_request)


def test_forbidden_action_never_admitted(supervised):
    from forge_factory.afo.authority import decide

    eff = policy.load(supervised["runtime"])
    for action in ("source_deploy", "edit_safety_policy", "release_signing", "service_restart"):
        assert not decide(action, dict(order_id=D.ORDERS[0]), afo=eff, log=False).allow


@pytest.mark.parametrize("change", ["hash", "source", "epoch", "guardian", "private_mode"])
def test_forged_stale_rebound_context_refuses(supervised, monkeypatch, change):
    from forge_factory.afo import line_recovery_control as C

    if change == "hash":
        monkeypatch.setenv(D.SHA, "0" * 64)
    elif change == "source":
        monkeypatch.setattr(C, "revision", lambda: dict(commit="b" * 40, dirty=False))
    elif change == "epoch":
        operations.Intent().set("RUNNING", actor="OWNER", reason="New epoch", expected_epoch=1)
    elif change == "guardian":
        monkeypatch.setattr(D, "guardian_alive", lambda *_: False)
    else:
        Path(supervised["ref"]["path"]).chmod(0o644)
    with pytest.raises(Refused):
        D.current(store=supervised["store"])


def test_retry_and_restart_never_reset_accounting(supervised):
    ledger = MissionLedger(supervised["store"])
    before = ledger.snapshot(D.MISSION)
    D.current(store=supervised["store"])
    D.current(store=supervised["store"])
    assert ledger.snapshot(D.MISSION) == before
    ledger.execution(D.MISSION, "next-product", "PRODUCT", reserved_tokens=100)
    assert D.current(store=supervised["store"])["mission"]["limits"] == before["limits"]
    assert ledger.snapshot(D.MISSION)["attempts"] == 1
    assert ledger.snapshot(D.MISSION)["charged_tokens"] == 100


def test_control_binding_requires_exact_document(supervised):
    from forge_factory.afo import line_recovery_control as C

    eff = policy.load(supervised["runtime"])
    req = dict(order_id=D.ORDERS[0], driver_class=DRIVER, model=supervised["control"]["profile"])
    assert C.configuration(supervised["control_ref"], eff, request=req) == supervised["control"]
    changed = copy.deepcopy(supervised["control"])
    changed["mission"]["limits"]["max_attempts"] += 1
    p = Path(supervised["control_ref"]["path"]).with_name("forged.json")
    immutable_json(p, changed)
    with pytest.raises(Refused):
        C.configuration(dict(path=str(p), sha256=sha256_file(p)), eff, request=req)


def test_agent_context_cannot_issue_record(supervised, monkeypatch):
    monkeypatch.setenv("FORGE_AGENT_ROLE", "swe6-author")
    with pytest.raises(Refused, match="OWNER_DEVELOPMENT_EXTERNAL_OPERATOR_REQUIRED"):
        D.create(
            supervised["store"],
            control_ref=supervised["control_ref"],
            runtime_policy=supervised["runtime"],
            line_policy=supervised["line"],
            directive=D.DIRECTIVE,
            expiry_ticket=supervised["ticket"],
        )


@pytest.fixture
def native_job(supervised, tmp_path, monkeypatch):
    from forge_factory import workorder
    from forge_factory.afo import line_product_context, product_job
    from forge_factory.afo.execution_lifecycle import Executions
    from forge_factory.lrtx.profile import load
    from test_afo_m2_queue import _env

    store = supervised["store"]
    control = supervised["control"]
    eff = policy.load(supervised["runtime"])
    repo = tmp_path / "input-repo"
    (repo / "afo-manifests").mkdir(parents=True)
    oid, _ = store.submit(
        _env(repo, rid=D.ORDERS[0], model=control["profile"], driver_class=DRIVER, tenant_scope="line-local"),
        repo=repo,
        max_queued=10,
    )
    epoch = store.acquire_lease("line:local", "PRIVATE-TEST", 300)
    aid = store.admit(
        oid,
        epoch=epoch,
        scope="line:local",
        policy_sha256=eff.sha256,
        authorization_id="OWNER_SUPERVISED_DEVELOPMENT",
        max_concurrent=1,
    )
    MissionLedger(store).link(D.MISSION, oid)
    attempt = store.attempts(oid)[-1]
    assert attempt["attempt_id"] == aid
    attempt["record"]["workspace_ref"] = "workorder:" + D.ORDERS[0]
    ws = tmp_path / "state/workorders" / D.ORDERS[0] / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    model = D.RUN_MODEL
    monkeypatch.setattr(workorder, "factory_revision", lambda: dict(commit="a" * 40, dirty=False))
    manifest = dict(
        model=model,
        profile=control["profile"],
        operations_epoch=1,
        line_role_authority_ref=supervised["control_ref"],
        line_origin={},
        product_attempt_token_reservations=[1048576] * 4,
    )
    job = product_job.prepare(store, store.order(oid), attempt, "c" * 32, manifest, eff)
    product_job.install(ws, {k: job[k] for k in ("job_id", "nonce", "mission_id", "order_id", "attempt_id", "operations_epoch")})
    (ws / ".forge-run/workflow.fabro").write_text(
        'digraph G {\ninspect_serve [script="python -m forge_factory.lrtx.stack serve --model qwen3.8:27b-q8_0"]\ninspect [prompt="PRIVATE TEST",model="qwen3.8:27b-q8_0"]\ninspect_serve -> inspect [condition="outcome=succeeded"]\n}\n'
    )
    (ws / ".forge-run/binding.json").write_text(
        json.dumps(dict(workspace=str(ws), nodes=dict(inspect=dict(role="swe6-inspector"))))
    )
    (ws / ".forge-run/model-profile.json").write_text(json.dumps(dict(default=model)))
    job.pop("line_origin", None)
    job["line_product_context"] = line_product_context.capture(ws, job, load(control["profile"]))
    with store.tx() as c:
        c.execute("UPDATE afo_product_jobs SET record=? WHERE job_id=?", (canonical_json(job).decode(), job["job_id"]))
    execution = Executions(store)
    execution.dispatch_intent(job["job_id"])
    execution.adopt(job["job_id"], ["PRIVATE-NATIVE-API-ID"])
    return dict(
        **supervised,
        job=job,
        execution=execution,
        body=dict(
            model="qwen3.8:27b-q8_0",
            messages=[],
            max_tokens=100,
            tools=[{"type": "function", "function": {"name": "PRIVATE", "parameters": {"type": "object"}}}],
            reasoning_effort="medium",
            temperature=None,
        ),
    )


def test_existing_role_request_ledger_and_nonce_integration(native_job):
    from forge_factory.afo import request_admission as A
    from forge_factory.lrtx.role_capability import admit_job

    p = native_job
    store = p["store"]
    job = p["job"]
    body = p["body"]
    selected = __import__("forge_factory.afo.line_product_context", fromlist=["request_job"]).request_job(
        job, "swe6-inspector", body["model"], policy.load()
    )
    assert admit_job(selected, "swe6-inspector", input_tokens=10, output_tokens=100, body=body) == dict(
        qualification_only=True, qualified=False
    )
    from forge_factory.afo.product_job import from_native

    correlated = from_native(store, "PRIVATE-NATIVE-API-ID")
    assert correlated == dict(job_id=job["job_id"], nonce=job["nonce"])
    binding = dict(**correlated, request_id="PRIVATE-REQUEST", role="swe6-inspector")
    measure = dict(sha256=digest(body), input_tokens=10, provider_instance_sha256=digest(None))
    rec = A.reserve(store, binding, body, measurement=measure)
    A.start(store, rec, body)
    assert MissionLedger(store).snapshot(D.MISSION)["requests"] == 1
    with pytest.raises(Refused, match="GENERATION_ALREADY_RESERVED_OR_SENT"):
        A.reserve(store, binding, body, measurement=measure)
    assert p["execution"].get(job["job_id"])["resource_lease"] == "HELD"
    assert MissionLedger(store).snapshot(D.MISSION)["attempts"] == 1


def test_guardian_exit_between_reservation_and_effect_refuses_and_holds(native_job):
    from forge_factory.afo import request_admission as A

    p = native_job
    job = p["job"]
    body = p["body"]
    store = p["store"]
    binding = dict(job_id=job["job_id"], nonce=job["nonce"], request_id="PRIVATE-REQUEST", role="swe6-inspector")
    rec = A.reserve(
        store, binding, body, measurement=dict(sha256=digest(body), input_tokens=10, provider_instance_sha256=digest(None))
    )
    before = MissionLedger(store).snapshot(D.MISSION)
    D.close_guardian(p["ref"])
    assert policy.load().mode == "OBSERVE_ONLY"
    with pytest.raises(Refused):
        A.start(store, rec, body)
    assert p["execution"].get(job["job_id"])["resource_lease"] == "HELD"
    assert MissionLedger(store).snapshot(D.MISSION) == before


def test_wrong_nonce_and_changed_role_config_reserve_nothing(native_job):
    from forge_factory.afo import request_admission as A

    p = native_job
    job = p["job"]
    body = p["body"]
    store = p["store"]
    before = MissionLedger(store).snapshot(D.MISSION)
    b = dict(job_id=job["job_id"], nonce="FOREIGN", request_id="PRIVATE", role="swe6-inspector")
    with pytest.raises(Refused, match="GENERATION_NONCE_MISMATCH"):
        A.reserve(store, b, body)
    b["nonce"] = job["nonce"]
    body["temperature"] = 1
    with pytest.raises(Refused, match="CONFIGURATION_UNDECLARED"):
        A.reserve(store, b, body, measurement=dict(sha256=digest(body), input_tokens=10, provider_instance_sha256=digest(None)))
    assert MissionLedger(store).snapshot(D.MISSION) == before


def test_copied_forged_record_cannot_be_attested_by_real_guardian(supervised, monkeypatch):
    value = json.loads(Path(supervised["ref"]["path"]).read_text())
    value["order_ids"].append("OUTSIDE-SCOPE")
    p = Path(supervised["ref"]["path"]).with_name(digest(value) + ".json")
    p.write_bytes(canonical_json(value))
    p.chmod(0o600)
    monkeypatch.setenv(D.FILE, str(p))
    monkeypatch.setenv(D.SHA, sha256_file(p))
    with pytest.raises(Refused):
        D.current(store=supervised["store"])


def test_actual_mapped_process_cannot_mint_even_with_both_forged_json_anchors(supervised):
    import subprocess
    import sys

    code = r"""
import os,json,sys
from pathlib import Path
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import canonical,digest,Refused
from forge_factory.lrtx.provider_process import identity,owner_view
original=Path(os.environ[D.FILE]);value=json.loads(original.read_text())
intent=Path(os.environ['FORGE_OPERATIONS_INTENT']);state=json.loads(intent.read_text())
ns=os.readlink('/proc/self/ns/user');mapping=owner_view(os.getpid())['uid_map']
state['control_context']['user_namespace']=ns;state['control_context']['uid_map']=mapping
intent.write_bytes(canonical(state))
value['control_context']['user_namespace']=ns;value['control_context']['uid_map']=mapping
value['guardian_pid']=os.getpid();value['guardian']={k:v for k,v in identity(os.getpid()).items()if k!='state'};value['guardian_view']=owner_view(os.getpid())
p=original.with_name(digest(value)+'.json');p.write_bytes(canonical(value));p.chmod(0o600)
os.environ[D.FILE]=str(p);os.environ[D.SHA]=__import__('hashlib').sha256(p.read_bytes()).hexdigest()
try:D.current()
except Refused as exc:
 assert exc.code=='OWNER_DEVELOPMENT_ISSUER_STORE_BINDING_REQUIRED',exc.code
 print('ACTUAL_MAPPED_FAKE_GUARDIAN_REFUSED')
else:raise AssertionError('FORGED_AUTHORITY')
"""
    r = subprocess.run(
        ["unshare", "--user", "--map-root-user", sys.executable, "-c", code], text=True, capture_output=True, timeout=10
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "ACTUAL_MAPPED_FAKE_GUARDIAN_REFUSED"


def test_actual_compiled_host_artifact_cannot_write_host_or_connect_control_socket(supervised, tmp_path):
    import socket
    import subprocess
    import tempfile

    from forge_factory.common import REPO_ROOT
    from forge_factory.mcp.sdk import run_argv

    with tempfile.TemporaryDirectory(prefix="owner-dev-host-boundary-") as td:
        host = Path(td)
        private = host / "host-only"
        private.write_text("UNCHANGED")
        control_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        control_socket.bind(str(host / "control.sock"))
        control_socket.listen(4)
        build = tmp_path / "build"
        build.mkdir()
        c = build / "boundary.c"
        binary = build / "boundary"
        c.write_text(r"""
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv) {
 if(argc!=5)return 90;
 int fd=open(argv[1],O_WRONLY|O_APPEND),w=fd>=0;if(fd>=0)close(fd);
 int source=open(argv[3],O_WRONLY),s=source>=0;if(source>=0)close(source);
 int sock=socket(AF_UNIX,SOCK_STREAM,0);struct sockaddr_un a={.sun_family=AF_UNIX};
 if(strlen(argv[2])>=sizeof(a.sun_path))return 91;strcpy(a.sun_path,argv[2]);
 int connected=connect(sock,(void*)&a,sizeof(a))==0;close(sock);
 printf("host_write=%d host_socket=%d source_write=%d\n",w,connected,s);
 return (w+2*connected+4*s)==atoi(argv[4])?0:92;
}
""")
        r = subprocess.run(["cc", str(c), "-o", str(binary)], capture_output=True, timeout=20)
        assert r.returncode == 0, r.stderr
        source = REPO_ROOT / "factory/python/forge_factory/afo/owner_supervised_development.py"
        before = sha256_file(source)
        baseline = subprocess.run(
            [str(binary), str(private), str(host / "control.sock"), str(source), "7"], capture_output=True, timeout=10
        )
        assert baseline.returncode == 0, baseline.stdout
        protected = run_argv([str(binary), str(private), str(host / "control.sock"), str(source), "0"], build, 10, {binary.name})
        assert protected.exit_code == 0, (protected.stdout, protected.stderr)
        assert protected.stdout.strip() == b"host_write=0 host_socket=0 source_write=0"
        assert private.read_text() == "UNCHANGED" and sha256_file(source) == before
        control_socket.close()


def test_missing_scoped_backend_never_uses_plain_host_subprocess(supervised, monkeypatch, tmp_path):
    from forge_factory.reliability import isolation

    monkeypatch.setattr(isolation, "available", lambda: False)
    with pytest.raises(Refused, match="SCOPED_EXECUTION_UNAVAILABLE"):
        isolation.execute("maintainer", ["false"], cwd=tmp_path, env={}, writable=[tmp_path])


def test_existing_default_placer_still_requires_signed_production_grant(supervised):
    from forge_factory.afo.line_orders import load_policy, verify_grant

    result = verify_grant(
        load_policy(supervised["line"]), now=time.time(), base=Path(supervised["line"]).parent / "no-signatures"
    )
    assert not result.allow
    assert result.code != "AUTH_OK"
    assert D.DevelopmentGrant(load_policy(supervised["line"])).view()["code"] == "OWNER_SUPERVISED_DEVELOPMENT_UNACCEPTED"


def test_native_stdio_config_explicitly_propagates_dev_confinement_marker(supervised):
    from forge_factory.fabro.runconfig import render_run_toml

    data = render_run_toml(
        "private.fabro", "PRIVATE", Path("/PRIVATE/binding.json"), {"tests": dict(module="forge_factory.mcp.servers.tests")}
    )
    import tomllib

    parsed = tomllib.loads(data)
    env = parsed["run"]["agent"]["mcps"]["tests"]["env"]
    assert env[D.FILE] == supervised["ref"]["path"] and env[D.SHA] == supervised["ref"]["sha256"]


def test_owner_development_uses_existing_placer_but_never_production_feed(supervised, monkeypatch, tmp_path):
    from types import SimpleNamespace

    from forge_factory.afo import line_launcher as LL
    from forge_factory.afo import line_orders as O
    from forge_factory.afo.line_conductor import feed_path, heartbeat_path

    feed_path().write_text("PRIVATE EXISTING PRODUCTION OBSERVE FEED")
    heartbeat_path().write_text("PRIVATE EXISTING PRODUCTION PID OBSERVE HEARTBEAT")
    before = (feed_path().read_bytes(), heartbeat_path().read_bytes(), MissionLedger(supervised["store"]).snapshot(D.MISSION))
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    monkeypatch.setenv("FORGE_DURABLE_NATIVE_HEADER", "1")
    cfg = SimpleNamespace(stack_root=tmp_path, launch_dir=tmp_path / "launch")
    monkeypatch.setattr(LL.LineConfig, "from_env", lambda: cfg)

    class Line:
        def free_bytes(self):
            return 100 * 1024**3

        def gpu_holders(self):
            return []

        def live_runs(self):
            return []

        def launch_dir(self):
            return tmp_path / "launch"

    monkeypatch.setattr(O, "RealLine", lambda _: Line())
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir()
    assert (
        D.main(
            [
                "--control",
                supervised["control_ref"]["path"],
                "--runtime-policy",
                str(supervised["runtime"]),
                "--line-policy",
                str(supervised["line"]),
                "--campaigns",
                str(campaigns),
                "--expiry-ticket",
                str(supervised["ticket_path"]),
                "--max-cycles",
                "1",
            ]
        )
        == 0
    )
    assert (
        feed_path().read_bytes(),
        heartbeat_path().read_bytes(),
        MissionLedger(supervised["store"]).snapshot(D.MISSION),
    ) == before
    rows = list((Path(supervised["ref"]["path"]).parent).glob("*.audit.jsonl"))
    assert len(rows) == 1
    record = json.loads(rows[0].read_text())
    assert record["mode"] == D.MODE and record["acceptance"] == "UNACCEPTED" and record["placement"]["actions"] == []


def test_real_mission_exhaustion_refuses_before_any_new_execution(supervised):
    ledger = MissionLedger(supervised["store"])
    for i in range(D.ATTEMPTS):
        ledger.execution(D.MISSION, "private-remaining-" + str(i), "PRODUCT", reserved_tokens=1)
    before = ledger.snapshot(D.MISSION)
    assert before["attempts"] == D.ATTEMPTS
    # The last execution can still settle; it never mints another.
    D.current(store=supervised["store"])
    with pytest.raises(Refused, match="MISSION_ALLOWANCE_EXHAUSTED"):
        ledger.execution(D.MISSION, "FORBIDDEN-SECOND", "PRODUCT", reserved_tokens=1)
    assert ledger.snapshot(D.MISSION) == before


@pytest.mark.parametrize("kind", ["canonical-state", "intent", "kernel-view", "policy"])
def test_privileged_execution_roots_never_mounted_for_untrusted_children(supervised, kind):
    record = D.current(store=supervised["store"])
    path = {
        "canonical-state": Path(record["store_path"]).parent,
        "intent": Path(record["intent_path"]).parent,
        "kernel-view": Path(record["store_path"]).parents[2] / "run",
        "policy": Path(record["runtime_policy_ref"]["path"]).parent,
    }[kind]
    with pytest.raises(Refused, match="PRIVILEGED_EXECUTION_MOUNT_DENIED"):
        D._untrusted_scope(record, [path], [])
    with pytest.raises(Refused, match="PRIVILEGED_EXECUTION_MOUNT_DENIED"):
        D._untrusted_scope(record, [], [path])


@pytest.mark.parametrize("change", ["boot", "stale", "deadline", "rtt", "upper", "anchor"])
def test_issuance_rejects_invalid_actual_utc_ticket(supervised, change):
    ticket = dict(supervised["ticket"])
    if change == "boot":
        ticket["remote_boot_id"] = "foreign-boot"
    elif change == "stale":
        ticket["fresh_until_monotonic"] = time.monotonic() - 1
    elif change == "deadline":
        ticket["deadline_monotonic"] += 30
    elif change == "rtt":
        ticket["RTT_seconds"] = -1
    elif change == "upper":
        ticket["external_utc_upper_at_remote_sample"] = supervised["limits"]["deadline"]
    else:
        ticket["anchor_sha256"] = "not-an-anchor"
    with pytest.raises(Refused, match="ACTUAL_UTC_EXPIRY_TICKET_INVALID"):
        D.validate_expiry_ticket(ticket, supervised["limits"]["deadline"])


def test_live_guardian_outlives_issuance_freshness_but_not_fixed_deadline(supervised, monkeypatch):
    before = MissionLedger(supervised["store"]).snapshot(D.MISSION)
    ticket = supervised["ticket"]
    monkeypatch.setattr(D.time, "monotonic", lambda: ticket["fresh_until_monotonic"] + 1)
    assert D.current(store=supervised["store"])["expiry_ticket"] == ticket
    monkeypatch.setattr(D.time, "monotonic", lambda: ticket["deadline_monotonic"])
    with pytest.raises(Refused, match="ACTUAL_UTC_WINDOW_EXPIRED"):
        D.current(store=supervised["store"])
    assert MissionLedger(supervised["store"]).snapshot(D.MISSION) == before


def test_provider_readiness_refuses_legacy_live_and_unknown_before_placing(supervised, tmp_path, monkeypatch):
    from forge_factory.lrtx import stack

    root = tmp_path
    assert D.provider_preflight(root)["state"] == "ABSENT"
    path = root / "run/services.json"
    path.parent.mkdir()
    path.write_text(json.dumps(dict(processes={"llama": dict(pid=123)})))
    path.chmod(0o600)
    monkeypatch.setattr(stack, "process_identity", lambda _: dict(boot_id="PRIVATE", start_ticks=1, uid=1000))
    assert D.provider_preflight(root)["state"] == "NEEDS_KNOWN_RETIREMENT"
    assert D.provider_preflight(root)["placing"] is False
    path.write_text("{broken")
    assert D.provider_preflight(root)["state"] == "UNKNOWN"
    assert D.provider_preflight(root)["placing"] is False


def test_bound_job_cannot_rebind_to_new_guardian_lifetime(native_job, monkeypatch):
    from forge_factory.afo import line_recovery_control as C

    p = native_job
    before = MissionLedger(p["store"]).snapshot(D.MISSION)
    job = p["job"]
    assert C.require_job_binding(job, p["control"], store=p["store"])
    newer = D.create(
        p["store"],
        control_ref=p["control_ref"],
        runtime_policy=p["runtime"],
        line_policy=p["line"],
        directive=D.DIRECTIVE,
        expiry_ticket=p["ticket"],
    )
    try:
        monkeypatch.setenv(D.FILE, newer["path"])
        monkeypatch.setenv(D.SHA, newer["sha256"])
        with pytest.raises(Refused, match="JOB_AUTHORITY_REBOUND"):
            C.require_job_binding(job, p["control"], store=p["store"])
        assert MissionLedger(p["store"]).snapshot(D.MISSION) == before
    finally:
        D.close_guardian(newer)


def test_suspend_cannot_extend_actual_utc_window(supervised, monkeypatch):
    record = D.current(store=supervised["store"])
    monkeypatch.setattr(D.time, "clock_gettime", lambda clock: record["expiry_boottime_deadline"])
    with pytest.raises(Refused, match="ACTUAL_UTC_WINDOW_EXPIRED"):
        D.current(store=supervised["store"])


def test_same_guardian_view_cannot_rebind_different_provider_profile(supervised, tmp_path):
    record = D.current(store=supervised["store"])
    instance = dict(
        root=str(tmp_path),
        profile=record["profile"],
        profile_sha256=record["profile_sha256"],
        owner_development_view=dict(
            record_sha256=digest(record),
            socket_identity=record["guardian_socket_identity"],
            store_identity=record["store_identity"],
            store_path=record["store_path"],
        ),
    )
    D.require_compatible_provider(instance)
    instance["profile"] = "foreign-profile"
    with pytest.raises(Refused, match="KNOWN_PROVIDER_REPLACEMENT_REQUIRED"):
        D.require_compatible_provider(instance)


@pytest.mark.parametrize("change", ["extra_model", "extra_role", "sampling", "task_class", "context"])
def test_issuance_never_expands_original_trial_envelopes(supervised, monkeypatch, change):
    from forge_factory.afo import product_role_trial as trials

    control = copy.deepcopy(supervised["control"])
    if change == "extra_model":
        control["product_role_trials"]["foreign-model"] = control["product_role_trial"]
    else:
        resolve = trials.resolve

        def changed(ref):
            doc = copy.deepcopy(resolve(ref))
            identities = next(iter(doc["roles"].values()))
            if change == "extra_role":
                doc["roles"]["foreign-role"] = identities
            elif change == "sampling":
                identities[0]["sampling"]["temperature"] = 1
            elif change == "task_class":
                identities[0]["task_class"] = "FOREIGN"
            else:
                identities[0]["context_tokens"] += 1
            return doc

        monkeypatch.setattr(trials, "resolve", changed)
    before = MissionLedger(supervised["store"]).snapshot(D.MISSION)
    with pytest.raises(Refused, match="ORIGINAL_ROLE_ENVELOPES_REQUIRED"):
        D._trial_envelopes(control)
    assert MissionLedger(supervised["store"]).snapshot(D.MISSION) == before


def test_suspend_between_sample_and_issuance_never_stretches_ticket(supervised, monkeypatch):
    ticket = supervised["ticket"]
    monkeypatch.setattr(D.time, "clock_gettime", lambda clock: ticket["remote_boottime"] + 61)
    with pytest.raises(Refused, match="ACTUAL_UTC_EXPIRY_TICKET_INVALID"):
        D.validate_expiry_ticket(ticket, supervised["limits"]["deadline"])


def _wo(lineage, phase, k=1):
    return D._name(D._LINEAGE[lineage], phase, k)


@pytest.mark.parametrize(
    ("order_id", "driver_class"),
    [
        (_wo("gpio-ll", "SWE.1"), "STM32N6_SPI_LL_ST"),
        (_wo("spi-ll", "SWE.6", 64), "STM32N6_GPIO_LL_ST"),
        (_wo("tim-ll", "SWE.3"), sorted(set(D.ORDER_DRIVERS.values()))),
        ("WO-F014-SWE6-AFOQUAL-20261104-L90AC", D.LEGACY_DRIVER),  # allowance C, closed
        ("WO-F014-SWE6-AFOQUAL-20261104-L90AD", D.LEGACY_DRIVER),  # allowance D, never registered
        ("WO-F014-SWE1-GPIOL-20261107-L40BM", "STM32N6_GPIO_LL_ST"),  # k = 65
        ("WO-F014-SWE7-GPIOL-20261107-L40", "STM32N6_GPIO_LL_ST"),
    ],
)
def test_permit_refuses_cross_pairs_closed_and_beyond_orders(supervised, order_id, driver_class):
    eff = policy.load(supervised["runtime"])
    request = dict(order_id=order_id, driver_class=driver_class, model=supervised["control"]["profile"])
    assert not D.permit(eff, "recover_workorder", request)


def test_permit_admits_every_lineage_with_its_own_driver(supervised):
    eff = policy.load(supervised["runtime"])
    record = D.current(store=supervised["store"])
    assert record["order_ids"] == list(D.ORDERS) and record["order_drivers"] == D.ORDER_DRIVERS
    assert record["driver_class"] == ["STM32N6_GPIO_LL_ST", "STM32N6_SPI_HAL", "STM32N6_SPI_LL_ST", "STM32N6_TIM_HAL",
                                      "STM32N6_TIM_LL_ST", "STM32N6_USART_LL_ST", "STM32N6_WWDG_HAL",
                                      "STM32N6_WWDG_LL_ST"]
    for L in D.LINEAGES:
        for order_id in (_wo(L["id"], "SWE.1"), _wo(L["id"], "SWE.6", 64)):
            request = dict(order_id=order_id, driver_class=L["driver_class"], model=supervised["control"]["profile"])
            assert D.permit(eff, "launch_workorder", request)


def _lineage(spec):
    from forge_factory.afo.line_campaign import PHASES, Lineage
    from forge_factory.quality import defaults

    return Lineage(campaign_id=D.CAMPAIGN, id=spec["id"], status="ACTIVE", example=spec["example"], tag=spec["tag"],
                   series=spec["series"], driver_class=spec["driver_class"], factory_revision="a" * 40,
                   profile=D.PROFILE, run_model=D.RUN_MODEL, purpose="ASPICE_ONLY", phases=PHASES, priority=50,
                   quality=defaults("ASPICE_ONLY"))


def _planner_order(supervised, phase, kind, k, resume_from=None, resume_upto=None, lineage="usart-ll"):
    """The Planner's own order builder (line_orders.phase_order), as Planner._order calls it."""
    from forge_factory.afo.line_orders import phase_order

    L = _lineage(D._LINEAGE[lineage])
    return phase_order(L, phase, kind, wo=L.wo(phase, k), resume_from=resume_from, provided_from=None,
                       resume_upto=resume_upto, quality_via="REVISION", durable_control=supervised["control_ref"])


# (phase, kind, k, resume_from, resume_upto) as line_orders.Planner.decide and line_recovery_coordination produce them.
PLANNER_SHAPES = {
    "START": ("SWE.1", "START", 1, None, None),
    "START_RETRY": ("SWE.1", "RETRY", 2, None, None),
    "START_RELAUNCH_INFRA": ("SWE.1", "RELAUNCH_INFRA", 1, None, None),
    "CHAIN": ("SWE.3", "CHAIN", 1, ("SWE.2", 4), None),
    "CHAIN_RETRY": ("SWE.3", "RETRY", 2, ("SWE.2", 4), None),
    "CHAIN_RETRY_INFRA": ("SWE.6", "RETRY_INFRA", 64, ("SWE.5", 1), None),
    "CHAIN_RELAUNCH": ("SWE.4", "RELAUNCH", 3, ("SWE.3", 1), None),
    "UPSTREAM": ("SWE.2", "UPSTREAM", 2, ("SWE.5", 1), "SWE.2"),
    "UPSTREAM_RETRY": ("SWE.2", "RETRY", 3, ("SWE.5", 1), "SWE.2"),
    "RECOVERY_SAME_PHASE": ("SWE.4", "RETRY", 2, ("SWE.4", 1), "SWE.4"),
    "RECOVERY_OWNER_PHASE": ("SWE.2", "RETRY", 2, ("SWE.4", 1), "SWE.2"),
    "RECOVERY_SWE1": ("SWE.1", "RETRY", 3, ("SWE.1", 2), "SWE.1"),
}


def _shape(supervised, name, lineage="usart-ll"):
    phase, kind, k, source, upto = PLANNER_SHAPES[name]
    resume_from = _wo(lineage, *source) if source else None
    return _planner_order(supervised, phase, kind, k, resume_from, upto, lineage=lineage)


@pytest.mark.parametrize("name", sorted(PLANNER_SHAPES))
def test_validate_order_accepts_every_planner_and_recovery_shape(supervised, name):
    for lineage in ("gpio-ll", "tim-ll"):
        D.validate_order(_shape(supervised, name, lineage))


@pytest.mark.parametrize(
    "change",
    [
        dict(provided_from="WO-F014-SWE6-CRCL-20261103-L24"),
        dict(phase="SWE.4"),
        dict(stop_after="SWE.4"),
        dict(example="0011l-st-cube-spi-swe1-gen"),
        dict(example="0014m-crc-hal"),
        dict(driver_class="STM32N6_SPI_LL_ST"),
        dict(revision="b" * 40),
        dict(profile="foreign-profile"),
        dict(run_model="qwen3.8:27b-q8_0"),
        dict(purpose="QM"),
        dict(campaign_id="CMP-FOREIGN"),
        dict(lineage="CMP-OMNI2-ST-LL-20261107/spi-ll"),
        dict(durable_control=None),
        dict(quality=None),
        dict(wo="WO-F014-SWE3-USARTL-20261107-L42BM"),  # k = 65
        dict(wo="WO-F014-SWE6-AFOQUAL-20261104-L90AD"),
        dict(resume_from=None),  # only SWE.1 starts from nothing
        dict(resume_from="WO-F014-SWE2-GPIOL-20261107-L40"),  # another lineage
        dict(resume_from="WO-F014-SWE1-USARTL-20261107-L42"),  # skips SWE.2
        dict(resume_from="WO-F014-SWE5-CRCHAL-20261104-L34G"),  # the old seed
        dict(resume_from="WO-F014-SWE3-USARTL-20261107-L42"),  # same phase without resume_upto
        dict(kind="UPSTREAM"),
        dict(kind="START"),
        dict(resume_upto="SWE.2"),
    ],
)
def test_validate_order_refuses_outside_the_campaign_envelope(supervised, change):
    order = {**_shape(supervised, "CHAIN"), **change}
    with pytest.raises(Refused, match=D.ENVELOPE_REFUSED):
        D.validate_order(order)


@pytest.mark.parametrize(
    ("name", "change"),
    [
        ("START", dict(wo="WO-F014-SWE2-USARTL-20261107-L42", phase="SWE.2", stop_after="SWE.2")),
        ("START", dict(kind="CHAIN")),
        ("START", dict(resume_upto="SWE.1")),
        ("UPSTREAM", dict(resume_upto=None)),
        ("UPSTREAM", dict(resume_upto="SWE.3")),
        ("UPSTREAM", dict(kind="CHAIN")),
        ("RECOVERY_SAME_PHASE", dict(kind="UPSTREAM")),
        ("RECOVERY_OWNER_PHASE", dict(resume_from="WO-F014-SWE1-USARTL-20261107-L42")),
    ],
)
def test_validate_order_refuses_shapes_the_planner_never_makes(supervised, name, change):
    with pytest.raises(Refused, match=D.ENVELOPE_REFUSED):
        D.validate_order({**_shape(supervised, name), **change})


def test_historical_control_validates_only_with_legacy_envelopes(supervised, monkeypatch):
    monkeypatch.setattr(D, "ROLE_ENVELOPES_E", PINNED_ROLE_ENVELOPES_E)
    assert set(PINNED_ROLE_ENVELOPES_E) == set(D.LEGACY_ROLE_ENVELOPES)
    assert all(len(v) == 64 for v in PINNED_ROLE_ENVELOPES_E.values())
    historical = copy.deepcopy(supervised["control"])
    historical["mission"]["mission_id"] = D.PRIOR_MISSION
    D._trial_envelopes(historical)
    D._trial_envelopes(historical, envelopes=D.LEGACY_ROLE_ENVELOPES)
    with pytest.raises(Refused, match="ORIGINAL_ROLE_ENVELOPES_REQUIRED"):
        D._trial_envelopes(historical, envelopes=D.ROLE_ENVELOPES_E)
    for envelopes in (None, D.LEGACY_ROLE_ENVELOPES, D.ROLE_ENVELOPES_E):
        with pytest.raises(Refused, match="ORIGINAL_ROLE_ENVELOPES_REQUIRED"):
            D._trial_envelopes(supervised["control"], envelopes=envelopes)


def test_mission_e_cannot_issue_before_its_envelopes_are_pinned(supervised, monkeypatch):
    monkeypatch.setattr(D, "ROLE_ENVELOPES_E", PINNED_ROLE_ENVELOPES_E)
    with pytest.raises(Refused, match="ORIGINAL_ROLE_ENVELOPES_REQUIRED"):
        D.create(
            supervised["store"], control_ref=supervised["control_ref"], runtime_policy=supervised["runtime"],
            line_policy=supervised["line"], directive=D.DIRECTIVE, expiry_ticket=supervised["ticket"],
        )


def test_trial_order_ids_name_every_campaign_order():
    from forge_factory.afo.queue import order_id_for

    ids = D.trial_order_ids()
    assert len(ids) == len(set(ids)) == len(D.ORDERS) and ids[0] == order_id_for("line-local", D.ORDERS[0])


@pytest.mark.parametrize("name", ["ornith-trial-e.json", "qwen-trial-e.json"])
def test_mission_e_trial_assets_hash_to_the_pinned_envelopes(name):
    trial = json.loads((Path(__file__).parent / "fixtures/owner-supervised-development" / name).read_text())
    normalized = {role: [{k: v for k, v in i.items() if k != "adapter_revision"} for i in ids]
                  for role, ids in trial["roles"].items()}
    assert digest(normalized) == D.ROLE_ENVELOPES_E[trial["model"]]
    roles = set(trial["roles"])
    assert roles == ({f"swe{n}-author" for n in range(1, 7)} | {"release-manager", "afo-recovery-planner",
                     "afo-factory-maintainer"} if "ornith" in trial["model"] else {f"swe{n}-inspector" for n in range(1, 7)})
