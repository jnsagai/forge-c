"""Feature 018 on the owner lane: the two-phase SWE.1 graph passes the durable line-product model-node check.

WO-F014-SWE1-WWDGL-20261109-L44 (and every order on 26f0bd8c) was refused before launch with
LINE_PRODUCT_UNDECLARED_MODEL_NODE: the phase-1 nodes call models but had no role binding.
"""
import json

from forge_factory.afo import line_product_context as C
from forge_factory.lrtx import profile as P
from forge_factory.workflow.builder import binding_for, build

PROFILE = "local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104"


def test_the_two_phase_graph_declares_a_role_for_every_model_node(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path / "lrtx"))
    prof = P.load(PROFILE)
    rm = prof["structured"]["role_models"]
    st = {"phases": ["SWE.1"], "inspect_phases": ["SWE.1"], "model": rm["author"], "author_model": rm["author"],
          "inspector_model": rm["inspector"], "visit_time_s": 240, "two_phase_inspection": True}
    g, nodes = build("WO-X", layer="LL", trace=True, peripheral="iwdg", structured=st)
    assert nodes["swe1_iq_inspect"]["role"] == "swe1-inspector" and nodes["swe1_iq_rework"]["role"] == "swe1-author"
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/workflow.fabro").write_text(g)
    binding_for("WO-X", str(ws.resolve()), nodes).dump(ws / ".forge-run/binding.json")
    (ws / ".forge-run/model-profile.json").write_text(json.dumps({"default": rm["author"]}))
    job = {"model": rm["author"], "job_id": "afo-product-x", "nonce": "n", "factory_revision": {"commit": "a" * 40}}
    ref = C.capture(ws, job, prof, phase="SWE.1")  # refused LINE_PRODUCT_UNDECLARED_MODEL_NODE before the fix
    ctx = json.loads(open(ref["path"]).read())
    assert {ctx["nodes"][n]["role"] for n in ("swe1_iq_inspect", "swe1_iq_inspect_more")} == {"swe1-inspector"}
    assert {ctx["nodes"][n]["role"] for n in ("swe1_iq_rework", "swe1_iq_rework_more")} == {"swe1-author"}
    assert ctx["role_models"]["swe1-inspector"] == [rm["inspector"]]
    assert ctx["role_models"]["swe1-author"] == [rm["author"]]
