"""Feature 021 US1 (T007): the SWE.1 functional carry on the generic validated-item store. A run's PASS requirements
are published to the store when its per-requirement inspection ends; a rerun whose named sources are not available on
this machine still finds the earlier run that validated the same inputs (same governance inventory) through the
store; a different inventory finds nothing (INPUT_CHANGED stays the rule). Scripted answers only."""
import json

from f020_fixtures import ser_spec
from f020_swe1 import prepared
from test_f020_carry import SRC, pair  # noqa: F401 - the two-run fixture (source passed IQ, rerun prepared)


def test_the_inspection_publishes_its_pass_requirements(pair):  # noqa: F811
    from forge_factory.governance import inventory as GI
    from forge_factory.lrtx import carry_store as CS
    from forge_factory.lrtx import swe1_quality as Q
    from forge_factory.common import sha256_file

    src, _dst = pair
    passed = {k: v for k, v in Q.verdicts(src).items() if v.get("passed") is True}
    store, dep = CS.Store(), sha256_file(src / GI.OUT)
    assert passed and store.orders_for("SWE.1", dep) == [SRC]
    tk, sha = next(iter(passed))
    hit = store.find("SWE.1", tk, dep_sha=dep)
    assert hit["source_order"] == SRC and hit["verdicts"]["IQ"] == "PASS"


def test_a_rerun_whose_named_source_is_gone_finds_the_validated_run_in_the_store(tmp_path, monkeypatch, pair):  # noqa: F811
    from forge_factory.lrtx import swe1_carry as C

    src, _dst = pair
    spec = ser_spec()
    spec["swe1"] = {"level": "functional", "template": "swe1-functional-v2", "carry_from": ["WO-F020-GONE"]}
    other = prepared(tmp_path, monkeypatch, spec=spec, wo="WO-F021-ONLY-GONE")
    p, meta = C.source(other)
    assert p == src and meta["source_work_order"] == SRC and meta["via"] == "validated-item store"


def test_another_inventory_finds_nothing_in_the_store(tmp_path, monkeypatch, pair):  # noqa: F811
    from forge_factory.governance import inventory as GI
    from forge_factory.lrtx import swe1_carry as C

    spec = ser_spec()
    spec["swe1"] = {"level": "functional", "template": "swe1-functional-v2", "carry_from": ["WO-F020-GONE"]}
    other = prepared(tmp_path, monkeypatch, spec=spec, wo="WO-F021-OTHER-INPUTS")
    inv = json.loads((other / GI.OUT).read_text())
    inv["module"] = inv["module"] + "-changed"
    (other / GI.OUT).write_text(json.dumps(inv))
    p, meta = C.source(other)
    assert p is None and "WO-F020-GONE:NOT_AVAILABLE" in meta["reason"]
