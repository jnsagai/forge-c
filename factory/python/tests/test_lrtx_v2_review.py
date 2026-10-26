"""Feature 011 M4 (F011-T025..T027; F011-AT-019, AT-020, AT-022, AT-023): evidence-grounded SWE.1 inspection.

Typed claims about the frozen baseline are adjudicated by fixed rules: a claim the baseline contradicts is REFUTED,
a claim it proves is CONFIRMED, and a judgement the rules cannot decide STANDS. Claim identity ignores wording.
A FAIL made only of refuted claims gets one reinspection and is otherwise recorded as ADJUDICATED_PASS, with every
claim kept. The verdicts go through the unchanged check_inspection operation and inspect gate.
"""
from __future__ import annotations

import json

import pytest
from forge_factory.lrtx import review_semantic as RS
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1_semantic as SEM
from test_lrtx_swe1 import _gate, _scripted
from test_lrtx_v2_swe1 import SEM_ANSWERS, iwdg, pytestmark  # noqa: F401 - answers, v2 IWDG work order, skip marker


@pytest.fixture()
def frozen(iwdg, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(SEM_ANSWERS, []))
    assert SEM.visit(iwdg, "qwen3-coder:30b")["status"] == "PASS"
    assert _gate(iwdg, monkeypatch) == 0  # the semantic SWE.1 baseline, frozen by the unchanged gate
    return iwdg


def _c(assertion, target, detail="a concrete observation about the document", related=()):
    return {"assertion": assertion, "target_id": target, "related_ids": list(related), "detail": detail,
            "remediation": "fix it"}


def test_baseline_facts_come_from_the_frozen_work_products_only(frozen):
    f = RS.baseline_facts(frozen)
    assert len(f["reqs"]) >= 9 and f["startup"] and all(f["budgets"].values())
    assert f["gap_rows"]["Safety allocation"] and f["gap_rows"]["Budgets"]
    assert f["traced"] and f["tested"]


def _budget(f, kind):
    return next(s for s, r in f["reqs"].items() if f"bytes of {kind}" in r["statement"])


def test_refutations_confirmations_and_judgements(frozen):
    f = RS.baseline_facts(frozen)
    swr = sorted(f["reqs"])[0]
    cases = [
        (_c("requirement_not_verifiable", swr), "REFUTED"),          # it states 'passes when ...'
        (_c("requirement_not_atomic", swr), "REFUTED"),              # exactly one 'shall'
        (_c("reset_startup_missing", "document"), "REFUTED"),        # the startup requirement exists
        (_c("safety_allocation_missing", "Safety allocation"), "REFUTED"),  # the owner's recorded gap
        (_c("budget_missing", "document"), "REFUTED"),
        (_c("requirement_untraceable", swr), "REFUTED"),
        (_c("requirement_not_verifiable", "SWR-999"), "REFUTED"),    # not a requirement of the baseline
        (_c("requirement_not_verifiable", "Safety allocation"), "REFUTED"),  # aimed at an input, not a requirement
        (_c("budget_not_measurable", _budget(f, "flash")), "REFUTED"),  # '4096 bytes' is a bound with a unit
        (_c("requirement_infeasible", _budget(f, "flash")), "REFUTED"),  # meeting a budget is measured later
        (_c("safe_state_missing", "document"), "REFUTED"),           # AT-020: the recorded PENDING allocation
        (_c("failure_handling_missing", "document"), "REFUTED"),     # ADR-0009: LL is register access, no waiting
        (_c("failure_handling_missing", "Safety allocation"), "REFUTED"),  # the owner's recorded gap
        (_c("safe_state_missing", swr), "STANDS"),                   # a claim about one requirement: a judgement
        (_c("failure_handling_missing", swr), "STANDS"),
        (_c("other", swr), "STANDS"),
    ]
    got = RS.adjudicate(frozen, "SWE1-02", [c for c, _ in cases], f)
    assert [g["decision"] for g in got] == [d for _, d in cases], [(g["assertion"], g["evidence"]) for g in got]


def test_a_requirement_without_pass_criterion_is_confirmed(frozen):
    md = frozen / "workproducts/SWE.1/software_requirements.md"
    swr = sorted(RS.baseline_facts(frozen)["reqs"])[0]
    text = md.read_text()
    first = text.index(f"**{swr}**")
    v = text.index("Verification:", first)
    end = text.index("\n", v)
    md.write_text(text[:v] + "Verification: inspected by review." + text[end:])
    got = RS.adjudicate(frozen, "SWE1-06", [_c("requirement_not_verifiable", swr)])
    assert got[0]["decision"] == "CONFIRMED"


def test_claim_identity_ignores_wording(frozen):
    a = _c("requirement_not_verifiable", "SWR-001", "the requirement has no measurable criterion at all")
    b = _c("requirement_not_verifiable", "SWR-001", "verification of SWR-001 is vague and cannot be checked")
    assert RS.identity("SWE1-06", a) == RS.identity("SWE1-06", b)
    assert RS.identity("SWE1-06", a) != RS.identity("SWE1-02", a)


def test_a_missing_mandatory_safety_input_is_never_refuted(frozen):
    """F011-AT-023: an ASIL target with owner safety document issues keeps a missing-allocation claim."""
    man = json.loads((frozen / ".forge-run/manifest.json").read_text())
    man["safety_target"] = "B"
    man["owner_safety_document_issues"] = ["software safety analysis: NOT_PROVIDED"]
    (frozen / ".forge-run/manifest.json").write_text(json.dumps(man))
    got = RS.adjudicate(frozen, "SWE1-01", [_c("safety_allocation_missing", "Safety allocation")])
    assert got[0]["decision"] == "STANDS"


def test_swe1_03_rules_keep_hal_failure_handling_and_missing_safety_inputs(frozen):
    """F011-T029 diagnostic (SWE1-03 false rejections of the owner-ruled clean LL baselines): the layer allocation
    refutes only an LL document-level claim, the recorded allocation only a safe-state claim; a HAL work order's
    failure handling, an unrecorded allocation and a missing mandatory ASIL input still stand."""
    path = frozen / ".forge-run/manifest.json"
    man = json.loads(path.read_text())
    assert man["layer"] == "LL"
    path.write_text(json.dumps({**man, "layer": "HAL"}))
    got = RS.adjudicate(frozen, "SWE1-03", [_c("failure_handling_missing", "document"),
                                            _c("safe_state_missing", "document")])
    assert [g["decision"] for g in got] == ["STANDS", "REFUTED"]
    gaps = frozen / "traceability/upstream_gaps.md"
    text = gaps.read_text()
    gaps.write_text("\n".join(x for x in text.splitlines() if not x.startswith("| Safety allocation |")))
    got = RS.adjudicate(frozen, "SWE1-03", [_c("safe_state_missing", "document")])
    assert got[0]["decision"] == "CONFIRMED"
    gaps.write_text(text)
    path.write_text(json.dumps({**man, "safety_target": "B",
                                "owner_safety_document_issues": ["software safety analysis: NOT_PROVIDED"]}))
    got = RS.adjudicate(frozen, "SWE1-03", [_c("safe_state_missing", "document"),
                                            _c("failure_handling_missing", "document")])
    assert [g["decision"] for g in got] == ["STANDS", "STANDS"]


def test_a_budget_is_recognised_in_any_phrasing_with_a_byte_bound(frozen):
    """F011-T029 run 5 (WO-0008C false rejection on SWE1-04): the static RAM budget written as '0 bytes of persistent
    static RAM ... within the 64-byte static RAM budget' is a budget; a statement without a byte bound is not."""
    md = frozen / "workproducts/SWE.1/software_requirements.md"
    text = md.read_text()
    f = RS.baseline_facts(frozen)
    ram = _budget(f, "static RAM")
    line = next(x for x in text.splitlines() if x.startswith(f"- **{ram}**"))
    md.write_text(text.replace(line, f"- **{ram}** The IWDG LL driver shall use 0 bytes of persistent static RAM for "
                                     "driver state, within the 64-byte static RAM budget."))
    assert RS.baseline_facts(frozen)["budgets"]["static RAM"]
    assert RS.adjudicate(frozen, "SWE1-04", [_c("budget_missing", "document")])[0]["decision"] == "REFUTED"
    md.write_text(text.replace(line, f"- **{ram}** The IWDG LL driver shall keep its static RAM use small."))
    assert not RS.baseline_facts(frozen)["budgets"]["static RAM"]
    assert RS.adjudicate(frozen, "SWE1-04", [_c("budget_missing", "document")])[0]["decision"] == "STANDS"


def _inspector(verdicts):
    """A scripted inspector: verdicts[item] is a list of answers, one per call of that item."""
    seen: dict[str, int] = {}

    def call(p, **_k):
        item = p["task"].split(":")[-1]
        n = seen.get(item, 0)
        seen[item] = n + 1
        default = [{"behaviours": []}] if item in ("coverage", "behaviours") else [{"verdict": "PASS", "claims": [], "evidence_checked": [
            "workproducts/SWE.1/software_requirements.md"]}]  # F011-T049: coverage questions get an empty answer
        if item in ("effects", "budgets"):  # F011-T054: every entry agrees / is covered
            row = p["output_schema"]["properties"]["entries"]["items"]["properties"]
            default = [{"entries": [{"entry": i, "reason": "stated by the requirement",
                                     **({"agrees": True} if item == "effects" else
                                        {"covered_by": row["covered_by"]["items"]["enum"][:1]})}
                                    for i in row["entry"]["enum"]]}]
        answers = verdicts.get(item, default)
        doc = answers[min(n, len(answers) - 1)]
        return {"doc": json.loads(json.dumps(doc)), "errors": S.validate(doc, p["output_schema"]),
                "usage": {"prompt_tokens": 1000, "completion_tokens": 100}, "wall_ms": 1.0, "finish_reason": "stop"}
    return call, seen


def test_a_clean_baseline_with_a_refuted_fail_is_adjudicated_pass_and_recorded(frozen, monkeypatch):
    """F011-AT-020: the clean baseline's PENDING/NOT_PROVIDED gap judged as a failure is refuted, not a rejection."""
    fail = {"verdict": "FAIL", "claims": [_c("safety_allocation_missing", "Safety allocation",
                                            "no software safety requirements are allocated")],
            "evidence_checked": ["traceability/upstream_gaps.md"]}
    call, seen = _inspector({"SWE1-01": [fail, fail]})
    monkeypatch.setattr(S, "call", call)
    rep = RS.visit(frozen, "SWE.1", "qwen3-coder:30b")
    assert rep["status"] == "PASS", rep
    assert seen["SWE1-01"] == 2  # one selective reinspection with the refutation
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert rec["items"]["SWE1-01"]["outcome"] == "ADJUDICATED_PASS"
    assert rec["items"]["SWE1-01"]["rounds"][0]["claims"][0]["decision"] == "REFUTED"
    assert any(i.startswith("LRTX_ADJUDICATED_PASS:SWE1-01") for i in rep["issues"])


def test_a_real_defect_claim_stands_and_the_item_fails(frozen, monkeypatch):
    swr = sorted(RS.baseline_facts(frozen)["reqs"])[0]  # a claim about one requirement (document level: AT-020)
    claim = _c("safe_state_missing", swr, "the requirement states no safe state after a failed register write")
    fail = {"verdict": "FAIL", "claims": [claim], "evidence_checked": ["workproducts/SWE.1/software_requirements.md"]}
    call, seen = _inspector({"SWE1-03": [fail]})
    monkeypatch.setattr(S, "call", call)
    rep = RS.visit(frozen, "SWE.1", "qwen3-coder:30b")
    assert rep["status"] == "REWORK" and seen["SWE1-03"] == 1  # standing claims: no reinspection, a real FAIL
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert rec["items"]["SWE1-03"]["outcome"] == "FAIL"


def test_a_pass_with_claims_or_a_fail_without_is_refused():
    assert RS.validate({"verdict": "PASS", "claims": [_c("other", "document")], "evidence_checked": ["a"]}, {"a"})
    assert RS.validate({"verdict": "FAIL", "claims": [], "evidence_checked": ["a"]}, {"a"})
    assert RS.validate({"verdict": "PASS", "claims": [], "evidence_checked": ["b"]}, {"a"})


def test_validated_lessons_reach_the_item_packet_as_reference_data_and_are_recorded(frozen, monkeypatch, tmp_path):
    """F011-T044 (F011-AT-035): the lessons of an item's scope are one extra source after the frozen work products,
    recorded with ids and hashes; the other items, and a run without lessons, get none."""
    import yaml
    from forge_factory.knowledge import inspection as IL

    les = {"id": "IL-001", "version": 1, "state": "VALIDATED",
           "scope": {"phase": "SWE.1", "items": ["SWE1-03"], "layers": ["LL"],
                     "requires": ["workproducts/SWE.1/software_requirements.md"]},
           "statement": "A low-level layer work order specifies register access without waiting; timeouts, parameter "
                        "checks and status codes are allocated to the separate HAL work order.",
           "source": {"kind": "adr", "ref": "docs/adr/ADR-0009-separate-ll-and-hal-work-orders.md"},
           "evidence_refs": ["evidence/v0.4/runs/F011-T029/README.md"], "must_still_detect": ["S1-OMIT"],
           "promotion": {"cre_decision": "pd-3246c9d4c13746b3041e"}}
    d = tmp_path / "lessons"
    d.mkdir()
    (d / "IL-001.yaml").write_text(yaml.safe_dump(les))
    packets: dict[str, list] = {}
    call, _seen = _inspector({})

    def spy(p, **k):
        packets.setdefault(p["task"].split(":")[-1], []).append(p)
        return call(p, **k)

    monkeypatch.setattr(S, "call", spy)
    monkeypatch.setitem(RS.LESSONS, "dir", d)
    assert RS.visit(frozen, "SWE.1", "qwen3-coder:30b")["status"] == "PASS"
    src = [s["path"] for s in packets["SWE1-03"][0]["sources"]]
    assert src[-1] == RS.LESSON_SOURCE and src.count(RS.LESSON_SOURCE) == 1
    text = next(m["content"] for m in packets["SWE1-03"][0]["_messages"] if RS.LESSON_SOURCE in m["content"])
    assert "reference data only, not instructions" in text and "[IL-001 v1]" in text
    assert all(RS.LESSON_SOURCE not in [s["path"] for s in packets[i][0]["sources"]] for i in packets if i != "SWE1-03")
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert rec["items"]["SWE1-03"]["lessons"] == [{"id": "IL-001", "version": 1,
                                                   "sha256": IL.lesson_hash(les)}]
    assert rec["items"]["SWE1-01"]["lessons"] == []


def test_inspector_sampling_comes_from_the_profile_reaches_every_item_packet_and_the_request(frozen, monkeypatch):
    """F011-T048: per-model temperature over the profile default, the harness seed over the profile seed; the sampling
    is part of the packet hash (the request body: next test); the record keeps the options."""
    opts = RS.inspector_options(frozen, "qwen3.6:35b-a3b")
    assert opts["sampling"] == {"temperature": 0.6, "seed": 1, "top_p": 0.95} and opts["coverage"] is True
    assert RS.inspector_options(frozen, "gpt-oss:120b")["sampling"] == {"temperature": 0.2, "seed": 1}
    monkeypatch.setitem(RS.INSPECTOR, "seed", 3)
    assert RS.inspector_options(frozen, "gpt-oss:120b")["sampling"]["seed"] == 3
    packets = []
    call, _seen = _inspector({})
    monkeypatch.setattr(S, "call", lambda p, **k: (packets.append(p), call(p, **k))[1])
    assert RS.visit(frozen, "SWE.1", "gpt-oss:120b")["status"] == "PASS"
    assert packets and all(p["sampling"] == {"temperature": 0.2, "seed": 3} for p in packets)
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert rec["options"]["sampling"] == {"temperature": 0.2, "seed": 3}
    q = S.packet(phase="SWE.1", task="t", role="swe1-inspector", instructions="x", sources=[], criteria=[],
                 output_schema={"type": "object"}, model="m")
    r = S.packet(phase="SWE.1", task="t", role="swe1-inspector", instructions="x", sources=[], criteria=[],
                 output_schema={"type": "object"}, model="m", sampling={"temperature": 0.2, "seed": 3})
    assert "sampling" not in q and q["input_hash"] != r["input_hash"]  # no sampling: the packet is as before


def test_the_request_body_carries_the_packet_sampling(monkeypatch):
    import io

    from forge_factory.lrtx import structured as SS

    sent = {}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=None):
        sent.update(json.loads(req.data))
        return Resp(b'data: {"choices":[{"delta":{"content":"{}"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n')

    monkeypatch.setattr(SS.urllib.request, "urlopen", urlopen)
    p = SS.packet(phase="SWE.1", task="t", role="swe1-inspector", instructions="x", sources=[], criteria=[],
                  output_schema={"type": "object"}, model="m", sampling={"temperature": 0.2, "top_p": None, "seed": 7})
    SS.call(p, url="http://127.0.0.1:9/v1")
    assert sent["temperature"] == 0.2 and sent["seed"] == 7 and "top_p" not in sent
    q = SS.packet(phase="SWE.1", task="t", role="swe1-inspector", instructions="x", sources=[], criteria=[],
                  output_schema={"type": "object"}, model="m")
    sent.clear()
    SS.call(q, url="http://127.0.0.1:9/v1")
    assert "temperature" not in sent and "seed" not in sent  # unchanged for every other caller


def test_coverage_answers_become_decided_swe1_05_claims(frozen, monkeypatch):
    """F011-T049: an uncovered scope behaviour on a field no requirement states stands (SWE1-05 FAIL naming the field);
    one a requirement states (with its value) is refuted; covered behaviours make no claim."""
    facts = RS.baseline_facts(frozen)
    swr, stmt = sorted(facts["reqs"].items())[0]
    import re as _re

    field = _re.search(r"\b[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*\b", stmt["statement"]).group(0)
    num = _re.search(r"\b0x[0-9A-Fa-f]+\b", stmt["statement"])
    doc = {"behaviours": [
        {"behaviour": "covered one", "register_field": field, "value": "", "covered_by": [swr]},
        {"behaviour": "stated elsewhere", "register_field": field, "value": num.group(0) if num else "",
         "covered_by": []},
        {"behaviour": "start the counter", "register_field": "XREG.NOFIELD", "value": "0x5", "covered_by": []}]}
    got = RS.coverage_claims("Start and refresh", doc, facts)
    assert [c["decision"] for c in got] == ["REFUTED", "STANDS"] and "XREG.NOFIELD" in RS.render_claim(got[1])
    assert RS.validate_coverage({"behaviours": [{"behaviour": "b", "register_field": "lower.case", "value": "",
                                                 "covered_by": ["SWR-999"]}]}, set(facts["reqs"])) == [
        "register_field 'lower.case' is not REGISTER.FIELD", "covered_by names SWR-999, not a requirement"]
    assert all(not x.lower().startswith("out of scope") for x in RS.scope_items(frozen))
    call, _seen = _inspector({"coverage": [{"behaviours": doc["behaviours"][2:]}]})
    monkeypatch.setattr(S, "call", call)
    rep = RS.visit(frozen, "SWE.1", "qwen3-coder:30b")
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert rep["status"] == "REWORK" and rec["items"]["SWE1-05"]["outcome"] == "FAIL"
    assert any("XREG.NOFIELD" in f for f in rec["result"].get("issues", []) + [json.dumps(rec["items"])])
    assert rec["coverage"] and rec["options"]["coverage"] is True


def test_entry_answers_become_decided_swe1_02_and_swe1_04_claims(frozen, monkeypatch):
    """F011-T054: an effects entry the inspector says contradicts its requirement stands on that requirement unless
    the requirement text states the entry's operation; an uncovered work-order budget stands unless a requirement
    states the resource with that bound. Agreeing and covered entries make no claim."""
    facts = RS.baseline_facts(frozen)
    eff = RS.effect_entries(frozen, facts)
    bud = RS.budget_entries(frozen)
    assert eff and [b["resource"] for b in bud] == ["flash", "static RAM", "stack"]
    assert RS.inspector_options(frozen, "qwen3.6:35b-a3b")["entries"] is True
    first = eff[0]
    assert RS._states_effect(first), first  # the clean baseline states its own effects
    flipped = dict(first, value=hex(int(first["value"], 16) ^ 1)) if first["op"] == "write" else \
        dict(first, op=RS.OPPOSITE[first["op"]])
    assert not RS._states_effect(flipped)
    doc = {"entries": [{"entry": e["entry"], "agrees": e is not first, "reason": "quoted words"} for e in eff]}
    assert [c["decision"] for c in RS.entry_claims("effects", doc, eff, facts)] == ["REFUTED"]
    got = RS.entry_claims("effects", doc, [flipped, *eff[1:]], facts)
    assert [(c["assertion"], c["target_id"], c["decision"]) for c in got] == [
        ("requirements_inconsistent", first["swr"], "STANDS")]
    bdoc = {"entries": [{"entry": b["entry"], "covered_by": [], "reason": "no requirement"} for b in bud]}
    assert {c["decision"] for c in RS.entry_claims("budgets", bdoc, bud, facts)} == {"REFUTED"}
    stack = next(s for s, r in facts["reqs"].items() if "stack" in r["statement"])
    less = {**facts, "reqs": {s: r for s, r in facts["reqs"].items() if s != stack}}
    got = RS.entry_claims("budgets", bdoc, bud, less)
    assert [c["decision"] for c in got] == ["REFUTED", "REFUTED", "STANDS"] and "budget_missing" in RS.render_claim(got[2])
    assert RS.validate_entries({"entries": doc["entries"][1:] + doc["entries"][1:2]}, [e["entry"] for e in eff])[:1] \
        == [f"entry {first['entry']} answered 0 times (answer each entry once)"]
    # through the visit: a contradiction the requirement text confirms fails SWE1-02, the record keeps the answers
    effp = frozen / "workproducts/SWE.1/register_effects.json"
    raw = json.loads(effp.read_text())
    call, _seen = _inspector({"effects": [doc]})
    monkeypatch.setattr(S, "call", call)
    assert RS.visit(frozen, "SWE.1", "qwen3-coder:30b")["status"] == "PASS"  # the claim is refuted by the text
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert [e["kind"] for e in rec["entries"]] == ["effects", "budgets"] and rec["options"]["entries"] is True
    site = next(e for e in raw["effects"] if e.get("op") in ("set", "clear", "write"))  # the entry E01 pairs
    site.update({"op": flipped["op"], **({"value": flipped["value"]} if flipped["op"] == "write" else {})})
    effp.write_text(json.dumps(raw))
    monkeypatch.setattr(S, "call", _inspector({"effects": [doc]})[0])
    rep = RS.visit(frozen, "SWE.1", "qwen3-coder:30b")
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert rep["status"] == "REWORK" and rec["items"]["SWE1-02"]["outcome"] == "FAIL"


def test_engine_output_reaches_the_inspector_by_hash_only(frozen):
    """F011-T036 (owner 2026-10-24, "Reference by hash"): the first semantic baseline inspected in a Fabro run
    (WO-0008A-STM32N6-RCC-LL-q36b) was refused with SOURCE_TOO_LARGE on the 54 kB register obligations. The SafeC
    engine files reach the inspector as path, sha256 and size; every other baseline file stays whole."""
    from forge_factory.common import sha256_bytes
    from forge_factory.lrtx import review as R

    bl, srcs = R.evidence(frozen, "SWE.1")
    by = {s["path"]: s for s in srcs}
    engine = [f for f in bl["files"] if f in R.ENGINE_FILES]
    assert engine, "the semantic SWE.1 baseline carries the engine output"
    for f in engine:
        assert f not in by and json.loads(by[f + "#sha256"]["text"])["sha256"] == sha256_bytes((frozen / f).read_bytes())
    req = "workproducts/SWE.1/software_requirements.md"
    assert by[req]["text"] == (frozen / req).read_text()
    assert RS.validate({"verdict": "PASS", "claims": [], "evidence_checked": [engine[0]]}, {s["path"] for s in srcs}) == []


def _step_answers(ws, facts, **override):
    """Correct answers to every F014 fact question of a clean baseline, keyed like the scripted inspector's items."""
    out = {}
    for q in RS.step_questions(ws, facts):
        if q["id"] == "startup":
            doc = {"quote": "after reset", "answer": facts["startup"][0]}
        elif q["id"].startswith("input-"):
            doc = {"quote": "| row |", "answer": q["input"]}
        elif q["id"].startswith("budget-"):
            hit = next(s for s, r in sorted(facts["reqs"].items()) if q["row"]["resource"] in r["statement"])
            doc = {"quote": "bound", "answer": hit}
        else:
            e = q["row"]
            doc = {"quote": "stated", "answer": e["op"], "value": str(e["value"]) if e["op"] == "write" else ""}
        out["step-" + q["id"]] = [override.get(q["id"], doc)]
    return out


def test_stepwise_fact_answers_become_decided_claims(frozen, monkeypatch):
    """F014 (owner 2026-10-26, "Stepwise inspector in 014"): one closed question per baseline fact. A found fact makes
    no claim; a NONE the baseline contradicts is refuted; a NONE the baseline proves (fact really absent) counts."""
    facts = RS.baseline_facts(frozen)
    qs = {q["id"]: q for q in RS.step_questions(frozen, facts)}
    assert {"startup", "input-hsi", "input-safety", "input-budgets", "budget-stack"} <= set(qs)
    assert all(q["answers"][-1] in ("NONE", "not_stated") for q in qs.values())
    assert "Safety allocation" in qs["input-safety"]["answers"]
    good = {k[5:]: v[0] for k, v in _step_answers(frozen, facts).items()}
    assert all(RS.step_claims(frozen, q, good[i], facts) == [] for i, q in qs.items())
    none = {"quote": "", "answer": "NONE"}
    assert [c["decision"] for c in RS.step_claims(frozen, qs["startup"], none, facts)] == ["REFUTED"]
    assert [c["decision"] for c in RS.step_claims(frozen, qs["startup"], none, {**facts, "startup": []})] == ["CONFIRMED"]
    gone = {**facts, "gap_rows": {**facts["gap_rows"], "Safety allocation": None}}
    assert [c["decision"] for c in RS.step_claims(frozen, qs["input-safety"], none, facts)] == ["REFUTED"]
    got = RS.step_claims(frozen, qs["input-safety"], none, gone)
    assert [c["decision"] for c in got] == ["CONFIRMED"] and "Safety allocation" in RS.render_claim(got[0])
    stack = next(s for s, r in facts["reqs"].items() if "stack" in r["statement"])
    less = {**facts, "reqs": {s: r for s, r in facts["reqs"].items() if s != stack}}
    got = RS.step_claims(frozen, qs["budget-stack"], none, less)
    assert [c["decision"] for c in got] == ["STANDS"] and "budget_missing" in RS.render_claim(got[0])
    effect = next(q for i, q in qs.items() if i.startswith("effect-"))
    wrong = {"quote": "x", "answer": RS.OPPOSITE.get(effect["row"]["op"], "not_stated"), "value": ""}
    # the requirement text states the entry's own operation: the model's misreading is refuted, never a rejection
    assert [c["decision"] for c in RS.step_claims(frozen, effect, wrong, facts)] == ["REFUTED"]
    # through the visit: temperature 0, entries replaced by fact questions, every answer recorded
    monkeypatch.setitem(RS.INSPECTOR, "stepwise", True)
    opts = RS.inspector_options(frozen, "qwen3.6:35b-a3b")
    assert opts["stepwise"] and opts["sampling"]["temperature"] == 0 and opts["coverage"] and not opts["entries"]
    call, seen = _inspector(_step_answers(frozen, facts))
    monkeypatch.setattr(S, "call", call)
    assert RS.visit(frozen, "SWE.1", "qwen3.6:35b-a3b")["status"] == "PASS"
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert {s["question"] for s in rec["steps"]} == set(qs) and all(not s["claims"] for s in rec["steps"])
    assert all(seen["step-" + i] == 1 for i in qs)
    # a contradicted effects entry (seeded S1-EFFECT shape): the model reads the requirement's own operation
    effp = frozen / "workproducts/SWE.1/register_effects.json"
    raw = json.loads(effp.read_text())
    site = next(x for x in raw["effects"] if x.get("op") in ("set", "clear", "write") and x.get("swr") == effect["row"]["swr"])
    if site["op"] == "write":
        site["value"] = hex(int(str(site["value"]), 16) ^ 1) if str(site["value"]).startswith("0x") else site["value"] ^ 1
    else:
        site["op"] = RS.OPPOSITE[site["op"]]
    effp.write_text(json.dumps(raw))
    original = {"quote": "stated", "answer": effect["row"]["op"],
                "value": str(effect["row"]["value"]) if effect["row"]["op"] == "write" else ""}
    monkeypatch.setattr(S, "call", _inspector(_step_answers(frozen, RS.baseline_facts(frozen),
                                                            **{effect["id"]: original}))[0])
    rep = RS.visit(frozen, "SWE.1", "qwen3.6:35b-a3b")
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert rep["status"] == "REWORK" and rec["items"]["SWE1-02"]["outcome"] == "FAIL"
    assert effect["row"]["swr"] in json.dumps(rec["items"]["SWE1-02"])


def test_adjudicated_pass_note_counts_the_verdict_round_when_fact_answers_follow(frozen, monkeypatch):
    """Omniverse2 smoke 2026-10-26: a refuted SWE1-03 FAIL followed by a refuted fact answer appended a round without
    claims, and the ADJUDICATED_PASS note raised KeyError instead of recording the inspection."""
    facts = RS.baseline_facts(frozen)
    fail = {"verdict": "FAIL", "claims": [_c("reset_startup_missing", "document")],
            "evidence_checked": ["workproducts/SWE.1/software_requirements.md"]}
    monkeypatch.setitem(RS.INSPECTOR, "stepwise", True)
    call, _seen = _inspector({"SWE1-03": [fail, fail],
                              **_step_answers(frozen, facts, startup={"quote": "", "answer": "NONE"})})
    monkeypatch.setattr(S, "call", call)
    rep = RS.visit(frozen, "SWE.1", "qwen3.6:35b-a3b")
    assert rep["status"] == "PASS" and any(i.startswith("LRTX_ADJUDICATED_PASS:SWE1-03: 1 claim") for i in rep["issues"])


def test_an_ambiguity_quoted_from_the_open_points_is_documented(frozen):
    """Omniverse2 stepwise smoke 2026-10-26: the clean IWDG baseline was rejected for an 'undocumented' ambiguity that
    the claim itself quoted from the document's Open points list."""
    facts = RS.baseline_facts(frozen)
    assert facts["open_points"], "the frozen fixture records open points"
    point = facts["open_points"].split(" - ")[0].lstrip("- ").rstrip(".")[:60]
    quoted = _c("ambiguity_not_documented", "document", f"The document lists '{point}' as an open point; unresolved.")
    other = _c("ambiguity_not_documented", "document", "The term 'nominal refresh window' is never defined anywhere.")
    got = RS.adjudicate(frozen, "SWE1-06", [quoted, other], facts)
    assert [c["decision"] for c in got] == ["REFUTED", "STANDS"]


def test_stepwise_coverage_offers_only_source_fields_and_register_wildcards(frozen):
    """Omniverse2 2026-10-26: a generic RCC scope item drew placeholder fields ('RCC_AHB2ENR.<field>') three times and
    the inspection recorded nothing. Stepwise coverage answers from the fields the frozen sources name, or REG.*."""
    from forge_factory.lrtx import review as R

    facts = RS.baseline_facts(frozen)
    _bl, srcs = R.evidence(frozen, "SWE.1")
    fields = RS.source_fields(srcs)
    assert fields and all(RS.FIELD.match(f) or RS.WILDCARD.match(f) for f in fields)
    wide = next(f for f in fields if f.endswith(".*"))
    schema = RS.coverage_schema(sorted(facts["reqs"]), fields)
    assert schema["properties"]["behaviours"]["items"]["properties"]["register_field"]["enum"] == fields
    assert RS.validate_coverage({"behaviours": [{"behaviour": "any clock", "register_field": wide, "value": "",
                                                 "covered_by": []}]}, set(facts["reqs"])) == []
    named = [s for s, r in facts["reqs"].items() if wide[:-2] in r["statement"]]
    got = RS.coverage_claims("enable a clock", {"behaviours": [{"behaviour": "any clock", "register_field": wide,
                                                                "value": "", "covered_by": []}]}, facts)
    assert [c["decision"] for c in got] == (["REFUTED"] if named else ["STANDS"])
    assert RS.coverage_schema(["SWR-001"])["properties"]["behaviours"]["items"]["properties"]["register_field"] == {
        "type": "string", "minLength": 3, "maxLength": 60}  # the F011 (non-stepwise) question is unchanged


def test_learning_run_patterns_are_decided_and_answers_are_closed(frozen):
    """Omniverse2 learning run 1 (2026-10-26): claims the baseline contradicts at input/document level are refuted,
    a reset pulse agrees with both entries it names, and stepwise evidence_checked is a closed list."""
    facts = RS.baseline_facts(frozen)
    got = RS.adjudicate(frozen, "SWE1-04", [_c("budget_not_measurable", "Budgets", "development targets only")], facts)
    assert [c["decision"] for c in got] == ["REFUTED"]
    no_stack = {**facts, "budgets": {**facts["budgets"], "stack": False}}
    got = RS.adjudicate(frozen, "SWE1-04", [_c("budget_not_measurable", "Budgets", "development targets only")], no_stack)
    assert [c["decision"] for c in got] == ["STANDS"]
    gap = _c("upstream_gap_not_recorded", "document", "upstream status NOT_PROVIDED is not recorded")
    assert [c["decision"] for c in RS.adjudicate(frozen, "SWE1-05", [gap], facts)] == ["REFUTED"]
    unrecorded = {**facts, "gap_rows": {**facts["gap_rows"], "Safety allocation": None}}
    assert [c["decision"] for c in RS.adjudicate(frozen, "SWE1-05", [gap], unrecorded)] == ["STANDS"]
    effect = next(q for q in RS.step_questions(frozen, facts) if q["id"].startswith("effect-"))
    assert "set_then_clear" in effect["answers"]
    pulse = {"quote": "assert and then release", "answer": "set_then_clear", "value": ""}
    expected = [] if effect["row"]["op"] in RS.OPPOSITE else ["REFUTED"]
    assert [c["decision"] for c in RS.step_claims(frozen, effect, pulse, facts)] == expected
    schema = RS.claim_schema("SWE1-01", ["document"], ["workproducts/SWE.1/software_requirements.md"])
    assert schema["properties"]["evidence_checked"]["items"]["enum"] == ["workproducts/SWE.1/software_requirements.md"]
    assert "enum" not in RS.claim_schema("SWE1-01", ["document"])["properties"]["evidence_checked"]["items"]


def test_an_input_row_label_may_carry_an_explanation(frozen):
    """Preflight 2026-10-26 (WO-0008C): the gaps-table row 'HSI contract (hardware/software interface)' records the HSI
    contract; the exact-label rule rejected the clean baseline even with truthful answers."""
    gaps = frozen / "traceability/upstream_gaps.md"
    text = gaps.read_text()
    assert "| HSI contract |" in text
    gaps.write_text(text.replace("| HSI contract |", "| HSI contract (hardware/software interface) |"))
    facts = RS.baseline_facts(frozen)
    assert facts["gap_rows"]["HSI contract"]
    q = next(x for x in RS.step_questions(frozen, facts) if x["id"] == "input-hsi")
    label = RS.input_label(q["answers"], "HSI contract")
    assert label == "HSI contract (hardware/software interface)"
    assert RS.step_claims(frozen, q, {"quote": "", "answer": label}, facts) == []
    got = RS.step_claims(frozen, q, {"quote": "", "answer": "NONE"}, facts)
    assert [c["decision"] for c in got] == ["REFUTED"]


def test_an_ambiguity_claim_on_a_recorded_upstream_input_is_refuted(frozen):
    """Run 2 (2026-10-26): the clean IWDG-LL baseline was rejected because its PENDING safety allocation was called an
    undocumented ambiguity; the input's recorded row is that documentation. Unrecorded, the claim stands."""
    facts = RS.baseline_facts(frozen)
    claim = _c("ambiguity_not_documented", "Safety allocation", "The safety allocation is PENDING; not resolved.")
    assert [c["decision"] for c in RS.adjudicate(frozen, "SWE1-06", [claim], facts)] == ["REFUTED"]
    gone = {**facts, "gap_rows": {**facts["gap_rows"], "Safety allocation": None}}
    assert [c["decision"] for c in RS.adjudicate(frozen, "SWE1-06", [claim], gone)] == ["STANDS"]


def test_a_count_bound_is_measurable(frozen):
    """Run 2 (2026-10-26): SWR-009 'at most HAL_RCC_TIMEOUT_VALUE = 1000 polling iterations' was confirmed unmeasurable
    because the unit list had only sizes, times and frequencies."""
    facts = RS.baseline_facts(frozen)
    swr = sorted(facts["reqs"])[0]
    timed = {**facts, "reqs": {**facts["reqs"], swr: {**facts["reqs"][swr], "statement":
             "The HAL RCC driver shall poll the ready flag at most HAL_RCC_TIMEOUT_VALUE = 1000 polling iterations."}}}
    got = RS.adjudicate(frozen, "SWE1-04", [_c("budget_not_measurable", swr, "iterations are not a unit")], timed)
    assert [c["decision"] for c in got] == ["REFUTED"]
    vague = {**facts, "reqs": {**facts["reqs"], swr: {**facts["reqs"][swr], "statement": "The driver shall be fast."}}}
    assert [c["decision"] for c in RS.adjudicate(frozen, "SWE1-04", [_c("budget_not_measurable", swr)], vague)] == [
        "CONFIRMED"]


def test_scope_behaviours_are_asked_one_by_one_and_an_uncovered_one_names_its_field(frozen):
    """Run 2 (2026-10-26): Qwen listed coverage behaviours by walking the requirements, so the omitted requirement never
    appeared. Stepwise lists behaviours from the scope sentence alone (requirements hidden), then asks each."""
    from forge_factory.lrtx import review as R

    facts = RS.baseline_facts(frozen)
    _bl, srcs = R.evidence(frozen, "SWE.1")
    pkt = RS.behaviour_packet(frozen, {"baseline_id": "BL"}, srcs, "Start the watchdog", RS.source_fields(srcs),
                              "qwen3.6:35b-a3b", {"temperature": 0})
    assert all(x["path"] != "workproducts/SWE.1/software_requirements.md" for x in pkt["sources"])
    e = RS.effect_entries(frozen, facts)[0]
    b = {"phrase": f"{e['op']} {e['field']}", "action": e["op"], "register_field": e["field"]}
    q = RS.behaviour_question("behaviour-0-0", b, sorted(facts["reqs"]))
    assert q["answers"][-1] == "NONE" and RS.BEHAVIOURS["behaviour-0-0"] == b
    assert RS.behaviour_claims(b, {"quote": "x", "answer": e["swr"]}, facts) == []
    # NONE while the requirement still states it: refuted; with that requirement removed: stands, naming the field
    got = RS.behaviour_claims(b, {"quote": "", "answer": "NONE"}, facts)
    assert [c["decision"] for c in got] == ["REFUTED"]
    less = {**facts, "reqs": {k: v for k, v in facts["reqs"].items() if e["field"] not in v["statement"]}}
    got = RS.behaviour_claims(b, {"quote": "", "answer": "NONE"}, less)
    assert [c["decision"] for c in got] == ["STANDS"] and e["field"] in RS.render_claim(got[0])


def test_behaviours_on_one_field_are_told_apart_by_their_purpose_words(frozen):
    """Run 3 (2026-10-26): every IWDG key write is 'write IWDG_KR.KEY'; the removed start-key requirement must not be
    covered by the refresh-key requirement."""
    facts = RS.baseline_facts(frozen)
    reqs = {"SWR-001": {"statement": "When the start function is called, the IWDG LL driver shall write 0x0000CCCC to "
                                     "IWDG_KR.KEY.", "verification": ""},
            "SWR-002": {"statement": "When the refresh function is called, the IWDG LL driver shall write 0x0000AAAA to "
                                     "IWDG_KR.KEY.", "verification": ""}}
    start = {"phrase": "start the watchdog by writing documented keys to IWDG_KR", "action": "write",
             "register_field": "IWDG_KR.KEY"}
    assert "start" in RS.purpose_words(start) and "iwdg_kr" not in RS.purpose_words(start)
    assert RS.behaviour_hit({**facts, "reqs": reqs}, start) == "SWR-001"
    # after the S1-OMIT seed the IWDG baseline still has several key writes (refresh and the access keys)
    access = {"statement": "When the write-access enable function is called, the IWDG LL driver shall write 0x00005555 "
                           "to IWDG_KR.KEY.", "verification": ""}
    only_refresh = {**facts, "reqs": {"SWR-002": reqs["SWR-002"], "SWR-003": access}}
    got = RS.behaviour_claims(start, {"quote": "", "answer": "NONE"}, only_refresh)
    assert [c["decision"] for c in got] == ["STANDS"] and "IWDG_KR.KEY" in RS.render_claim(got[0])


def test_a_cited_requirement_must_state_the_behaviour_itself(frozen):
    """Run 3 (2026-10-26): 'enable HSI oscillator' (set RCC_CR.HSION) was answered with the requirement that clears
    HSION; the citation is checked, so the omitted enable requirement stands while a clean baseline is refuted."""
    facts = RS.baseline_facts(frozen)
    reqs = {"SWR-001": {"statement": "When the HSI enable function is called, the RCC LL driver shall set RCC_CR.HSION.",
                        "verification": ""},
            "SWR-002": {"statement": "When the HSI disable function is called, the RCC LL driver shall clear RCC_CR.HSION.",
                        "verification": ""}}
    enable = {"phrase": "enable HSI oscillator (HSION)", "action": "set", "register_field": "RCC_CR.HSION"}
    wrong = {"quote": "shall clear RCC_CR.HSION", "answer": "SWR-002"}
    assert RS.behaviour_claims(enable, {"quote": "shall set RCC_CR.HSION", "answer": "SWR-001"},
                               {**facts, "reqs": reqs}) == []
    got = RS.behaviour_claims(enable, wrong, {**facts, "reqs": reqs})
    assert [c["decision"] for c in got] == ["REFUTED"]  # clean: SWR-001 states it
    got = RS.behaviour_claims(enable, wrong, {**facts, "reqs": {"SWR-002": reqs["SWR-002"]}})
    assert [c["decision"] for c in got] == ["STANDS"] and "RCC_CR.HSION" in RS.render_claim(got[0])


def test_purpose_words_decide_only_between_several_candidates(frozen):
    """Run 4 (2026-10-26): 'set the reload value in IWDG_RLR.RL' was rejected because SWR-006 ('write the requested
    value to IWDG_RLR.RL'), the one requirement on that field, never says 'reload'."""
    facts = RS.baseline_facts(frozen)
    reqs = {"SWR-006": {"statement": "When the reload set function is called, the IWDG LL driver shall write the "
                                     "requested value to IWDG_RLR.RL.".replace("reload set", "set"), "verification": ""}}
    reload = {"phrase": "set the reload value in IWDG_RLR.RL", "action": "write", "register_field": "IWDG_RLR.RL"}
    assert RS.behaviour_claims(reload, {"quote": "", "answer": "SWR-006"}, {**facts, "reqs": reqs}) == []
    assert RS.behaviour_hit({**facts, "reqs": reqs}, reload) == "SWR-006"


def test_a_flag_read_split_by_value_is_one_behaviour(frozen):
    """Run 5 (2026-10-26): 'query the PVU update flag in IWDG_SR' was rejected: SWR-007/SWR-008 return 1U/0U for
    IWDG_SR.PVU and neither says 'update'."""
    facts = RS.baseline_facts(frozen)
    reqs = {"SWR-007": {"statement": "When the PVU query function is called and IWDG_SR.PVU is 1, the IWDG LL driver "
                                     "shall return 1U.", "verification": ""},
            "SWR-008": {"statement": "When the PVU query function is called and IWDG_SR.PVU is 0, the IWDG LL driver "
                                     "shall return 0U.", "verification": ""}}
    pvu = {"phrase": "query the PVU update flag in IWDG_SR", "action": "read", "register_field": "IWDG_SR.PVU"}
    assert RS.behaviour_claims(pvu, {"quote": "", "answer": "SWR-007"}, {**facts, "reqs": reqs}) == []


def test_an_action_noun_is_not_the_action(frozen):
    """Run 6 (2026-10-26): 'HSI oscillator enable' was answered with SWR-003, which clears 'the selected oscillator
    enable bit, respectively RCC_CR.HSION'; the citation passed on the noun 'enable bit'."""
    facts = RS.baseline_facts(frozen)
    disable = {"statement": "When a valid HSI or HSE disable request is received, the RCC driver shall clear the selected "
                            "oscillator enable bit, respectively RCC_CR.HSION or RCC_CR.HSEON.", "verification": ""}
    enable = {"phrase": "HSI oscillator enable", "action": "set", "register_field": "RCC_CR.HSION"}
    got = RS.behaviour_claims(enable, {"quote": "", "answer": "SWR-003"}, {**facts, "reqs": {"SWR-003": disable}})
    assert [c["decision"] for c in got] == ["STANDS"]
    off = {"phrase": "HSI oscillator disable", "action": "clear", "register_field": "RCC_CR.HSION"}
    assert RS.behaviour_claims(off, {"quote": "", "answer": "SWR-003"}, {**facts, "reqs": {"SWR-003": disable}}) == []


def test_the_imposed_verb_decides_not_any_action_word(frozen):
    """Run 7 (2026-10-26): with the HSI enable requirement removed, SWR-007 ('for an HSI enable request ... shall clear
    the enable bit it set, respectively RCC_CR.HSION') and SWR-010 ('While no oscillator enable ... shall leave
    RCC_CR.HSION') still counted as stating the enable."""
    facts = RS.baseline_facts(frozen)
    reqs = {"SWR-007": {"statement": "If RCC_SR.HSIRDY for an HSI enable request remains 0 throughout the timeout, then "
                                     "the RCC driver shall clear the enable bit it set, respectively RCC_CR.HSION.",
                        "verification": ""},
            "SWR-010": {"statement": "While no oscillator enable or disable has been requested after reset, the RCC driver "
                                     "shall leave RCC_CR.HSION at its reset value 1.", "verification": ""}}
    enable = {"phrase": "HSI oscillator enable", "action": "set", "register_field": "RCC_CR.HSION"}
    got = RS.behaviour_claims(enable, {"quote": "", "answer": "SWR-007"}, {**facts, "reqs": reqs})
    assert [c["decision"] for c in got] == ["STANDS"]
    with_enable = {**reqs, "SWR-001": {"statement": "When a valid HSI enable request is received, the RCC driver shall "
                                                    "set RCC_CR.HSION and return HAL_OK.", "verification": ""}}
    assert RS.behaviour_claims(enable, {"quote": "", "answer": "SWR-001"}, {**facts, "reqs": with_enable}) == []
    pulse = {"statement": "When a reset request is received, the driver shall assert and then release "
                          "RCC_AHB1RSTR.ADC12RST.", "verification": ""}
    release = {"phrase": "ADC12 reset release", "action": "clear", "register_field": "RCC_AHB1RSTR.ADC12RST"}
    assert RS.behaviour_claims(release, {"quote": "", "answer": "SWR-006"}, {**facts, "reqs": {"SWR-006": pulse}}) == []


def test_a_register_write_states_a_set_or_clear_behaviour(frozen):
    """Run 8 (2026-10-26): 'Enable write access to IWDG_PR with the documented key' (set IWDG_PR.*) was rejected
    although SWR-003 imposes 'write 0x00005555 to IWDG_KR.KEY' to enable write access to IWDG_PR."""
    facts = RS.baseline_facts(frozen)
    swr = {"statement": "When the write-access enable function is called, the IWDG LL driver shall write 0x00005555 to "
                        "IWDG_KR.KEY to enable write access to IWDG_PR and IWDG_RLR.", "verification": ""}
    access = {"phrase": "Enable write access to IWDG_PR with the documented key", "action": "set",
              "register_field": "IWDG_PR.*"}
    assert RS.behaviour_claims(access, {"quote": "", "answer": "SWR-003"}, {**facts, "reqs": {"SWR-003": swr}}) == []


def test_a_read_named_anywhere_in_the_requirement_covers_a_flag_wait(frozen):
    """Run 9 (2026-10-26): 'HSI ready flag wait' was rejected against SWR-001 'shall set RCC_CR.HSION and return HAL_OK
    upon observing RCC_SR.HSIRDY equal to 1'."""
    facts = RS.baseline_facts(frozen)
    swr = {"statement": "When a valid HSI enable request is received, the RCC driver shall set RCC_CR.HSION and return "
                        "HAL_OK upon observing RCC_SR.HSIRDY equal to 1 within the caller-supplied timeout.",
           "verification": ""}
    wait = {"phrase": "HSI ready flag wait", "action": "read", "register_field": "RCC_SR.HSIRDY"}
    assert RS.behaviour_claims(wait, {"quote": "", "answer": "SWR-001"}, {**facts, "reqs": {"SWR-001": swr}}) == []
    assert "return" in RS.imposed_verbs(swr["statement"])


def test_an_objection_to_the_recorded_upstream_status_is_refuted(frozen):
    """Run 10 (2026-10-26): the clean 0008B baseline was rejected by an SWE1-04 'other' claim that conceded the budgets
    are explicit and measurable but objected that the upstream status is NOT_PROVIDED with DRAFT_TEMPLATE issues."""
    facts = RS.baseline_facts(frozen)
    claim = _c("other", "document", "These are explicit and measurable. However, the upstream status is NOT_PROVIDED "
                                    "with DRAFT_TEMPLATE issues, so the budgets are not approved.")
    assert [c["decision"] for c in RS.adjudicate(frozen, "SWE1-04", [claim], facts)] == ["REFUTED"]
    unrecorded = {**facts, "gap_rows": {**facts["gap_rows"], "Budgets": None}}
    assert [c["decision"] for c in RS.adjudicate(frozen, "SWE1-04", [claim], unrecorded)] == ["STANDS"]
    other = _c("other", "document", "SWR-004 and SWR-005 contradict each other on the enable order.")
    assert [c["decision"] for c in RS.adjudicate(frozen, "SWE1-02", [other], facts)] == ["STANDS"]
