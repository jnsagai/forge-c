"""Native synthetic artifacts traverse the real post-authoring verification consumers."""

import copy
import json
import os
from pathlib import Path

import pytest
from forge_factory.assurance import mutation, register_wp
from forge_factory.assurance import safec_oracle as SO
from forge_factory.lrtx import profile as P
from forge_factory.safec_bridge import client as CL
from forge_factory.safec_bridge import contract as K
from forge_factory.safec_bridge import contracts as C
from forge_factory.safec_bridge import domain as D
from forge_factory.safec_bridge import obligations as OB
from forge_factory.safec_bridge import oracle as O
from test_safec_bridge_v02 import intent, special  # noqa: F401 - source-parsed synthetic fixture

PIN = os.environ.get("FORGE_SAFEC_V02_ENGINE_PIN")
pytestmark = pytest.mark.skipif(not PIN, reason="explicit independently pinned v02 engine required")


@pytest.fixture
def artifacts(special, tmp_path, monkeypatch):  # noqa: F811 - pytest imported fixture
    doc, raw = special
    prof = P.load("local-rtx-v2-omniverse2-wwdg-v02")
    ws = tmp_path / "consumer"
    (ws / ".forge-run").mkdir(parents=True)
    manifest = {
        "work_order": "SYNTHETIC-CONSUMER",
        "layer": "LL",
        "peripheral": "wwdg",
        "local_profile": {
            "id": prof["id"],
            "version": prof["version"],
            "config": prof["_path"],
            "config_sha256": prof["_sha256"],
            "semantic_profile": "register-io-0.2",
        },
    }
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))

    def build(_ws, *, semantic_profile="register-io-0.1"):
        value = copy.deepcopy(doc)
        value["profile"] = semantic_profile
        value["schema"] = C.domain_schema(semantic_profile)
        return value, C.canonical_bytes(value)

    monkeypatch.setattr(D, "build", build)
    data = json.loads(Path(PIN).read_bytes())
    pin = CL.EnginePin(Path(data["binary"]), data["binary_sha256"], data["source_commit_sha"], data["semantic_profile"])
    its = [
        intent("TST_CR", "LATCH", "set_field"),
        intent("TST_CR", "VALUE", "write_field", "127"),
        intent("TST_SR", "FLAG", "clear_field"),
    ]
    binding = {
        "workorder_id": manifest["work_order"],
        "workorder_sha256": C.sha256_bytes((ws / ".forge-run/manifest.json").read_bytes()),
        "source_manifest_sha256": C.sha256_bytes(raw),
        "policy_sha256": prof["_sha256"],
    }
    produced = {}
    for op in ("validate_intents", "derive_tests", "derive_contracts"):
        req, rraw = C.build_request(request_id=op, operation=op, engine=pin.expected(), binding=binding, intents=its)
        work = tmp_path / op
        out = CL.invoke(pin, req, rraw, work, domain=raw)
        assert out.admissible, out.record()
        contract = K.materialize(out, req, raw, work, pin)
        if op == "derive_tests":
            produced["oracle"] = O.materialize(out, contract, raw, work)
        if op == "derive_contracts":
            produced["obligations"] = OB.materialize(out, contract, raw, work)
    rec = {
        "schema": "forge-c/lrtx-register-oracle/1",
        "contract_semantic_digest": contract.semantic_digest,
        "domain_sha256": contract.domain_sha256,
        "engine": pin.expected(),
        "operations": list(contract.operations),
        "case_of_intent": {x["intent_id"]: "case-" + str(n) for n, x in enumerate(its)},
        "oracle": produced["oracle"],
    }
    ob = {
        "schema": "forge-c/lrtx-register-obligations/1",
        "contract_semantic_digest": contract.semantic_digest,
        "domain_sha256": contract.domain_sha256,
        "engine": pin.expected(),
        "obligations": produced["obligations"],
    }
    for path, value in [(SO.FILE, rec), (register_wp.OBLIGATIONS_FILE, ob)]:
        f = ws / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(value))
    return ws, rec, ob, manifest


def test_new_oracle_is_reverified_with_its_frozen_domain_family(artifacts):
    ws, rec, ob, manifest = artifacts
    verified, issues = SO.verified(ws)
    assert issues == [] and verified is not None, issues


def test_new_formal_obligations_reach_independent_downstream_checks(artifacts):
    ws, rec, ob, manifest = artifacts
    verified, issues = register_wp.verified(ws)
    assert issues == [] and verified is not None, issues
    assert verified["obligations"]["schema"] == "forge-c/register-io-obligations/2"


def test_mutation_operators_come_from_reverified_new_source(artifacts):
    ws, rec, ob, manifest = artifacts
    ops = mutation.register_ops(ws)
    assert ops and {"OMIT_WRITE", "FIELD_BIT_SHIFT"} <= {op[0] for op in ops}


@pytest.mark.parametrize(
    "change", ["profile-downgrade", "missing-engine", "stale-configuration", "corrupt-operation", "wrong-oracle-family", "rehashed-wrong-oracle"]
)
def test_downstream_oracle_never_accepts_stale_mixed_or_rehashed_records(artifacts, change):
    ws, rec, ob, manifest = artifacts
    if change == "profile-downgrade":
        rec["engine"]["semantic_profile"] = "register-io-0.1"
    elif change == "missing-engine":
        del rec["engine"]
    elif change == "stale-configuration":
        manifest["local_profile"]["config_sha256"] = "0" * 64
        (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    elif change == "corrupt-operation":
        rec["operations"][0]["encoded_value"] = "0x00000000"
    elif change == "wrong-oracle-family":
        rec["oracle"]["schema"] = "forge-c/register-io-oracle/1"
    else:
        rec["oracle"]["cases"][0]["expected_after"] = "0x00000000"
        body = {k: v for k, v in rec["oracle"].items() if k != "oracle_digest"}
        rec["oracle"]["oracle_digest"] = C.sha256_bytes(C.canonical_bytes(body))
    (ws / SO.FILE).write_text(json.dumps(rec))
    verified, issues = SO.verified(ws)
    assert verified is None and issues
    assert mutation.register_ops(ws) == []


def test_mixed_engine_on_obligations_is_refused_even_with_valid_inner_payload(artifacts):
    ws, rec, ob, manifest = artifacts
    ob["engine"]["source_commit_sha"] = "0" * 40
    (ws / register_wp.OBLIGATIONS_FILE).write_text(json.dumps(ob))
    verified, issues = register_wp.verified(ws)
    assert verified is None and issues
