"""T028: the conductor with a fake harness (no model)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SKILLS
from hi_helpers import SWR_ITEMS, SYS_ITEMS, make_project, req, write

CONDUCT = SKILLS / "hi-conductor" / "scripts" / "conduct.py"
FAKE = Path(__file__).resolve().parent / "fake_harness.py"


def F(item, sev="major", desc="The trigger condition is not stated."):
    return {"checklist_item": item, "severity": sev, "description": desc, "requested_change": "State it."}


def setup(root, scenario, *, level="HI-2", stages=("sys-req",), inspector_family="fake-b", raw=False, read_only=True):
    make_project(root, level=level, stages=stages)
    proj = json.loads((root / ".hi/project.json").read_text())
    proj["roles"] = {
        "author": {"harness": "custom", "command": [sys.executable, str(FAKE), "author"], "model_family": "fake-a"},
        "inspector": {"harness": "custom", "command": [sys.executable, str(FAKE), "inspector"],
                      "model_family": inspector_family, "read_only": read_only},
    }
    if raw:
        proj["trace_capture"] = {"raw_prompts": True}
    write(root / ".hi/project.json", proj)
    sc = root.parent / f"{root.name}-scenario.json"
    sc.write_text(json.dumps(scenario))
    return sc


GOV_PHASES = ("governance", "fix-governance")


def conduct(root, sc, *args, gov=False):
    """Run the conductor. The governance step (entry stage, before the author writes) is left out of the returned
    calls unless `gov` is true: most tests are about the item and set loop."""
    log = root.parent / f"{root.name}-calls.jsonl"
    env = {"FAKE_SCENARIO": str(sc), "FAKE_LOG": str(log), "PATH": "/usr/bin:/bin"}
    r = subprocess.run([sys.executable, str(CONDUCT), *args], cwd=root, capture_output=True, text=True, timeout=120,
                       env=env)
    calls = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
    if not gov:
        calls = [c for c in calls if c["phase"] not in GOV_PHASES]
    out = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"stderr": r.stderr}
    return r.returncode, out, calls


def events(root, out):
    return [json.loads(l) for l in (root / out["events"]).read_text().splitlines()]


def seq(calls):
    return [(c["role"], c["phase"], c["round"], tuple(c["items"])) for c in calls]


def test_happy_path_sequence(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {
        "author": {"items": SYS_ITEMS, "rework": {"SYS-SUP-001": {"text": SYS_ITEMS[0]["text"] + " "}}},
        "inspector": {"item_rounds": [{"SYS-SUP-001": [F("IQ-04")], "SYS-SUP-002": [F("IQ-11", "minor")]}, {}],
                      "set_rounds": [[]]},
    })
    code, out, calls = conduct(root, sc, "--stage", "sys-req", gov=True)
    assert code == 0, out
    assert out["status"] == "DONE" and out["stages"][0]["outcome"] == "ACCEPTED"
    first = calls.pop(0)  # the governance package comes before any requirement
    assert (first["role"], first["phase"]) == ("author", "governance")
    assert first["active_role"]["write_scope"] == ["hi/sys-req/**"]
    assert seq(calls) == [
        ("author", "create", 0, ()),
        ("inspector", "item", 1, ("SYS-SUP-001", "SYS-SUP-002")),
        ("author", "rework", 1, ("SYS-SUP-001",)),          # only the major one, alone
        ("inspector", "item", 2, ("SYS-SUP-001",)),         # re-judge only the reworked item
        ("inspector", "set", 1, ()),
    ]
    assert calls[4]["findings"] == 1                        # the minor finding is carried into the set phase
    fs = json.loads((root / "hi/sys-req/inspection/findings.json").read_text())["findings"]
    assert {f["status"] for f in fs} == {"resolved"}
    state = json.loads((root / ".hi/state.json").read_text())["stages"]["sys-req"]
    assert state["state"] == "accepted"
    assert (root / ".hi/trace-baseline.json").is_file()
    gates = json.loads((root / "hi/sys-req/gates/scope.json").read_text())
    assert gates["verdict"] == "PASS" and "snapshot" in gates["tool"]["name"]


def test_roles_get_their_write_scope_and_inspector_is_read_only(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}, "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 0, out
    a = next(c for c in calls if c["role"] == "author")
    i = next(c for c in calls if c["role"] == "inspector")
    assert a["active_role"]["write_scope"] == ["hi/sys-req/**"] and a["env_role"] == "author"
    assert i["active_role"]["write_scope"] == [] and i["active_role"]["role"] == "inspector"
    assert not (root / ".hi/active-role.json").exists()


def test_inspector_binding_must_be_read_only(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}}, read_only=False)
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 2 and "read_only" in out["error"] and calls == []


def test_inspector_file_write_is_rejected(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}, "inspector": {"write_file": "hi/sys-req/requirements.json.bak"}})
    code, out, _ = conduct(root, sc, "--stage", "sys-req")
    assert code == 1 and out["stages"][0]["outcome"] == "BLOCKED"
    assert "outside its write scope" in out["stages"][0]["reason"]
    scope_gate = json.loads((root / "hi/sys-req/gates/scope.json").read_text())
    assert scope_gate["verdict"] == "FAIL"


def test_author_write_outside_scope_blocks(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS, "write_outside": "src/sneaky.c"}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 1 and out["stages"][0]["outcome"] == "BLOCKED"
    assert [c["role"] for c in calls] == ["author"]


def test_rework_changes_to_other_items_are_discarded_and_splits_are_judged(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    new = dict(SYS_ITEMS[0], id="SYS-SUP-003", text="The supervisor shall report a missing alive indication within 10 ms.")
    sc = setup(root, {
        "author": {"items": SYS_ITEMS, "rework_also": {"SYS-SUP-002": {"text": "The supervisor shall do something new."}},
                   "split": {"SYS-SUP-001": [new]}},
        "inspector": {"item_rounds": [{"SYS-SUP-001": [F("IQ-05")]}, {}], "set_rounds": [[]]},
    })
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 0, out
    items = {i["id"]: i for i in json.loads((root / "hi/sys-req/requirements.json").read_text())["items"]}
    assert items["SYS-SUP-002"]["text"] == SYS_ITEMS[1]["text"]
    assert "SYS-SUP-003" in items
    assert ("inspector", "item", 2, ("SYS-SUP-001", "SYS-SUP-003")) in seq(calls)


def test_unresolved_findings_are_carried_to_set_phase(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {
        "author": {"items": SYS_ITEMS},
        "inspector": {"item_rounds": [{"SYS-SUP-001": [F("IQ-03")]}] * 5, "set_rounds": [[]]},
    }, level="HI-0")  # generic HI-0: rework limit 2
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    item_rounds = [c for c in calls if c["phase"] == "item"]
    # the fake author leaves the item exactly as it was: it is not judged again, its finding is carried
    assert len(item_rounds) == 1 and [c["items"] for c in calls if c["phase"] == "rework"] == [["SYS-SUP-001"]]
    assert any(e.get("step") == "rework-check" and e.get("unchanged") for e in events(root, out))
    set_call = next(c for c in calls if c["phase"] == "set")
    assert set_call["findings"] == 1
    assert out["stages"][0]["outcome"] == "ACCEPTED"        # the set inspector did not re-raise it


def test_rework_limit_exhaustion_blocks(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    # the author changes the item every time; the inspector keeps finding one defect, on a different criterion each
    # round (not the same findings, so not stuck; not fewer, so no progress extension): the base limit applies
    rot = ["IQ-02", "IQ-04", "IQ-06", "IQ-09", "IQ-02", "IQ-04", "IQ-06", "IQ-09"]
    sc = setup(root, {
        "author": {"items": SYS_ITEMS, "rework_touch": True},
        "inspector": {"item_rounds": [{"SYS-SUP-001": [F(c, "blocking")]} for c in rot],
                      "set_rounds": [[dict(F(c, "blocking"), target_id="SYS-SUP-001")] for c in rot]},
    })
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 1 and out["status"] == "BLOCKED"
    assert "open blocking findings" in out["stages"][0]["reason"]
    reworks = [c for c in calls if c["phase"] == "rework"]
    assert len(reworks) == 3                                 # generic HI-2 rework limit 3
    assert len([c for c in calls if c["phase"] == "rework-set"]) == 3
    state = json.loads((root / ".hi/state.json").read_text())["stages"]["sys-req"]
    assert state["state"] == "blocked"


def test_gate_issues_go_back_to_author_before_inspection(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    bad = [dict(SYS_ITEMS[0], text="The supervisor reacts quickly to a missing alive indication."), SYS_ITEMS[1]]
    sc = setup(root, {
        "author": {"items": bad, "fix_gates": [{"id": "SYS-SUP-001", "text": SYS_ITEMS[0]["text"]}]},
        "inspector": {"item_rounds": [{}], "set_rounds": [[]]},
    })
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 0, out
    assert seq(calls)[:3] == [("author", "create", 0, ()), ("author", "fix-gates", 1, ()),
                              ("inspector", "item", 1, ("SYS-SUP-001", "SYS-SUP-002"))]


def test_unparseable_inspector_reply_is_retried_then_blocks(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}, "inspector": {"garbage": True}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 1 and "not a findings object" in out["stages"][0]["reason"]
    assert [c["role"] for c in calls] == ["author", "inspector", "inspector"]


def test_events_have_no_raw_prompt_unless_enabled(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}, "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    _, out, _ = conduct(root, sc, "--stage", "sys-req")
    ev = events(root, out)
    assert ev and not any("prompt" in e or "reply" in e for e in ev)
    assert {"stage-start", "role", "gate", "findings", "stage-end"} <= {e["step"] for e in ev}
    assert not list((root / ".hi/runs").rglob("*.prompt.md"))

    root2 = tmp_path / "q"
    root2.mkdir()
    sc2 = setup(root2, {"author": {"items": SYS_ITEMS}, "inspector": {"item_rounds": [{}], "set_rounds": [[]]}}, raw=True)
    _, out2, _ = conduct(root2, sc2, "--stage", "sys-req")
    roles = [e for e in events(root2, out2) if e["step"] == "role"]
    assert all("prompt" in e and "reply" in e for e in roles)


def test_same_model_family_at_hi3_is_an_independence_gap(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}, "inspector": {"item_rounds": [{}], "set_rounds": [[]]}},
               level="HI-3", inspector_family="fake-a")
    code, out, _ = conduct(root, sc, "--stage", "sys-req")
    assert code == 1 and out["stages"][0]["gates"]["independence"] == "FAIL"
    assert out["stages"][0]["outcome"] == "BLOCKED"


def test_two_stages_with_until(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}, "inspector": {"item_rounds": [{}], "set_rounds": [[]]}},
               stages=("sys-req", "sw-req"))
    # the fake author writes the same items for every stage, so sw-req fails on IDs: it must stop BLOCKED there
    code, out, calls = conduct(root, sc, "--stage", "sys-req", "--until", "sw-req")
    assert [s["outcome"] for s in out["stages"]] == ["ACCEPTED", "BLOCKED"]
    sw_author = next(c for c in calls if c["role"] == "author" and c["phase"] == "create" and
                     c["active_role"]["stage"] == "sw-req")
    assert sw_author["active_role"]["write_scope"] == ["hi/sw-req/**"]


def test_dry_run_calls_nothing(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req", "--dry-run")
    assert code == 0 and out["status"] == "DRY_RUN" and calls == []


def test_manual_harness_is_assisted_mode(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    make_project(root)
    code, out, _ = conduct(root, root / "none.json", "--stage", "sys-req")
    assert code == 2 and "assisted mode" in out["error"]


def clean_scenario(**author):
    return {"author": {"items": SYS_ITEMS, **author}, "inspector": {"item_rounds": [{}] * 9, "set_rounds": [[]] * 9}}


def test_rerun_without_changes_keeps_inspected_items(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, clean_scenario())
    assert conduct(root, sc, "--stage", "sys-req")[0] == 0
    (root.parent / "p-calls.jsonl").unlink()
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 0, out
    assert seq(calls) == [("inspector", "set", 2, ())]       # no author call, no item re-judge


def test_input_change_updates_and_rejudges_only_changed_items(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    new_text = "The supervisor shall detect a missing alive indication of a supervised task within 30 ms."
    sc = setup(root, clean_scenario(update={"patch": {"SYS-SUP-001": {"text": new_text}}}))
    assert conduct(root, sc, "--stage", "sys-req")[0] == 0
    (root.parent / "p-calls.jsonl").unlink()
    needs = root / "needs/stakeholder-needs.md"
    needs.write_text(needs.read_text().replace("stops.", "stops for 30 ms."))
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 0, out
    assert calls[0]["phase"] == "update" and calls[0]["changed_inputs"] == ["needs/stakeholder-needs.md"]
    assert calls[0]["suspect"] == ["SYS-SUP-001"]
    assert ("inspector", "item", 2, ("SYS-SUP-001",)) in seq(calls)
    assert out["stages"][0]["outcome"] == "ACCEPTED"          # re-accepted: the suspect link is re-baselined


def test_blocking_open_point_then_answer_unblocks(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    op = [{"id": "OP-SYS-001", "text": "The repeat count is not given.", "raised_by": "author", "blocks": True}]
    sc = setup(root, clean_scenario(open_points=op, update={"open_points": []}))
    code, out, _ = conduct(root, sc, "--stage", "sys-req")
    assert code == 1 and "blocking open points" in out["stages"][0]["reason"]
    (root / "needs/constraints.md").write_text(CONSTRAINT_ANSWER)
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 0 and out["stages"][0]["outcome"] == "ACCEPTED", out
    assert calls[-3]["phase"] == "update" or any(c["phase"] == "update" for c in calls)


CONSTRAINT_ANSWER = "| CON-SUP-001 | Target: a Cortex-M55 microcontroller. |\n| CON-SUP-002 | Latch after 3 faults. |\n"


def test_fresh_reauthors(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, clean_scenario())
    conduct(root, sc, "--stage", "sys-req")
    (root.parent / "p-calls.jsonl").unlink()
    _, _, calls = conduct(root, sc, "--stage", "sys-req", "--fresh")
    assert calls[0]["phase"] == "create"


def test_findings_blocked_by_an_open_point_are_carried_not_reworked(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    op = [{"id": "OP-SYS-001", "text": "The repeat count is not given.", "raised_by": "author", "blocks": True}]
    waits = dict(F("IQ-06", "blocking"), blocked_by="OP-SYS-001")
    sc = setup(root, {"author": {"items": SYS_ITEMS, "open_points": op},
                      "inspector": {"item_rounds": [{"SYS-SUP-001": [waits], "SYS-SUP-002": [F("IQ-04")]}, {}],
                                    "set_rounds": [[]]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    reworked = [c["items"] for c in calls if c["phase"] == "rework"]
    assert reworked == [["SYS-SUP-002"]]                      # the blocked finding is not sent to rework
    fs = json.loads((root / "hi/sys-req/inspection/findings.json").read_text())["findings"]
    blocked = [f for f in fs if f.get("blocked_by") == "OP-SYS-001"]
    assert blocked and blocked[0]["status"] == "carried"
    assert code == 1 and "blocking open points" in out["stages"][0]["reason"]


def test_blocked_by_an_unknown_open_point_is_ignored(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS},
                      "inspector": {"item_rounds": [{"SYS-SUP-001": [dict(F("IQ-06"), blocked_by="OP-SYS-404")]}, {}],
                                    "set_rounds": [[]]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert [c["items"] for c in calls if c["phase"] == "rework"] == [["SYS-SUP-001"]]
    assert code == 0, out


def test_sigterm_clears_the_active_role(tmp_path):
    import signal
    import time
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS, "sleep": 30}})
    env = {"FAKE_SCENARIO": str(sc), "FAKE_LOG": str(tmp_path / "log.jsonl"), "PATH": "/usr/bin:/bin"}
    proc = subprocess.Popen([sys.executable, str(CONDUCT), "--stage", "sys-req"], cwd=root, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for _ in range(100):
        if (root / ".hi/active-role.json").exists():
            break
        time.sleep(0.1)
    assert (root / ".hi/active-role.json").exists()
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=20)
    assert proc.returncode != 0
    assert not (root / ".hi/active-role.json").exists()


def test_set_rework_changes_are_not_suspect_after_the_set_is_judged_again(tmp_path):
    # run 2 (2026-11-22): items changed by the set rework kept TR-SUSPECT links ("changed since acceptance"), so the
    # final trace gate failed although the set inspector had judged the changed set afterwards
    root = tmp_path / "p"
    root.mkdir()
    set_f = dict(F("SQ-05"), target_id="SYS-SUP-001")
    fixed = "The supervisor shall detect a missing alive indication of a supervised task within 30 ms."
    sc = setup(root, {"author": {"items": SYS_ITEMS, "set_fix": {"SYS-SUP-001": {"text": fixed}}},
                      "inspector": {"item_rounds": [{}], "set_rounds": [[set_f], []]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert [c["phase"] for c in calls if c["role"] == "author"] == ["create", "rework-set"]
    assert out["stages"][0]["gates"]["trace"] == "PASS", out
    assert code == 0 and out["stages"][0]["outcome"] == "ACCEPTED", out


def test_set_inspector_re_raising_a_waiting_finding_does_not_duplicate_it(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    op = [{"id": "OP-SYS-001", "text": "The repeat count is not given.", "raised_by": "author", "blocks": True}]
    waits = dict(F("IQ-06", "blocking"), blocked_by="OP-SYS-001")
    sc = setup(root, {"author": {"items": SYS_ITEMS, "open_points": op},
                      "inspector": {"item_rounds": [{"SYS-SUP-001": [waits]}],
                                    "set_rounds": [[dict(waits, target_id="SYS-SUP-001")]]}})
    code, out, _ = conduct(root, sc, "--stage", "sys-req")
    fs = json.loads((root / "hi/sys-req/inspection/findings.json").read_text())["findings"]
    live = [f for f in fs if f["status"] in ("open", "carried")]
    assert [(f["target_id"], f["checklist_item"], f.get("blocked_by")) for f in live] == \
        [("SYS-SUP-001", "IQ-06", "OP-SYS-001")]                # the re-raised one replaces the carried one
    assert code == 1 and "blocking open points" in out["stages"][0]["reason"]


@pytest.mark.parametrize("phase", ["create", "rework", "rework-set"])
def test_invalid_json_from_the_author_goes_back_as_a_gate_issue(tmp_path, phase):
    # run 3 (2026-11-22): a set rework left requirements.json without a comma and the conductor stopped with ERROR
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS, "break_json": [phase]},
                      "inspector": {"item_rounds": [{"SYS-SUP-001": [F("IQ-03")]}, {}],
                                    "set_rounds": [[dict(F("SQ-05"), target_id="SYS-SUP-002")], []]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert out.get("status") != "ERROR", out
    i = next(n for n, c in enumerate(calls) if c["role"] == "author" and c["phase"] == phase)
    assert calls[i + 1]["role"] == "author" and calls[i + 1]["phase"] == "fix-gates"
    assert code == 0 and out["stages"][0]["outcome"] == "ACCEPTED", out


def test_json_the_author_cannot_repair_blocks_cleanly(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS, "break_json": ["rework-set", "always"]},
                      "inspector": {"item_rounds": [{}], "set_rounds": [[dict(F("SQ-05"), target_id="SYS-SUP-002")]]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 1 and out["status"] == "BLOCKED", out
    assert "not valid JSON" in out["stages"][0]["reason"]
    assert out["stages"][0]["gates"]["validate"] == "FAIL"
    assert not (root / ".hi/active-role.json").exists()


def test_rework_continues_past_the_limit_while_findings_fall(tmp_path):
    # owner plan 2026-11-14: keep reworking while the open findings fall, up to the safety cap
    root = tmp_path / "p"
    root.mkdir()
    items = SYS_ITEMS + [req(f"SYS-SUP-{n:03d}", f"The supervisor shall report event {n} within 10 ms.", ["STK-SUP-001"])
                         for n in range(3, 9)]
    ids = [i["id"] for i in items]
    rounds = [{i: [F("IQ-04")] for i in ids[:k]} for k in (8, 7, 6, 5, 4, 3, 2, 1, 0)]
    sc = setup(root, {"author": {"items": items, "rework_touch": True},
                      "inspector": {"item_rounds": rounds, "set_rounds": [[]]}}, level="HI-0")  # base limit 2
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    item_rounds = [c for c in calls if c["phase"] == "item"]
    assert len(item_rounds) == 9                             # 8 rework rounds, far past the base limit of 2
    assert code == 0 and out["stages"][0]["outcome"] == "ACCEPTED", out


def test_rework_stops_when_two_rounds_return_the_same_findings(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS, "rework_touch": True},
                      "inspector": {"item_rounds": [{"SYS-SUP-001": [F("IQ-04", "blocking")]}] * 6,
                                    "set_rounds": [[dict(F("IQ-04", "blocking"), target_id="SYS-SUP-001")]] * 6}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert len([c for c in calls if c["phase"] == "rework"]) == 1   # round 2 repeats round 1: stuck, stop
    stuck = [e for e in events(root, out) if e.get("step") == "rework-stuck"]
    assert stuck and stuck[0]["phase"] == "item"
    assert code == 1 and "open blocking findings" in out["stages"][0]["reason"]


def test_open_major_findings_give_accepted_with_gaps_and_a_seal_gap(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS},
                      "inspector": {"item_rounds": [{"SYS-SUP-001": [F("IQ-04", "major")]}],
                                    "set_rounds": [[dict(F("IQ-04", "major"), target_id="SYS-SUP-001")]] * 5}})
    code, out, _ = conduct(root, sc, "--stage", "sys-req")
    st = out["stages"][0]
    assert st["outcome"] == "ACCEPTED_WITH_GAPS" and "open major findings" in st["reason"], out
    from forge_hi import seal
    from forge_hi.config import load_project
    gaps, _ = seal.collect_gaps(root, load_project(root))
    assert any(g["code"] == "FINDING-MAJOR" for g in gaps)


def test_different_set_findings_on_the_same_criterion_are_not_stuck(tmp_path):
    root = tmp_path / "p"
    root.mkdir()

    def sq(ids):
        return dict(F("SQ-01", "blocking", desc=f"The set does not cover {ids}."), target_id="SET")

    sc = setup(root, {"author": {"items": SYS_ITEMS, "rework_touch": True},
                      "inspector": {"item_rounds": [{}],
                                    "set_rounds": [[sq("CON-SUP-001 and CON-SUP-004"), sq("CON-SUP-002")],
                                                   [sq("CON-SUP-003")], []]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert not [e for e in events(root, out) if e.get("step") == "rework-stuck"]
    assert len([c for c in calls if c["phase"] == "rework-set"]) == 2
    assert code == 0 and out["stages"][0]["outcome"] == "ACCEPTED", out
    # the same defect again (same criterion, same cited ids) is stuck
    root2 = tmp_path / "q"
    root2.mkdir()
    sc = setup(root2, {"author": {"items": SYS_ITEMS, "rework_touch": True},
                       "inspector": {"item_rounds": [{}], "set_rounds": [[sq("CON-SUP-003")]] * 4}})
    code, out, calls = conduct(root2, sc, "--stage", "sys-req")
    assert [e for e in events(root2, out) if e.get("step") == "rework-stuck"]
    assert len([c for c in calls if c["phase"] == "rework-set"]) == 1



def test_author_that_writes_no_workproduct_gets_one_corrective_retry(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS, "skip_create_once": True},
                      "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    creates = [c for c in calls if c["role"] == "author" and c["phase"] == "create"]
    assert len(creates) == 2 and creates[1]["notice"] and "directly" in creates[1]["notice"]
    assert any(e.get("step") == "author-retry" for e in events(root, out))
    assert code == 0 and out["stages"][0]["outcome"] == "ACCEPTED", out


# ---------------------------------------------------------------- governance step (feature 020 port)
GOV_UC = {"id": "UC-SUP-001", "title": "Supervise", "actor": "ACT-SUP-001", "goal": "Every failure is noticed.",
          "needs": ["STK-SUP-001", "STK-SUP-002"]}


def gov(**kw):
    from hi_helpers import governance_doc
    return governance_doc(**{"use_cases": [GOV_UC], **kw})


def test_governance_comes_first_and_coverage_gaps_go_back_to_the_author(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS, "governance": gov(use_cases=[dict(GOV_UC, needs=["STK-SUP-001"])]),
                                 "governance_fix": gov()},
                      "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req", gov=True)
    assert code == 0 and out["stages"][0]["outcome"] == "ACCEPTED", out
    assert [c["phase"] for c in calls[:3]] == ["governance", "fix-governance", "create"]
    assert calls[1]["findings"] == 1
    ev = [e for e in events(root, out) if e["step"] == "governance"]
    assert [e["codes"] for e in ev] == [["GOV-NEED-UNCOVERED"], []]
    g = json.loads((root / "hi/sys-req/gates/governance.json").read_text())
    assert g["verdict"] == "PASS"


def test_governance_coverage_that_cannot_be_fixed_blocks_before_any_requirement(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS, "governance": gov(use_cases=[dict(GOV_UC, needs=["STK-SUP-001"])])}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req", gov=True)
    assert code == 1 and out["stages"][0]["outcome"] == "BLOCKED"
    assert "governance coverage" in out["stages"][0]["reason"] and "GOV-NEED-UNCOVERED" in out["stages"][0]["reason"]
    assert "create" not in [c["phase"] for c in calls]


def test_unrealised_use_case_goes_back_as_a_gate_issue(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    fix = [{"id": i["id"], "attributes": {"use_cases": ["UC-SUP-001"]}} for i in SYS_ITEMS]
    sc = setup(root, {"author": {"items": SYS_ITEMS, "governance": gov(), "no_use_cases": True, "fix_gates": fix},
                      "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 0 and out["stages"][0]["outcome"] == "ACCEPTED", out
    assert [c["phase"] for c in calls[:2]] == ["create", "fix-gates"]


def test_blocking_governance_open_point_blocks_the_stage(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    op = {"id": "OP-GOV-001", "text": "Who owns the supervision configuration?", "concerns": ["STK-SUP-002"],
          "blocks": True}
    sc = setup(root, {"author": {"items": SYS_ITEMS, "governance": gov(open_points=[op])},
                      "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    code, out, _ = conduct(root, sc, "--stage", "sys-req")
    assert code == 1 and out["stages"][0]["outcome"] == "BLOCKED"
    assert "OP-GOV-001" in out["stages"][0]["reason"]


def test_governance_is_updated_only_when_inputs_change(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS, "governance": gov()},
                      "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    assert conduct(root, sc, "--stage", "sys-req")[0] == 0
    log = root.parent / f"{root.name}-calls.jsonl"
    log.unlink()
    code, out, calls = conduct(root, sc, "--stage", "sys-req", gov=True)
    assert code == 0 and "governance" not in [c["phase"] for c in calls]
    log.unlink()
    with open(root / "needs/stakeholder-needs.md", "a") as fh:
        fh.write("\nA clarification by the product owner.\n")
    code, out, calls = conduct(root, sc, "--stage", "sys-req", gov=True)
    assert code == 0, out
    assert calls[0]["phase"] == "governance" and calls[0]["changed_inputs"] == ["needs/stakeholder-needs.md"]
    assert calls[1]["phase"] == "update"


def test_a_changed_checklist_or_inspector_skill_invalidates_earlier_judgements(tmp_path, monkeypatch):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}, "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    assert conduct(root, sc, "--stage", "sys-req")[0] == 0
    jp = root / "hi/sys-req/inspection/judged.json"
    rec = json.loads(jp.read_text())
    assert "checklists/requirements-item.json" in rec["basis"] and "hi-sys-req-inspector" in rec["basis"]
    log = root.parent / f"{root.name}-calls.jsonl"
    log.unlink()
    _, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert [c["phase"] for c in calls if c["role"] == "inspector"] == ["set"]   # nothing changed: judgements kept
    rec["basis"]["checklists/requirements-item.json"] = "0" * 64              # as if the checklist had changed
    jp.write_text(json.dumps(rec))
    log.unlink()
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 0, out
    assert [tuple(c["items"]) for c in calls if c["phase"] == "item"] == [("SYS-SUP-001", "SYS-SUP-002")]
    assert any(e["step"] == "basis-changed" for e in events(root, out))


def test_findings_may_wait_on_a_governance_open_point(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    op = {"id": "OP-GOV-001", "text": "Is lateness measured per task or per cycle?", "concerns": ["STK-SUP-002"],
          "blocks": True}
    waits = dict(F("IQ-04", "blocking"), blocked_by="OP-GOV-001")
    sc = setup(root, {"author": {"items": SYS_ITEMS, "governance": gov(open_points=[op])},
                      "inspector": {"item_rounds": [{"SYS-SUP-002": [waits]}, {}], "set_rounds": [[]]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert [c for c in calls if c["phase"] == "rework"] == []        # waits on the decision, no rework
    fs = json.loads((root / "hi/sys-req/inspection/findings.json").read_text())["findings"]
    assert [f["status"] for f in fs if f.get("blocked_by") == "OP-GOV-001"] == ["carried"]
    assert code == 1 and "OP-GOV-001" in out["stages"][0]["reason"]
