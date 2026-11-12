"""Workflow prompts carry real line breaks. Found by the private launch rehearsal at native binding."""
import pytest
from forge_factory.afo.durable import Refused
from forge_factory.afo.line_product_context import _attrs


def test_multiline_prompt_attribute_parses():
    assert _attrs('prompt="first\nsecond\ttab", backend=native') == {"prompt": "first\nsecond\ttab", "backend": "native"}


def test_json_escapes_still_decode():
    assert _attrs(r'prompt="say \"hi\"\nbye"') == {"prompt": 'say "hi"\nbye'}


def test_duplicate_attribute_still_refuses():
    with pytest.raises(Refused, match="LINE_PRODUCT_GRAPH_ATTRIBUTE_INVALID"):
        _attrs('prompt="a", prompt="b"')


def test_unterminated_value_still_fails_rather_than_parsing_partially():
    with pytest.raises(ValueError):
        _attrs('prompt="unterminated')


# A resumed single-phase order: the graph holds every phase, the owner's trial only the bound one.
ROLES = ("swe1-author", "swe5-inspector", "swe6-author", "swe6-inspector", "release-manager", "afo-recovery-planner")


def test_phase_scope_keeps_the_bound_phase_and_unphased_roles():
    from forge_factory.afo.line_product_context import role_in_phase

    kept = [role for role in ROLES if role_in_phase(role, "SWE.6")]
    assert kept == ["swe6-author", "swe6-inspector", "release-manager", "afo-recovery-planner"]


def test_no_bound_phase_keeps_every_role_for_existing_callers():
    from forge_factory.afo.line_product_context import role_in_phase

    assert all(role_in_phase(role, None) for role in ROLES)


@pytest.mark.parametrize("phase", ["SWE6", "swe.6", "SWE.", "", 6])
def test_malformed_phase_refuses(phase):
    from forge_factory.afo.line_product_context import role_in_phase

    with pytest.raises(Refused, match="LINE_PRODUCT_PHASE_SCOPE_INVALID"):
        role_in_phase("swe6-author", phase)


def test_out_of_phase_role_cannot_obtain_a_model_at_request_time(monkeypatch):
    """Scoping tightens the runtime: a request for an excluded role refuses even if a path reached it."""
    from forge_factory.afo import line_product_context as C

    frozen = {"role_models": {"swe6-author": ["m"]}}
    monkeypatch.setattr(C, "resolve", lambda job: (frozen, {"models": {"allowed": {"m": {"digest": "d", "quantization": "q"}}}}))
    with pytest.raises(Refused, match="LINE_PRODUCT_REQUEST_MODEL_OR_ROLE_UNDECLARED"):
        C.request_job({"model": "m"}, "swe1-author", "m", None)
    assert C.request_job({"model": "m", "role_capabilities": {"swe6-author": {"identity": {"model_digest": "d"}}}},
                         "swe6-author", "m", None)["model_digest"] == "d"
