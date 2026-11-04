"""The native HAL author must receive the stdout protocol that matrix5 actually observes."""
import json
import re
import shutil
import subprocess

import pytest
from forge_factory.acp import _split_attrs, statements
from forge_factory.inspection.swtrace import check_results
from forge_factory.workflow.builder import build


def author_prompt(peripheral="crc", *, layer="HAL", trace=True, gtest=True):
    graph, _ = build("WO-C152", layer=layer, peripheral=peripheral, trace=trace, uspec_gtest=gtest)
    attrs = next(a for _, _, _, name, a in statements(graph) if name == "swe5_author")
    quoted = next(a.partition("=")[2] for a in _split_attrs(attrs) if a.startswith("prompt="))
    return json.loads(quoted)


@pytest.mark.parametrize("peripheral", ["crc", "wwdg", "iwdg"])
def test_native_hal_publishes_output_and_existing_test_identity_contract(peripheral):
    prompt = author_prompt(peripheral)
    assert "HOST RESULT PROTOCOL" in prompt
    assert "IT-001-NOMINAL PASS" in prompt and "IT-001-INVALID FAIL" in prompt
    assert "IT-101 does not verify IT-001" in prompt
    assert "evaluates condition once" in prompt and "main returns nonzero for any failure" in prompt
    assert "Preserve every functional predicate and assertion" in prompt
    assert "forge_target_test.h and TCHECK belong to the Renode target tests" in prompt
    assert f"software/tests/unit/test_{peripheral}.cpp" in prompt


@pytest.mark.skipif(not shutil.which("gcc"), reason="gcc unavailable")
def test_published_printf_executes_both_results_and_strict_parser_keeps_failure_dominance(tmp_path):
    prompt = author_prompt()
    statement = re.search(r'printf\("%s %s\\n", id, ok \? "PASS" : "FAIL"\);', prompt)
    assert statement, "Native author did not receive the executable result protocol"
    src = tmp_path / "protocol.c"
    src.write_text('#include <stdio.h>\nstatic void result(const char *id, int ok) { ' + statement[0] +
                   ' }\nint main(void) { result("IT-001-NOMINAL", 1); result("IT-001-INVALID", 0); '
                   'result("IT-002-NOMINAL", 1); return 0; }\n')
    exe = tmp_path / "protocol"
    subprocess.run(["gcc", "-std=c11", "-Wall", "-Werror", str(src), "-o", str(exe)], check=True, capture_output=True)
    raw = tmp_path / "result.log"
    raw.write_bytes(subprocess.run([str(exe)], check=True, capture_output=True).stdout)
    assert check_results([raw]) == {"IT-001": "FAIL", "IT-002": "PASS"}
    raw.write_text("CHECK IT-001 result => PASS\nIT-101 PASS\n")
    assert check_results([raw]) == {"IT-101": "PASS"}  # No prefix widening or invented IT-001 observation.


def test_legacy_ll_and_nontrace_hal_do_not_receive_new_hal_rule():
    assert "HOST RESULT PROTOCOL" not in author_prompt(layer="LL")
    assert "HOST RESULT PROTOCOL" not in author_prompt(trace=False)
