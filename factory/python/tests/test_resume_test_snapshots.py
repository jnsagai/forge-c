"""CAPA-105: a greenfield resume carries the content-addressed test snapshots of its source and of the source's own
resume ancestors, so a resumed lineage's package has a complete test history; only hash-verified files are copied."""
import hashlib
import json

from forge_factory import workorder
from forge_factory.inspection.defects import SNAPSHOTS


def _wo(root, name, parent=None, snaps=()):
    ws = root / "workorders" / name / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    m = {"work_order": name}
    if parent:
        m["resumed_from"] = {"source_work_order": parent}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    for body in snaps:
        d = ws / SNAPSHOTS
        d.mkdir(parents=True, exist_ok=True)
        (d / hashlib.sha256(body).hexdigest()).write_bytes(body)
    return ws


def test_snapshots_of_the_whole_resume_chain_are_carried_and_verified(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    _wo(tmp_path, "WO-A", snaps=[b"swe4 test"])
    b = _wo(tmp_path, "WO-B", parent="WO-A", snaps=[b"swe5 test"])
    (b / SNAPSHOTS / ("0" * 64)).write_bytes(b"tampered")  # content does not hash to its name: never copied
    dst = _wo(tmp_path, "WO-C")
    assert workorder.carry_test_snapshots(b, dst) == 2
    names = sorted(p.name for p in (dst / SNAPSHOTS).iterdir())
    assert names == sorted(hashlib.sha256(x).hexdigest() for x in (b"swe4 test", b"swe5 test"))
    assert workorder.carry_test_snapshots(b, dst) == 0  # nothing overwritten or duplicated
