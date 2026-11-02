"""Feature 016 OB-T003: the onboarding package and approval contracts validate their examples and reject the
invalid shapes the data model forbids."""
import copy
import json

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from forge_factory.common import REPO_ROOT

C = REPO_ROOT / "specs/016-peripheral-onboarding/contracts"


@pytest.mark.parametrize("name", ["onboarding-package", "onboarding-approval"])
def test_examples_validate(name):
    schema = json.loads((C / f"{name}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    errs = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
        json.loads((C / f"{name}.example.json").read_text())))
    assert errs == []


def _bad(mutate):
    schema = json.loads((C / "onboarding-package.schema.json").read_text())
    ex = copy.deepcopy(json.loads((C / "onboarding-package.example.json").read_text()))
    mutate(ex)
    return list(Draft202012Validator(schema).iter_errors(ex))


def _fact(ex, name):
    return next(f for f in ex["facts"] if f["name"] == name)


def test_invalid_packages_are_rejected():
    assert _bad(lambda e: _fact(e, "instance").update(sources=[]))                      # DERIVED without a source
    assert _bad(lambda e: _fact(e, "mm_page").update(value="p.180"))                    # NOT_DERIVED with a value
    assert _bad(lambda e: (_fact(e, "base_address").update(status="CONFLICT")))          # CONFLICT without question
    assert _bad(lambda e: e["authored"][0].update(attempts=4))                          # more than 3 attempts


def test_rejected_approval_needs_a_reason():
    schema = json.loads((C / "onboarding-approval.schema.json").read_text())
    ex = json.loads((C / "onboarding-approval.example.json").read_text())
    ex["decision"] = "REJECTED"
    assert list(Draft202012Validator(schema).iter_errors(ex))
    ex["reason"] = "base address conflict unresolved"
    assert not list(Draft202012Validator(schema).iter_errors(ex))
