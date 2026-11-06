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
