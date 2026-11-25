"""T028: the conductor with a fake harness (no model)."""
from __future__ import annotations

import hashlib
import json
import shutil
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
    assert seq(calls) == []                 # an accepted stage with nothing changed is kept, no model is called
    assert out["stages"][0]["outcome"] == "ACCEPTED" and out["stages"][0]["kept"] is True


def test_an_accepted_stage_is_kept_only_while_nothing_it_was_judged_on_changed(tmp_path):
    def edit(rel_path, fn):
        def go(root):
            f = root / rel_path
            f.write_text(fn(f.read_text()))
        return go

    def touched(text):
        d = json.loads(text)
        d["items"][0]["attributes"] = {**d["items"][0].get("attributes", {}), "rationale": "edited by hand"}
        return json.dumps(d)

    def gapped(text):
        d = json.loads(text)
        d["stages"]["sys-req"]["outcome"] = "ACCEPTED_WITH_GAPS"
        return json.dumps(d)

    cases = {"input": edit("needs/stakeholder-needs.md", lambda t: t + "\nA clarification.\n"),
             "workproduct": edit("hi/sys-req/requirements.json", touched),
             "settings": edit(".hi/project.json", lambda t: t + "\n"),
             "gaps": edit(".hi/state.json", gapped)}
    for name, change in cases.items():
        root = tmp_path / name
        root.mkdir()
        sc = setup(root, clean_scenario())
        assert conduct(root, sc, "--stage", "sys-req")[0] == 0
        (root.parent / f"{name}-calls.jsonl").unlink()
        change(root)
        code, out, calls = conduct(root, sc, "--stage", "sys-req")
        assert not out["stages"][0].get("kept"), name
        assert "set" in [c["phase"] for c in calls], name


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
    log.unlink(missing_ok=True)
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
    assert [c for c in calls if c["role"] == "inspector"] == []                 # nothing changed: judgements kept
    rec["basis"]["checklists/requirements-item.json"] = "0" * 64              # as if the checklist had changed
    jp.write_text(json.dumps(rec))
    sp = root / ".hi/state.json"
    state = json.loads(sp.read_text())
    state["stages"]["sys-req"]["fingerprint"]["basis:checklists/requirements-item.json"] = "0" * 64
    sp.write_text(json.dumps(state))
    log.unlink(missing_ok=True)
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


# ---------------------------------------------------------------- coverage matrix (guideline 3.1, T089)
def test_coverage_matrix_rules(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    rows1 = [
        {"source": "STK-SUP-001", "requirements": ["SYS-SUP-001"], "status": "covered", "reason": ""},
        {"source": "STK-SUP-002", "requirements": ["SYS-SUP-002", "SYS-SUP-404"], "status": "partial",
         "reason": "Only the deadline, not the start."},                                 # tracked by the finding below
        {"source": "shutdown", "requirements": [], "status": "n/a", "reason": ""},       # n/a without reason -> gap
        {"source": "invalid input", "requirements": [], "status": "n/a", "reason": "The supervisor takes no input."},
        {"source": "recovery", "requirements": [], "status": "covered", "reason": ""},   # covered by nothing -> gap
    ]
    set_f = dict(F("SQ-02"), target_id="SET", description="STK-SUP-002 is only partly covered.")
    sc = setup(root, {"author": {"items": SYS_ITEMS, "rework_touch": True},
                      "inspector": {"item_rounds": [{}], "set_rounds": [[set_f], []],
                                    "coverage_rounds": [rows1, [dict(r, status="covered", requirements=["SYS-SUP-001"])
                                                                for r in rows1]]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert code == 0 and out["stages"][0]["outcome"] == "ACCEPTED", out
    r1 = json.loads((root / "hi/sys-req/inspection/set-r1.json").read_text())["findings"]
    auto = [f for f in r1 if f["description"].startswith("Coverage")]
    assert sorted(f["description"].split(":")[1].split(" - ")[0].strip() for f in auto) == ["recovery", "shutdown"]
    assert {f["checklist_item"] for f in auto} == {"SQ-01"} and {f["severity"] for f in auto} == {"major"}
    ev = [e for e in events(root, out) if e["step"] == "coverage"]
    assert ev[0]["raised"] == 2 and ev[0]["gap"] == 2 and ev[0]["partial"] == 1 and ev[0]["na"] == 1
    cov = json.loads((root / "hi/sys-req/inspection/coverage.json").read_text())
    assert cov["round"] == 2 and {r["status"] for r in cov["rows"]} == {"covered"}
    from forge_hi.config import schema
    from forge_hi.jsonschema_lite import validate
    assert validate(cov, schema("coverage-matrix")) == []
    assert [c["phase"] for c in calls if c["role"] == "author"].count("rework-set") == 1


def test_set_reply_without_coverage_is_recorded_as_not_provided(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}, "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    code, out, _ = conduct(root, sc, "--stage", "sys-req")
    assert code == 0, out
    cov = json.loads((root / "hi/sys-req/inspection/coverage.json").read_text())
    assert cov["provided"] is False and cov["rows"] == []


def test_coverage_row_that_points_at_a_finding_or_open_point_is_tracked(tmp_path):
    # run 6 pass 2: rows whose reason said "see the SQ-10 finding" were raised again as SQ-01 findings
    root = tmp_path / "p"
    root.mkdir()
    op = [{"id": "OP-SYS-001", "text": "The start-up message has no deadline.", "raised_by": "author", "blocks": False,
           "deferred_to": "sw-req"}]
    rows = [{"source": "STK-SUP-002", "requirements": ["SYS-SUP-002"], "status": "partial",
             "reason": "Margins are missing; see the SQ-10 finding."},
            {"source": "start-up", "requirements": [], "status": "gap", "reason": "Deadline open in OP-SYS-001."},
            {"source": "shutdown", "requirements": [], "status": "partial", "reason": "Only power loss is covered."}]
    sq10 = dict(F("SQ-10", "minor"), target_id="SET", description="The verification margins are not recorded.")
    sc = setup(root, {"author": {"items": SYS_ITEMS, "open_points": op},
                      "inspector": {"item_rounds": [{}], "set_rounds": [[sq10], []], "coverage_rounds": [rows]}})
    code, out, _ = conduct(root, sc, "--stage", "sys-req")
    r1 = json.loads((root / "hi/sys-req/inspection/set-r1.json").read_text())["findings"]
    auto = [f["description"] for f in r1 if f["description"].startswith("Coverage")]
    assert auto == ["Coverage partial: shutdown - Only power loss is covered."]
    assert code == 0, out                                   # the one real gap was reworked in round 2


def test_an_open_point_id_names_one_question_across_passes(tmp_path):
    # run 6 pass 3: OP-SYS-004 was answered, and the author gave a new, unrelated question the same id
    root = tmp_path / "p"
    root.mkdir()
    old = {"id": "OP-SYS-001", "text": "Which fault reports wait while an answer line is being transmitted?",
           "raised_by": "author", "blocks": True}
    new = {"id": "OP-SYS-001", "text": "Does the checked CRC range include the byte at the end symbol address?",
           "raised_by": "author", "blocks": True}
    reworded = dict(old, text="Which fault reports must wait while an answer line is still being transmitted?")
    sc = setup(root, {"author": {"items": SYS_ITEMS, "open_points": [old]},
                      "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    assert conduct(root, sc, "--stage", "sys-req")[0] == 1                  # blocked on the open point
    hist = json.loads((root / "hi/sys-req/inspection/open-points.json").read_text())["ids"]
    assert hist["OP-SYS-001"]["retired"] is False
    with open(root / "needs/stakeholder-needs.md", "a") as fh:
        fh.write("\nA decision by the product owner.\n")
    fresh_id = dict(new, id="OP-SYS-002")
    sc.write_text(json.dumps({"author": {"items": SYS_ITEMS, "update": {"open_points": [new]},
                                         "fix_open_points": [fresh_id]},
                              "inspector": {"item_rounds": [{}], "set_rounds": [[]]}}))
    log = root.parent / f"{root.name}-calls.jsonl"
    log.unlink()
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert [c["phase"] for c in calls if c["role"] == "author"][:2] == ["update", "fix-gates"]
    wp = json.loads((root / "hi/sys-req/requirements.json").read_text())
    assert [o["id"] for o in wp["open_points"]] == ["OP-SYS-002"]
    hist = json.loads((root / "hi/sys-req/inspection/open-points.json").read_text())["ids"]
    assert hist["OP-SYS-001"]["retired"] is True and hist["OP-SYS-002"]["retired"] is False
    # a reworded question keeps its id
    sys.path.insert(0, str(CONDUCT.parent))
    from conduct import Conductor
    assert Conductor._same_question(old["text"], reworded["text"]) and not Conductor._same_question(old["text"], new["text"])


def test_an_existing_governance_package_with_gaps_is_fixed_before_writing(tmp_path):
    # driver demo T052: a run stopped during fix-governance; the next run must not write requirements on that package
    root = tmp_path / "p"
    root.mkdir()
    partial = gov(use_cases=[dict(GOV_UC, needs=["STK-SUP-001"])])
    write(root / "hi/sys-req/governance.json", partial)
    sc = setup(root, {"author": {"items": SYS_ITEMS, "governance_fix": gov()},
                      "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    write(root / "hi/sys-req/governance.json", partial)              # setup() rewrote the project, not this file
    code, out, calls = conduct(root, sc, "--stage", "sys-req", gov=True)
    assert code == 0, out
    assert [c["phase"] for c in calls[:2]] == ["fix-governance", "create"]


def test_document_coverage_row_is_tracked_by_a_finding_citing_its_section():
    # driver demo T052: rows "RM0486#59.7.1" were raised again although a finding cited "sections 59.2 ... and 59.7.1"
    sys.path.insert(0, str(CONDUCT.parent))
    from conduct import Conductor
    f = {"id": "F-1", "checklist_item": "SQ-01", "target_id": "SET"}
    texts = {"F-1": "SET RM0486 sections 59.2, 59.4.4 and 59.7.1 remain partially covered."}
    assert Conductor.row_tracker("RM0486#59.7.1", "inherits the refresh findings", [f], texts, {}) == "F-1"
    assert Conductor.row_tracker("RM0486#59.7", "inherits the refresh findings", [f], texts, {}) is None
    assert Conductor.row_tracker("RM0486#59.4", "", [f], texts, {}) is None
    assert Conductor.row_tracker("RM9999#59.2", "", [f], texts, {}) is None


def test_task_gives_the_author_the_current_input_hashes(tmp_path):
    # driver demo pass 3: after an input changed, the task still carried the hashes written by `hi init`
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}, "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    write(root / ".hi/inputs.lock.json", {"schema": "forge-c-hi/inputs-lock@1", "inputs": {
        "needs/stakeholder-needs.md": "0" * 64}})
    sys.path.insert(0, str(CONDUCT.parent))
    from conduct import Conductor
    from forge_hi.io import sha256_file
    t = Conductor(root, dry_run=True).task("author", "sys-req", "create")
    assert t["input_hashes"]["needs/stakeholder-needs.md"] == sha256_file(root / "needs/stakeholder-needs.md")


def test_coverage_row_citing_an_item_with_a_finding_is_tracked():
    # driver demo pass 5: "The findings on DRV-IWDG-024 and DRV-IWDG-051 track ..." was raised again
    sys.path.insert(0, str(CONDUCT.parent))
    from conduct import Conductor
    fs = [{"id": "F-9", "checklist_item": "SQ-05", "target_id": "DRV-IWDG-024"}]
    texts = {"F-9": "DRV-IWDG-024 conflicts with the timeout handling."}
    assert Conductor.row_tracker("UC-IWDG-007", "The findings on DRV-IWDG-024 track it.", fs, texts, {}) == "F-9"
    assert Conductor.row_tracker("UC-IWDG-007", "See DRV-IWDG-099.", fs, texts, {}) is None


def test_linked_project_items_are_snapshotted_for_the_roles(tmp_path):
    # T052: the middleware's author must see the driver's DRV items to cite them
    from hi_helpers import reqset
    drv = tmp_path / "drv"
    make_project(drv, stages=("sw-req",), swr_items=[
        req("DRV-WDG-001", "The driver shall start the watchdog when the start service is called.",
            [{"kind": "document", "doc_id": "RM1", "section": "4.2", "page": 3}], level="driver_interface")])
    root = tmp_path / "p"
    root.mkdir()
    setup(root, {"author": {"items": SYS_ITEMS}})
    proj = json.loads((root / ".hi/project.json").read_text())
    proj["links"] = [{"project_path": "../drv", "level": "driver_interface"}]
    write(root / ".hi/project.json", proj)
    sys.path.insert(0, str(CONDUCT.parent))
    from conduct import Conductor
    c = Conductor(root, dry_run=True)
    t = c.task("author", "sys-req", "create")
    assert t["linked"] == [".hi/linked/01-drv-driver_interface.json"]
    snap = json.loads((root / t["linked"][0]).read_text())
    assert [i["id"] for i in snap["items"]] == ["DRV-WDG-001"] and "sources" not in snap["items"][0]


def test_code_gate_issues_go_back_to_the_author(tmp_path, monkeypatch):
    # full-V run T068: sw-design ended BLOCKED with a build error and a static-analysis error never sent to the author
    root = tmp_path / "p"
    root.mkdir()
    setup(root, {"author": {"items": SYS_ITEMS}})
    sys.path.insert(0, str(CONDUCT.parent))
    import conduct
    fake = {"verdict": "FAIL", "gates": {"build": "FAIL", "static-analysis": "FAIL", "scope": "FAIL"}, "issues": [
        {"gate": "build", "code": "BUILD-ERROR", "message": "src/crc32.c:29: 'NULL' undeclared"},
        {"gate": "static-analysis", "code": "SA-arrayIndexOutOfBounds", "message": "src/diag.c:83"},
        {"gate": "scope", "code": "SCOPE-OUTSIDE", "message": "x"}]}
    monkeypatch.setattr(conduct.gates, "gate_stage", lambda *a, **k: fake)
    _, issues = conduct.Conductor(root, dry_run=True).det_issues("sys-req")
    assert [i["gate"] for i in issues] == ["build", "static-analysis"]


def test_coverage_matrix_is_for_requirement_stages_only(tmp_path, monkeypatch):
    # full-V run T068: 84 of 90 open sys-arch findings were raised by the conductor from coverage rows
    root = tmp_path / "p"
    root.mkdir()
    setup(root, {"author": {"items": SYS_ITEMS}}, stages=("sys-req", "sys-arch"))
    write(root / "hi/sys-arch/architecture.json", {"items": [], "open_points": []})
    sys.path.insert(0, str(CONDUCT.parent))
    from conduct import Conductor
    c = Conductor(root)
    reply = {"status": "DONE", "findings": [], "coverage": [
        {"source": "STK-SUP-001", "requirements": ["SYS-SUP-001"], "status": "covered", "reason": ""}]}
    monkeypatch.setattr(c, "run_role", lambda *a, **k: reply)
    assert c.inspect("sys-arch", "set", 1, [], []) == []
    assert not (root / "hi/sys-arch/inspection/coverage.json").exists()
    for stage, wanted in (("sys-arch", False), ("sys-req", True), ("sw-req", True)):
        assert Conductor.has_coverage(stage) is wanted
    t = c.task("inspector", "sys-arch", "set")
    assert "coverage" not in t["reply_contract"] and "coverage matrix" not in c.prompt(t)
    t = c.task("inspector", "sys-req", "set")
    assert "coverage" in t["reply_contract"] and "coverage matrix" in c.prompt(t)


def test_different_set_findings_on_the_same_item_are_not_stuck(tmp_path):
    # full-V attempt 3 pass 11: one item contradicted one requirement, then (after the rework) another one
    root = tmp_path / "p"
    root.mkdir()

    def sq(other):
        return dict(F("SQ-05", "blocking", desc=f"SYS-SUP-001 contradicts {other}."), target_id="SYS-SUP-001")

    sc = setup(root, {"author": {"items": SYS_ITEMS, "rework_touch": True},
                      "inspector": {"item_rounds": [{}],
                                    "set_rounds": [[sq("SYS-SUP-002")], [sq("CON-SUP-003")], []]}})
    code, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert not [e for e in events(root, out) if e.get("step") == "rework-stuck"]
    assert len([c for c in calls if c["phase"] == "rework-set"]) == 2
    assert code == 0 and out["stages"][0]["outcome"] == "ACCEPTED", out


def test_different_defects_citing_the_same_ids_are_not_stuck(tmp_path):
    # full-V attempt 3 pass 13: two different defects in one decision share target, criterion and cited ids
    def sq(text):
        return dict(F("SYA-08", "blocking", desc=text), target_id="SET")

    one = sq("DEC-SUP-001 compares a free-running count but does not say how SYS-SUP-001 holds across rollover.")
    two = sq("SYS-SUP-001: the arm value of DEC-SUP-001 is one ahead, so an immediate check reports a violation.")
    again = sq("DEC-SUP-001 compares a free-running count and still does not say how SYS-SUP-001 holds across rollover.")
    for name, second, reworks in (("p", two, 2), ("q", again, 1)):
        root = tmp_path / name
        root.mkdir()
        sc = setup(root, {"author": {"items": SYS_ITEMS, "rework_touch": True},
                          "inspector": {"item_rounds": [{}], "set_rounds": [[one], [second], []]}})
        code, out, calls = conduct(root, sc, "--stage", "sys-req")
        assert len([c for c in calls if c["phase"] == "rework-set"]) == reworks, name
        assert bool([e for e in events(root, out) if e.get("step") == "rework-stuck"]) == (name == "q")


def returning(**sw):
    """sys-req and sw-req; the software author returns OP-SWR-001 to sys-req and drops it once told it was settled."""
    op = [{"id": "OP-SWR-001", "text": "SYS-SUP-002 cannot be met with SYS-SUP-001.", "blocks": True,
           "returned_to": "sys-req"}]
    sc = clean_scenario(by_stage={
        "sys-req": {"update": {"patch": {"SYS-SUP-002": {"rationale": "settled the returned point"}}}},
        "sw-req": {"items": SWR_ITEMS, "open_points": op, "update": {"open_points": []}, **sw}})
    return sc, op


def test_a_returned_point_goes_back_to_the_earlier_stage_and_is_settled(tmp_path):
    # full-V attempt 3 pass 19: sw-design found an accepted interface that could not meet an accepted time limit
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, returning()[0], stages=("sys-req", "sw-req"))
    code, out, calls = conduct(root, sc, "--stage", "sys-req", "--until", "sw-req")
    assert code == 0, out
    assert [(s["stage"], s["outcome"]) for s in out["stages"]] == [("sys-req", "ACCEPTED"), ("sw-req", "ACCEPTED")]
    back = [c for c in calls if c["stage"] == "sys-req" and c["returned"]]
    assert [(c["role"], c["phase"]) for c in back] == [("author", "update"), ("inspector", "set")]
    assert back[0]["returned"][0]["id"] == "OP-SWR-001" and back[0]["returned"][0]["from_stage"] == "sw-req"
    upd = [c for c in calls if c["stage"] == "sw-req" and c["phase"] == "update"]
    assert upd and upd[0]["open_points"] == ["OP-SWR-001"]
    assert [e["to_stage"] for e in events(root, out) if e.get("step") == "returned"] == ["sys-req"]


def test_a_point_returned_again_unchanged_waits_for_a_person(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc0, op = returning()
    sc0["author"]["by_stage"]["sw-req"]["update"] = {"open_points": op}
    sc = setup(root, sc0, stages=("sys-req", "sw-req"))
    code, out, calls = conduct(root, sc, "--stage", "sys-req", "--until", "sw-req")
    assert code == 1 and out["stages"][-1]["outcome"] == "BLOCKED"
    assert "OP-SWR-001" in out["stages"][-1]["reason"]
    assert sum(1 for c in calls if c["stage"] == "sys-req" and c["phase"] == "update") == 1


def test_a_point_for_a_person_is_not_returned(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc0, op = returning()
    op[0]["returned_to"] = None
    sc = setup(root, sc0, stages=("sys-req", "sw-req"))
    code, out, calls = conduct(root, sc, "--stage", "sys-req", "--until", "sw-req")
    assert code == 1 and [s["outcome"] for s in out["stages"]] == ["ACCEPTED", "BLOCKED"]
    assert not [c for c in calls if c["returned"]]


def test_a_returned_point_reopens_an_accepted_stage_in_a_later_run(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, returning()[0], stages=("sys-req", "sw-req"))
    assert conduct(root, sc, "--stage", "sys-req")[0] == 0
    code, out, calls = conduct(root, sc, "--stage", "sw-req")   # sys-req is not in this run: it cannot go back
    assert code == 1 and [s["stage"] for s in out["stages"]] == ["sw-req"]
    (root.parent / "p-calls.jsonl").unlink()
    code, out, calls = conduct(root, sc, "--stage", "sys-req", "--until", "sw-req")
    assert code == 0, out
    assert calls[0]["stage"] == "sys-req" and calls[0]["returned"][0]["id"] == "OP-SWR-001"


def test_failing_tests_returned_as_a_code_defect_are_not_sent_back_again(tmp_path, monkeypatch):
    root = tmp_path / "p"
    root.mkdir()
    setup(root, {"author": {"items": SYS_ITEMS}}, stages=("sys-req", "sw-req", "sw-design", "unit-verif"))
    write(root / "hi/unit-verif/test-spec.json", {"items": [], "open_points": [
        {"id": "OP-UTC-001", "text": "am_step returns the wrong code.", "blocks": True, "returned_to": "sw-design"}]})
    sys.path.insert(0, str(CONDUCT.parent))
    import conduct as cond
    c = cond.Conductor(root)
    ran = []
    monkeypatch.setattr(c, "run_role", lambda *a, **k: ran.append(a[2]))
    fails = [{"gate": "unit-test", "code": "UT-FAIL", "message": "UTC-SUP-004"}]
    monkeypatch.setattr(c, "det_issues", lambda s: (None, fails))
    with pytest.raises(cond.Blocked, match="OP-UTC-001 to sw-design"):
        c.author_with_gates_fix_only("unit-verif", fails)
    assert ran == ["fix-gates"]


def test_who_settles_a_blocking_open_point_is_stated(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    setup(root, {"author": {"items": SYS_ITEMS}}, stages=("sys-req", "sw-req", "sw-arch", "sw-design"))
    sys.path.insert(0, str(CONDUCT.parent))
    import conduct as cond
    project = cond.load_project(root)

    def bad(stage, **kw):
        return bool(cond.gates.check_returns(project, stage, [{"id": "OP-1", "text": "x", **kw}]))
    assert bad("sw-design", blocks=True)                                      # unclassified
    assert not bad("sw-design", blocks=True, returned_to="sw-arch")
    assert not bad("sw-design", blocks=True, returned_to=None)
    assert bad("sw-design", blocks=True, returned_to="unit-verif")            # not earlier
    assert bad("sw-design", blocks=True, returned_to="sys-arch")              # not a stage of this project
    assert bad("sw-design", blocks=False, returned_to="sw-arch")
    assert bad("sw-design", blocks=False, deferred_to="sw-req")               # deferred upwards
    assert not bad("sw-design", blocks=False, deferred_to="sw-integ")
    assert not bad("sys-req", blocks=True)                                    # nothing earlier in the project


def test_gate_fixes_are_batched_and_continue_only_while_issues_fall(tmp_path, monkeypatch):
    # full-V attempt 3 pass 23: 33 missing functions in one call, three times, and none was written
    root = tmp_path / "p"
    root.mkdir()
    setup(root, {"author": {"items": SYS_ITEMS}}, stages=("sys-req", "sw-design"))
    write(root / "hi/sw-design/design.json", {"items": [], "open_points": []})
    sys.path.insert(0, str(CONDUCT.parent))
    import conduct as cond

    def go(counts):
        c = cond.Conductor(root)
        calls, left = [], iter(counts[1:])
        monkeypatch.setattr(c, "run_role", lambda *a, **k: calls.append((k["round"], len(k["findings"]))))

        def issues(n):
            return [{"gate": "build", "code": "BUILD-UNDEFINED", "target_id": f"f{i}", "message": "x"} for i in range(n)]
        monkeypatch.setattr(c, "det_issues", lambda s: (None, issues(next(left))))
        try:
            c.fix_gates("sw-design", issues(counts[0]), "authoring")
        except cond.Blocked as exc:
            return calls, str(exc)
        return calls, None
    limit = cond.Conductor(root).limit
    assert go([23, 0]) == ([(1, 10), (1, 10), (1, 3)], None)
    calls, err = go([9, 8, 7, 6, 5, 4, 0])          # falling: allowed past the limit
    assert err is None and len(calls) == 6 > limit
    calls, err = go([9] * 20)                       # not falling: stops at the limit
    assert "rework limit" in err and len(calls) == limit


def test_many_changed_code_items_are_updated_in_batches(tmp_path, monkeypatch):
    root = tmp_path / "p"
    root.mkdir()
    setup(root, {"author": {"items": SYS_ITEMS}}, stages=("sys-req", "sw-design"))
    for stage in ("sw-design", "sys-req"):
        write(root / f"hi/{stage}" / ("design.json" if stage == "sw-design" else "requirements.json"),
              {"items": [], "open_points": []})
    sys.path.insert(0, str(CONDUCT.parent))
    import conduct as cond
    c = cond.Conductor(root)
    calls = []
    monkeypatch.setattr(c, "run_role", lambda r, s, p, **k: calls.append((k["changed_inputs"], k["suspect"])))
    monkeypatch.setattr(c, "det_issues", lambda s: (None, []))
    kw = {"changed_inputs": ["a.md"], "suspect": list("ABCDE"), "open_points": ["OP-1"], "returned": []}
    c.author_with_gates("sw-design", "update", **kw)
    assert calls == [(["a.md"], []), ([], list("ABC")), ([], list("DE"))]
    calls.clear()
    c.author_with_gates("sys-req", "update", **kw)     # text stages are updated in one call as before
    assert calls == [(["a.md"], list("ABCDE"))]


def test_set_rework_makes_every_statement_of_a_rule_agree(tmp_path):
    # full-V attempt 3 pass 24: "changing as little as possible" fixed one statement of a limit per set round and left
    # its copies in other items contradicting it, until the rework limit
    root = tmp_path / "p"
    root.mkdir()
    set_f = dict(F("SQ-05"), target_id="SYS-SUP-001")
    sc = setup(root, {"author": {"items": SYS_ITEMS}, "inspector": {"item_rounds": [{}], "set_rounds": [[set_f], []]}},
               raw=True)
    conduct(root, sc, "--stage", "sys-req")
    prompts = [e for p in (root / ".hi/runs").rglob("events.jsonl") for e in map(json.loads, p.read_text().splitlines())
               if e.get("step") == "role" and "prompt" in e]
    reworks = [e["prompt"] for e in prompts if e["phase"] == "rework-set"]
    assert reworks and all("every other statement" in t and "as little as possible" not in t for t in reworks)
    assert all("every other statement" not in e["prompt"] for e in prompts if e["role"] == "inspector")


@pytest.mark.parametrize("text,limit", [("You've hit your 5-hour limit, resets 7:30pm SECRETWORD", True),
                                        ("segmentation fault SECRETWORD", False)])
def test_usage_limit_on_stdout_is_named_without_recording_the_output(tmp_path, text, limit):
    # full-V attempt 3 pass 25: the limit message is on stdout, the event held an empty stderr_tail
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {})
    proj = json.loads((root / ".hi/project.json").read_text())
    proj["roles"]["author"]["command"] = [sys.executable, "-c", f"import sys; print({text!r}); sys.exit(1)"]
    write(root / ".hi/project.json", proj)
    code, out, _ = conduct(root, sc, "--stage", "sys-req")
    assert code != 0 and out["stages"][0]["outcome"] == "BLOCKED"
    assert ("usage limit" in out["stages"][0]["reason"]) is limit
    role = [e for e in events(root, out) if e["step"] == "role"][-1]
    assert (role.get("cause") == "usage-limit") is limit
    assert "SECRETWORD" not in json.dumps(events(root, out))


def test_an_update_records_the_inputs_it_was_made_from(tmp_path):
    # full-V attempt 3 passes 25 to 28: after an update the workproduct kept the hash of an earlier input
    root = tmp_path / "p"
    root.mkdir()
    sc = setup(root, {"author": {"items": SYS_ITEMS}, "inspector": {"item_rounds": [{}], "set_rounds": [[]]}})
    assert conduct(root, sc, "--stage", "sys-req")[0] == 0
    proj = json.loads((root / ".hi/project.json").read_text())
    path = proj["inputs"][0]["path"]
    (root / path).write_text((root / path).read_text() + "\nA note that changes the file.\n")
    _, out, calls = conduct(root, sc, "--stage", "sys-req")
    assert "update" in [c["phase"] for c in calls if c["role"] == "author"]
    prov = json.loads((root / "hi/sys-req/requirements.json").read_text())["provenance"]
    assert prov["input_hashes"][path] == hashlib.sha256((root / path).read_bytes()).hexdigest()
    assert prov["run_id"] == out["run_id"] and prov["role"] == "author"


@pytest.mark.skipif(not (shutil.which("gcc")), reason="gcc not installed")
def test_a_returned_test_failure_is_run_again_on_the_changed_code(tmp_path, monkeypatch):
    # full-V attempt 3 pass 33: two measured limits were fixed in the code, but the design stage cannot run anything,
    # so its author asked a person for the run and the inspector kept the findings
    root = tmp_path / "p"
    root.mkdir()
    setup(root, {"author": {"items": SYS_ITEMS}}, stages=("sys-req", "sw-req", "sw-design", "unit-verif", "sw-integ"),
          raw=True)
    write(root / "include/a.h", "int cost(void);\n")
    write(root / "src/a.c", '#include "a.h"\nint cost(void) { return 511; }\n')
    write(root / "hi/sw-integ/host/test_a.c", '#include <stdio.h>\n#include "a.h"\nint main(void) { int c = cost();\n'
          ' printf("measured %d\\nHI-TEST ITC-SUP-001 %s\\n", c, c <= 260 ? "PASS" : "FAIL late");'
          ' return c <= 260 ? 0 : 1; }\n')
    write(root / "hi/sw-integ/results.json", {"kept": True})
    spec = {"items": [{"id": "ITC-SUP-001", "automation": {"kind": "host-unit", "file": "x"}}], "open_points": [
        {"id": "OP-ITC-001", "text": "cost is above its limit.", "blocks": True, "returned_to": "sw-design"}]}
    write(root / "hi/sw-integ/test-spec.json", spec)
    write(root / "hi/sw-design/design.json", {"items": [], "open_points": []})
    sys.path.insert(0, str(CONDUCT.parent))
    import conduct as cond
    c = cond.Conductor(root)
    asked = []
    monkeypatch.setattr(c, "run_role", lambda r, s, p, **k: asked.append((r, p, k.get("retests"))) or {"findings": []})
    monkeypatch.setattr(c, "det_issues", lambda s: (None, []))
    c.author_with_gates("sw-design", "update", changed_inputs=[], suspect=[], open_points=[], returned=[])
    (role, phase, got), = asked
    assert (role, phase, got[0]["stage"], got[0]["verdict"]) == ("author", "update", "sw-integ", "FAIL")
    assert got[0]["issues"][0]["code"] == "VT-FAIL"
    write(root / "src/a.c", '#include "a.h"\nint cost(void) { return 232; }\n')
    asked.clear()
    c.inspect("sw-design", "set", 1, [], [])
    (role, phase, got), = asked
    assert (role, phase, got[0]["verdict"]) == ("inspector", "set", "PASS")
    assert "measured 232" in (root / got[0]["logs"][0]).read_text()
    # the later stage's own evidence is untouched, and an unchanged code base is not run twice
    assert json.loads((root / "hi/sw-integ/results.json").read_text()) == {"kept": True}
    assert not (root / "hi/sw-integ/gates").exists()
    monkeypatch.setattr(cond.code_gates, "verification", lambda *a, **k: pytest.fail("run again without a change"))
    assert c.retests("sw-design")[0]["verdict"] == "PASS"
    assert c.retests("sys-req") == []                                  # a text stage has no code to run
    # author and inspector are told what the run is evidence for
    for role, phase in (("author", "update"), ("inspector", "set")):
        text = c.prompt(c.task(role, "sw-design", phase, retests=c.retests("sw-design")))
        assert "and for nothing else" in text and "retests" in text
    spec["open_points"] = []
    write(root / "hi/sw-integ/test-spec.json", spec)
    assert c.retests("sw-design") == []                                # nothing returned, nothing run


def answer_project(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    op = [{"id": "OP-SWR-001", "text": "Who performs the analysis?", "blocks": True, "returned_to": None},
          {"id": "OP-SWR-002", "text": "SYS-SUP-002 is wrong.", "blocks": True, "returned_to": "sys-req"}]
    sc = setup(root, clean_scenario(by_stage={
        "sys-req": {}, "sw-req": {"items": SWR_ITEMS, "open_points": op[:1], "update": {"open_points": []}}}),
        stages=("sys-req", "sw-req"))
    return root, sc, op


def test_an_answer_to_a_stage_reaches_that_stage_only(tmp_path):
    # full-V attempt 3 pass 34: "who performs the analyses?" could only be answered in the inputs, which makes every
    # earlier stage be judged again
    root, sc, _ = answer_project(tmp_path)
    code, out, calls = conduct(root, sc, "--stage", "sys-req", "--until", "sw-req")
    assert [s["outcome"] for s in out["stages"]] == ["ACCEPTED", "BLOCKED"], out
    n = len(calls)
    code, out, calls = conduct(root, sc, "--stage", "sys-req", "--until", "sw-req")
    assert code == 1 and not [c for c in calls[n:] if c["phase"] == "update"]        # nothing answered: no update
    n = len(calls)
    sys.path.insert(0, str(CONDUCT.parent))
    import conduct as cond
    cond.answers.add(root, "sw-req", "OP-SWR-001", by="product owner", text="Nobody; it stays a gap.")
    code, out, calls = conduct(root, sc, "--stage", "sys-req", "--until", "sw-req")
    assert code == 0, out
    assert out["stages"][0]["kept"] and {c["stage"] for c in calls[n:]} == {"sw-req"}
    upd, = [c for c in calls[n:] if c["phase"] == "update"]
    assert upd["answers"] == [{"open_point": "OP-SWR-001", "answer": "Nobody; it stays a gap.",
                               "answered_by": "product owner"}]
    judged = [c for c in calls[n:] if c["role"] == "inspector" and c["phase"] == "set"]
    assert judged and judged[0]["answers"][0]["question"] == "Who performs the analysis?"
    assert cond.answers.current(root, "sw-req") == []                                # the point is gone


def test_an_answer_holds_only_for_the_question_it_was_given_to(tmp_path):
    root, sc, op = answer_project(tmp_path)
    sys.path.insert(0, str(CONDUCT.parent))
    import conduct as cond
    spec = {"items": SWR_ITEMS, "open_points": op}
    write(root / "hi/sw-req/requirements.json", spec)
    for bad in (("sw-req", "OP-SWR-009"), ("sw-req", "OP-SWR-002"), ("sys-qual", "OP-SWR-001")):
        with pytest.raises(ValueError):                         # unknown point; another stage's to settle; no such stage
            cond.answers.add(root, *bad, by="me", text="x")
    with pytest.raises(ValueError):
        cond.answers.add(root, "sw-req", "OP-SWR-001", by=" ", text="x")
    r = subprocess.run([sys.executable, str(SKILLS / "hi-gates/scripts/hi.py"), "answer", "sw-req", "OP-SWR-001", "--by", "me", "--text", "a"],
                       cwd=root, capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "DONE", r.stdout + r.stderr
    assert [a["answer"] for a in cond.answers.current(root, "sw-req")] == ["a"]
    cond.answers.add(root, "sw-req", "OP-SWR-001", by="me", text="b")                # a later answer replaces it
    assert [a["answer"] for a in cond.answers.current(root, "sw-req")] == ["b"]
    op[0]["text"] = "Who performs both analyses?"
    write(root / "hi/sw-req/requirements.json", spec)
    assert cond.answers.current(root, "sw-req") == []
    from forge_hi import seal
    assert Path(".hi/answers.json") in seal.package_files(root, cond.load_project(root))
    text = cond.Conductor(root).prompt(cond.Conductor(root).task("author", "sw-req", "update", answers=[{"answer": "b"}]))
    assert "turns NOT_RUN into a result" in text
