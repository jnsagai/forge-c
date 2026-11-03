"""CAPA-126 (run WO-F014-SWE2-CRCHAL-20261103-L26): the SWE.1/SWE.2/SWE.3 HAL prompts of a no-wait HAL (CRC) carry
no RCC timeout requirement, polling-iteration example or TIMEOUT_VALUE define; they use the profile's own
hal_failure_responses and hal_wait_rule. Waiting HALs (IWDG, RCC and every profile without own HAL texts) render
exactly the prompts they rendered before."""
import re

import pytest
from forge_factory import layer
from forge_factory.peripheral import DIR
from forge_factory.workflow import builder


def _dot(pid, lyr="HAL"):
    return builder.build("WO-CAPA-126", chunk_lines=150, layer=lyr, trace=True, isolation=True, peripheral=pid)[0]


def _prompt(dot, node):
    return re.search(rf'  {node} \[.*?prompt="((?:\\.|[^"\\])*)"', dot, re.S).group(1)


@pytest.mark.parametrize("lyr", ["HAL", "LL+HAL"])
def test_no_wait_hal_prompts_have_no_timeout_bound(lyr):
    dot = _dot("crc", lyr)
    s1, s2, s3 = (_prompt(dot, n) for n in ("swe1_author", "swe2_author", "swe3_hal_author"))
    for p in (s1, s2, s3):
        assert "TIMEOUT_VALUE" not in p and "polling iterations" not in p
    assert "returns without waiting on a CRC flag" in s1  # the profile's own timing requirement
    assert "No HAL_CRC_ function waits" in s3  # the profile's hal_wait_rule
    assert "Error handling and timing" in s2 and "Timeouts and error handling" not in s2


@pytest.mark.parametrize("pid", sorted(p.stem for p in DIR.glob("*.yaml") if p.stem != "crc") + [None])
@pytest.mark.parametrize("lyr", ["HAL", "LL+HAL", "LL"])
def test_waiting_hal_prompts_unchanged(monkeypatch, pid, lyr):
    dot = _dot(pid, lyr)
    monkeypatch.setattr(layer, "hal_waits_of", lambda p: True)  # the pre-CAPA-126 prompt for every profile
    assert _dot(pid, lyr) == dot


def test_the_crc_prompt_differs_only_by_the_no_wait_branch(monkeypatch):
    fixed = _prompt(_dot("crc"), "swe1_author")
    monkeypatch.setattr(layer, "hal_waits_of", lambda p: True)
    old = _prompt(_dot("crc"), "swe1_author")
    assert "every wait is bounded by HAL_CRC_TIMEOUT_VALUE = 1000 polling iterations" in old
    assert "polling iterations" not in fixed
    iwdg = _prompt(_dot("iwdg"), "swe1_author")
    assert "update timeout" in iwdg and "HAL_TIMEOUT" in iwdg  # a waiting HAL keeps its timeout requirement
