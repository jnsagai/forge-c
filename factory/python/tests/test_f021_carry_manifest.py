"""Feature 021 US2 (T010): every carried item is listed in a carry manifest with its provenance, labelled CARRIED
(never a direct result of this run); a reworked item is not listed; the manifest goes into the package staging area
without changing the package status. Scripted answers only."""
import json

from test_f020_carry import SRC, _author_dst, pair  # noqa: F401 - the two-run fixture
from forge_factory.lrtx import structured as S
import test_f020_two_phase as two


def _rerun(dst, monkeypatch):
    from forge_factory.lrtx import swe1_quality as Q

    rep, _ = _author_dst(dst, monkeypatch)
    assert rep["status"] == "PASS", rep
    monkeypatch.setattr(S, "call", two.judge({}, []))
    assert Q.iq_inspect(dst, "fake-model:q8")["status"] == "PASS"


def test_every_carried_item_is_listed_with_provenance(pair, monkeypatch):  # noqa: F811
    from forge_factory.lrtx import carry_manifest as CM

    _src, dst = pair
    _rerun(dst, monkeypatch)
    doc = CM.build(dst)
    items = doc["items"]
    kinds = {i["kind"] for i in items}
    assert kinds >= {"author_requirement", "iq_verdict", "governance_answer"}, kinds
    assert all(i["label"] == "CARRIED" and i["source_work_order"] == SRC for i in items)
    keys = {i["item"] for i in items if i["kind"] == "author_requirement"}
    assert "requirements:g_blocking_transfer|receive_blocking" in keys  # restored (kept) despite the answer
    assert "requirements:g_blocking_transfer|transmit_blocking" not in keys  # reworked: a direct result
    assert all(len(i["content_sha256"]) == 64 for i in items if i["kind"] != "governance_answer")
    assert doc["counts"]["total"] == len(items)


def test_the_manifest_goes_into_the_package_staging(pair, monkeypatch, tmp_path):  # noqa: F811
    from forge_factory.lrtx import carry_manifest as CM

    _src, dst = pair
    _rerun(dst, monkeypatch)
    stage = tmp_path / "stage"
    stage.mkdir()
    n = CM.bundle_into(dst, stage, "BLOCKED")
    doc = json.loads((stage / CM.STAGE_PATH).read_text())
    assert n == doc["counts"]["total"] > 0 and doc["package_status_at_bundle"] == "BLOCKED"


def test_a_run_without_carry_has_no_manifest(pair, tmp_path):  # noqa: F811
    from forge_factory.lrtx import carry_manifest as CM

    src, _dst = pair
    stage = tmp_path / "stage"
    stage.mkdir()
    assert CM.build(src)["items"] == [] and CM.bundle_into(src, stage, "BLOCKED") == 0
    assert not (stage / CM.STAGE_PATH).exists()
