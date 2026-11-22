"""T028: the conductor with a fake harness (no model)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SKILLS
from hi_helpers import SWR_ITEMS, SYS_ITEMS, make_project, write

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


def conduct(root, sc, *args):
    log = root.parent / f"{root.name}-calls.jsonl"
    env = {"FAKE_SCENARIO": str(sc), "FAKE_LOG": str(log), "PATH": "/usr/bin:/bin"}
    r = subprocess.run([sys.executable, str(CONDUCT), *args], cwd=root, capture_output=True, text=True, timeout=120,
                       env=env)
    calls = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
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
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 0, out
    assert out["status"] == "DONE" and out["stages"][0]["outcome"] == "ACCEPTED"
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
    assert len(item_rounds) == 3                            # judge + 2 re-judges (limit 2)
    set_call = next(c for c in calls if c["phase"] == "set")
    assert set_call["findings"] == 1
    assert out["stages"][0]["outcome"] == "ACCEPTED"        # the set inspector did not re-raise it


def test_rework_limit_exhaustion_blocks(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {
        "author": {"items": SYS_ITEMS},
        "inspector": {"item_rounds": [{"SYS-SUP-001": [F("IQ-02", "blocking")]}] * 5,
                      "set_rounds": [[dict(F("IQ-02", "blocking"), target_id="SYS-SUP-001")]] * 5},
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
