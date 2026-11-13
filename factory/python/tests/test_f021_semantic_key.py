"""Feature 021 FR-004 (T003): the semantic key of a packet is run-identity-free - two runs (work orders) asking the
same thing with the same inputs share it, while their input_hash differs; any content dependency changes it. It is a
pure function of the packet: packets themselves are unchanged (SC-004, register-level byte identity)."""
import copy

from forge_factory.lrtx import structured as S


def _packet(wo="WO-A"):
    p = {"schema": "s", "prompt_version": 3, "phase": "SWE.1", "task": "requirements:g_state", "role": "author",
         "skill": {"path": "s.md", "sha256": "a" * 64}, "model": "m", "instructions": "do it", "criteria": ["c1"],
         "output_schema": {"type": "object"}, "sources": [{"path": "in.md", "sha256": "b" * 64}], "artifacts": [],
         "findings": [], "repair_of": None, "output_reserve": 4096,
         "assessment_scope": {"purpose": "ASPICE_ONLY", "binding_sha256": wo * 8, "instruction": f"order {wo}"},
         "lessons_offered": [f"L-{wo}"], "demonstration_scope": {"wo": wo},
         "accounting": {"serialized_chars": 1}, "input_hash": wo, "_messages": [wo]}
    return p


def test_two_work_orders_share_the_semantic_key():
    a, b = _packet("WO-A"), _packet("WO-B")
    assert S.semantic_key(a) == S.semantic_key(b)
    assert a["assessment_scope"] != b["assessment_scope"]  # the run context differs (and so does input_hash)


def test_every_content_dependency_changes_the_key():
    base = S.semantic_key(_packet())
    for path, value in ((("sources", 0, "sha256"), "c" * 64), (("skill", "sha256"), "d" * 64), (("model",), "m2"),
                        (("criteria",), ["c2"]), (("instructions",), "other"), (("findings",), ["f"]),
                        (("output_schema",), {"type": "array"})):
        p = copy.deepcopy(_packet())
        tgt = p
        for k in path[:-1]:
            tgt = tgt[k]
        tgt[path[-1]] = value
        assert S.semantic_key(p) != base, path


def test_the_key_does_not_change_the_packet():
    p = _packet()
    before = copy.deepcopy(p)
    S.semantic_key(p)
    assert p == before and "semantic_key" not in p
