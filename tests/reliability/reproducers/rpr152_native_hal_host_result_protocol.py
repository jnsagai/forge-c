"""Native GoogleTest HAL on a provided CMSIS LL must publish its host stdout protocol.

The real CRC L34 emitted descriptive CHECK lines and unrelated IT ids. This reproducer isolates only the missing
format contract with valid IT ids; it does not attribute the author's wrong ids or functional errors to the factory.
No model, production workspace, source requirement or validator is changed.
"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

SIG = "native HAL SWE5 omits the host result-line protocol required by the strict trace parser"


def main():
    from forge_factory.acp import _split_attrs, statements
    from forge_factory.inspection.swtrace import check_results
    from forge_factory.workflow.builder import build

    with tempfile.TemporaryDirectory(prefix="rpr152-") as td:
        root = Path(td)
        raw = root / "checks.log"
        raw.write_text("IT-001-NOMINAL PASS\nIT-001-CORNER FAIL\nIT-002 PASS\n")
        if check_results([raw]) != {"IT-001": "FAIL", "IT-002": "PASS"}:
            raise RuntimeError("STRICT_PARSER_OR_FAILURE_DOMINANCE_CHANGED")
        # Correctly named ids alone cannot satisfy the existing observer when the format is unspecified.
        raw.write_text("CHECK IT-001 nominal => PASS\nIT-101 PASS\n")
        if check_results([raw]) != {"IT-101": "PASS"}:
            raise RuntimeError("PARSER_WIDENED_OR_WRONG_ID_INVENTED")
        missing = []
        for peripheral in ("crc", "wwdg"):
            inst = peripheral.upper()
            fn = f"LL_{inst}_ReadData32" if peripheral == "crc" else f"LL_{inst}_IsEnabled"
            api = {"instance": inst, "functions": [fn], "calls": {fn: f"{fn}({inst})"},
                   "signatures": {fn: f"uint32_t {fn}(const {inst}_TypeDef *instance)"}}
            graph, _ = build("WO-RPR152", layer="HAL", peripheral=peripheral, trace=True, uspec_gtest=True,
                             provided_api=api)
            attrs = next(a for _, _, _, name, a in statements(graph) if name == "swe5_author")
            quoted = next(a.partition("=")[2] for a in _split_attrs(attrs) if a.startswith("prompt="))
            prompt = json.loads(quoted)
            if "OWNER TRACE RULES" not in prompt or f"software/tests/integration/test_{peripheral}_integration.c" not in prompt:
                raise RuntimeError("ACTUAL_NATIVE_HAL_TRACE_SCENARIO_NOT_REACHED")
            statement = re.search(r'printf\("%s %s\\n", id, ok \? "PASS" : "FAIL"\);', prompt)
            if not statement:
                missing.append(peripheral)
                continue
            # Compile and execute the published statement, rather than treating a matching sentence as proof.
            src = root / f"{peripheral}.c"
            src.write_text('#include <stdio.h>\nstatic void result(const char *id, int ok) { ' + statement[0] +
                           ' }\nint main(void) { result("IT-001-NOMINAL", 1); result("IT-001-INVALID", 0); '
                           'result("IT-002", 1); return 0; }\n')
            exe = root / peripheral
            subprocess.run(["gcc", "-std=c11", "-Wall", "-Werror", str(src), "-o", str(exe)],
                           check=True, capture_output=True, timeout=30)
            raw.write_bytes(subprocess.run([str(exe)], check=True, capture_output=True, timeout=5).stdout)
            if check_results([raw]) != {"IT-001": "FAIL", "IT-002": "PASS"}:
                raise RuntimeError("PUBLISHED_HOST_PROTOCOL_NOT_OBSERVED")
    if missing:
        print("SYMPTOM_PRESENT:" + SIG)
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("REPRODUCER_ERROR:" + type(exc).__name__ + ":" + str(exc)[:160])
        sys.exit(2)
