"""Feature 011 / SafeC S013-T015: an adversarial payload corpus sent straight to the real pinned SafeC engine, past
the Forge-C client's own refusals. For every payload the engine must end within its limit, never panic, and either
refuse the usage (no result) or write a result that satisfies the public result schema and is never PASS.

Runs only when FORGE_SAFEC_ENGINE_PIN names a pinned engine.
"""
from __future__ import annotations

import json
import subprocess

import pytest
from forge_factory.safec_bridge import contracts as C
from test_safec_bridge_m2 import PIN, _engine, needs_engine, synthetic  # noqa: F401 - shared fixtures

GOOD = [{"intent_id": "EN-ON", "source_fact_ids": ["F-TST_CR-EN"], "register": "TST_CR", "field": "EN",
         "action": "set_field"}]


def _valid(raw_domain: bytes) -> dict:
    req, _ = C.build_request(request_id="CORPUS", operation="validate_intents", engine=_engine().expected(),
                             binding={"workorder_id": "WO-CORPUS", "workorder_sha256": "1" * 64,
                                      "source_manifest_sha256": C.sha256_bytes(raw_domain), "policy_sha256": "3" * 64},
                             intents=GOOD)
    return req


def _corpus(req: dict, domain: bytes) -> list[tuple[str, bytes, bytes | None]]:
    def j(d):
        return json.dumps(d).encode()

    deep = b"[" * 20000 + b"]" * 20000
    out = [("empty", b"", domain), ("not json", b"{not json", domain), ("array", b"[]", domain),
           ("invalid utf-8", b'{"request_id": "\xff\xfe"}', domain), ("deep nesting", deep, domain),
           ("nan", j(req).replace(b'"CORPUS"', b"NaN"), domain),
           ("huge integer", j({**req, "request_id": 10 ** 400}), domain),
           ("oversize", j({**req, "padding": "x" * (12 * 1024 * 1024)}), domain),
           ("duplicate key", b'{"operation": "validate_intents", ' + j(req)[1:], domain),
           ("unknown field", j({**req, "unexpected": True}), domain),
           ("wrong schema", j({**req, "schema": "forge-c/safec-bridge-request/999"}), domain),
           ("unknown operation", j({**req, "operation": "rm -rf"}), domain),
           ("domain not bound", j(req), domain + b" "), ("domain not json", j(req), b"{"),
           ("no domain", j(req), None)]
    trav = json.loads(json.dumps(req))
    trav["inputs"]["semantic_intents"][0]["register"] = "../../../etc/passwd"
    out.append(("path traversal register", j(trav), domain))
    many = json.loads(json.dumps(req))
    many["inputs"]["semantic_intents"] = [{**GOOD[0], "intent_id": f"I-{i}"} for i in range(20000)]
    out.append(("20000 intents", j(many), domain))
    return out


@needs_engine
def test_the_real_engine_never_passes_never_panics_on_hostile_payloads(synthetic, tmp_path):  # noqa: F811
    _, raw_domain = synthetic
    pin = _engine()
    seen = []
    for name, payload, domain in _corpus(_valid(raw_domain), raw_domain):
        d = tmp_path / name.replace(" ", "_")
        d.mkdir(parents=True)  # the engine creates its own evidence directory and refuses an existing one
        (d / "request.json").write_bytes(payload)
        argv = [str(pin.binary), "run", "--request", str(d / "request.json"), "--result", str(d / "result.json"),
                "--evidence-dir", str(d / "evidence")]
        if domain is not None:
            (d / "domain.json").write_bytes(domain)
            argv += ["--domain", str(d / "domain.json")]
        p = subprocess.run(argv, capture_output=True, timeout=60, env={}, cwd=d)
        assert p.returncode != 101 and b"panicked" not in p.stderr, (name, p.returncode, p.stderr[-300:])
        if (d / "result.json").is_file():
            res = json.loads((d / "result.json").read_bytes())
            assert C.schema_errors("result", res) == [], (name, C.schema_errors("result", res)[:3])
            assert res["status"] != "PASS", (name, res["status"])
            seen.append((name, res["status"]))
        else:
            assert p.returncode != 0, name  # no result is only acceptable as a refused usage
            seen.append((name, f"exit {p.returncode}"))
    assert len(seen) == 17
    # not vacuous: most payloads reach the engine's own decision and come back as a result (ERROR/STALE/FAIL)
    assert sum(not str(s).startswith("exit") for _n, s in seen) >= 14, seen
    print(json.dumps(seen))
    # the control: the same request, correctly bound, does pass (the corpus is not refused for an unrelated reason)
    d = tmp_path / "control"
    d.mkdir(parents=True)
    (d / "request.json").write_bytes(json.dumps(_valid(raw_domain)).encode())
    (d / "domain.json").write_bytes(raw_domain)
    subprocess.run([str(pin.binary), "run", "--request", str(d / "request.json"), "--result", str(d / "result.json"),
                    "--evidence-dir", str(d / "evidence"), "--domain", str(d / "domain.json")], timeout=60, env={},
                   cwd=d, capture_output=True)
    assert json.loads((d / "result.json").read_bytes())["status"] == "PASS"


@needs_engine
def test_control_characters_in_the_request_id_are_schema_valid_and_echoed_unchanged(synthetic, tmp_path):  # noqa: F811
    """Recorded finding (2026-10-22): the public request schema allows any 1-128 character request_id, so control
    characters pass and are echoed into the result. Forge-C builds request ids from fixed tags only; a display that
    shows them must filter (trace policy). Forbidding them would be a protocol version change in both repositories."""
    _, raw_domain = synthetic
    req = {**_valid(raw_domain), "request_id": "a\u0000b\u001b[31m"}
    assert C.schema_errors("request", req) == []
    d = tmp_path / "cc"
    d.mkdir()
    (d / "request.json").write_bytes(C.canonical_bytes(req))
    (d / "domain.json").write_bytes(raw_domain)
    subprocess.run([str(_engine().binary), "run", "--request", str(d / "request.json"), "--result",
                    str(d / "result.json"), "--evidence-dir", str(d / "evidence"), "--domain", str(d / "domain.json")],
                   timeout=60, env={}, cwd=d, capture_output=True)
    res = json.loads((d / "result.json").read_bytes())
    assert res["status"] == "PASS" and res["request_id"] == "a\u0000b\u001b[31m"
