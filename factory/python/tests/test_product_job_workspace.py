"""A product job must bind the real work-order workspace, not the attempt's pending placeholder.

The private launch rehearsal found every durable product refusing at native admission with
SOURCE_WORKSPACE_MISMATCH, because attempts only become `workorder:<name>` after launch.
"""
from pathlib import Path

import pytest
from forge_factory.afo import product_job as P
from forge_factory.afo.durable import Refused
from forge_factory.common import state_dir


def attempt(ref):
    return {"attempt_id": "afo-1-a1", "record": {"workspace_ref": ref}}


def test_pending_attempt_uses_the_named_work_order():
    ws = P.product_workspace(attempt("pending:afo-1-a1"), "WO-F014-SWE6-X-L1")
    assert ws == state_dir() / "workorders/WO-F014-SWE6-X-L1/workspace"


def test_placeholder_never_reaches_a_path():
    assert "pending:" not in str(P.product_workspace(attempt("pending:afo-1-a1"), "WO-F014-SWE6-X-L1"))


def test_launched_attempt_keeps_its_recorded_workspace():
    ws = P.product_workspace(attempt("workorder:WO-F014-SWE6-X-L1"), None)
    assert ws == state_dir() / "workorders/WO-F014-SWE6-X-L1/workspace"


def test_named_work_order_cannot_disagree_with_a_launched_attempt():
    with pytest.raises(Refused, match="PRODUCT_WORKSPACE_REBOUND"):
        P.product_workspace(attempt("workorder:WO-F014-SWE6-X-L1"), "WO-F014-SWE6-X-L2")


@pytest.mark.parametrize("name", ["", "../escape", "a/b", ".", ".."])
def test_unsafe_work_order_name_refuses_before_a_path_exists(name):
    with pytest.raises(Refused, match="PRODUCT_WORKSPACE_NAME_INVALID"):
        P.product_workspace(attempt("pending:afo-1-a1"), name)


def test_pending_attempt_without_a_name_refuses_instead_of_binding_the_placeholder():
    with pytest.raises(Refused, match="PRODUCT_WORKSPACE_NAME_REQUIRED"):
        P.product_workspace(attempt("pending:afo-1-a1"), None)


def test_dispatch_passes_the_launch_name():
    source = (Path(P.__file__).parent / "dispatch.py").read_text()
    assert "work_order=name)" in source
