"""CAPA-104 (run WO-F014-SWE1-CRCK-20261101-L9): a brownfield graph scoped to SWE.1 holds the delivery_inject node after
the SWE.1 inspection gate, so a later phase can resume the order (the injection record exists)."""
from forge_factory.workflow.builder import build
from test_builder_stop_after import edges, reachable


def test_a_brownfield_swe1_scoped_graph_injects_the_delivery_before_it_ends():
    dot, _nodes = build("WO-X", layer="LL", trace=True, peripheral="crc", brownfield="FROZEN", stop_after="SWE.1")
    e = edges(dot)
    assert ("swe1_inspect_gate", "delivery_inject", "outcome=succeeded") in e
    assert ("delivery_inject", "release_manager", "outcome=succeeded") in e and ("delivery_inject", "finalize", "") in e
    assert "delivery_inject" in reachable(dot) and "swe2_author" not in dot
    green, _n = build("WO-X", layer="LL", trace=True, peripheral="crc", stop_after="SWE.1")
    assert "delivery_inject" not in green  # greenfield graphs are unchanged
    full, _n = build("WO-X", layer="LL", trace=True, peripheral="crc", brownfield="FROZEN", stop_after="SWE.2")
    assert sum(1 for a, b, _c in edges(full) if b == "delivery_inject") == 1  # still once, before SWE.2
