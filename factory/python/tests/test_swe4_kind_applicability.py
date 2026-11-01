"""CAPA-101 (run WO-F014-SWE4-IWDG-20261101-L4, SWE4-02): a test kind without a test is stated NOT COVERED or not
applicable with a deterministic reason, never only 'none declared'."""
from forge_factory.lrtx import swe4


def _c(stmt, returns="void", params=()):
    return {"swr": "SWR-001", "statement": stmt, "unit": {"id": "SWU-LL-01", "function": {
        "name": "LL_X_Enable", "returns": returns, "params": [{"name": "v", "type": t} for t in params]}}}


def test_error_and_boundary_are_not_applicable_only_with_their_reason():
    uc = [_c("The driver shall write 0xCCCC to IWDG_KR.KEY.")]
    assert swe4._kind_gap("error", uc).startswith("error: not applicable - no requirement of this unit (SWR-001)")
    assert swe4._kind_gap("boundary", uc) == "boundary: not applicable - LL_X_Enable takes no value"
    assert swe4._kind_gap("negative", uc) == "negative: NOT COVERED"
    assert swe4._kind_gap("error", [_c("The driver shall return HAL_TIMEOUT when the flag stays clear.")]) == \
        "error: NOT COVERED"
    assert swe4._kind_gap("error", [_c("Reads the flag.", returns="ErrorStatus")]) == "error: NOT COVERED"
    assert swe4._kind_gap("boundary", [_c("Sets the field.", params=("uint32_t",))]) == "boundary: NOT COVERED"
