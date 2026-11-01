"""CAPA-090 (runs WO-F014-SWE3-IWDG-20261101-01, -OBL-01): a resume carries the validated structured checkpoints of the
passed phases (SWE.3 reads the SWE.2 interface task, SWE.6 the SWE.1 requirement map); the source's run state does not."""
from __future__ import annotations

import json

from forge_factory.workorder import carry_checkpoints


def test_only_validated_checkpoints_of_the_carried_phases_are_copied(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    for ph, files in {"SWE.1": {"assembly.json": "{}", "inventory.json": "{}", "visit-state.json": '{"open": true}',
                                "development-execution.json": "{}"},
                      "SWE.2": {"visits.jsonl": ""}, "SWE.3": {"assembly.json": "{}"}}.items():
        d = src / ".forge-run/lrtx" / ph
        d.mkdir(parents=True)
        for n, t in files.items():
            (d / n).write_text(t)
    pk = src / ".forge-run/lrtx/SWE.2/packets"
    pk.mkdir(parents=True)
    (pk / "interfaces.json").write_text(json.dumps({"task": "interfaces", "status": "VALID"}))
    (pk / "design.json").write_text(json.dumps({"task": "design", "status": "INVALID"}))
    copied = carry_checkpoints(src, dst, ["SWE.1", "SWE.2"])
    assert sorted(copied) == ["SWE.1/assembly.json", "SWE.1/inventory.json", "SWE.2/packets/interfaces.json"]
    assert not (dst / ".forge-run/lrtx/SWE.1/visit-state.json").exists()  # run state and budgets stay behind
    assert not (dst / ".forge-run/lrtx/SWE.1/development-execution.json").exists()
    assert not (dst / ".forge-run/lrtx/SWE.2/packets/design.json").exists()  # an invalid answer is never carried
    assert not (dst / ".forge-run/lrtx/SWE.3").exists()  # a phase not carried keeps nothing
