"""Frozen Omniverse2 verification-model reproducer (no inference or product execution).

Run with PYTHONPATH/FORGE_REPO_ROOT pointing to the clean SDK at
/mnt/data/forge-c/inspector-014-b309039/consumers-466d87b/repo.
Supply --destination /mnt/data/forge-c/inspector-014-b309039/repro-wwdg-<unique-name>.
Requires the preserved candidate002/private engine/vendor inputs. Existing outputs
are never overwritten. Exit2 records an abstract register-image model mismatch;
it is not a hardware-defect or product-readiness verdict. No grants are renewed.
"""

import argparse
import json
import os
import resource
import shutil
import socket
import subprocess
import sys

from pathlib import Path

from forge_factory.assurance import mutation, register_wp
from forge_factory.assurance import safec_oracle as SO
from forge_factory.brownfield import cmsis
from forge_factory.knowledge import experience as E
from forge_factory.knowledge.store import LessonStore
from forge_factory.lrtx import swe1_semantic as S
from forge_factory.safec_bridge import contract as K
from forge_factory.safec_bridge import contracts as C
from forge_factory.safec_bridge import obligations as OB
from forge_factory.safec_bridge import oracle as O

sys.dont_write_bytecode = True

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--destination", type=Path, required=True)
args = parser.parse_args()
Q = Path("/mnt/data/forge-c/inspector-014-b309039")
R = Q / "consumers-466d87b/repo"
N = args.destination.resolve()
assert socket.gethostname() == "omniverse2", "FROZEN_OMNIVERSE2_SCENARIO_ONLY"
assert N.parent == Q and N.name.startswith("repro-wwdg-"), "FRESH_ISOLATED_DESTINATION_REQUIRED"
assert not N.exists(), "REFUSE_EXISTING_DESTINATION"
assert Path(S.__file__).resolve().is_relative_to(R), "IMPORTED_SDK_NOT_FROZEN_SOURCE"
N.mkdir(mode=0o700)
(N / "tmp").mkdir()
os.environ["TMPDIR"] = str(N / "tmp")
os.environ["FORGE_STATE_DIR"] = str(N / "state")
os.environ["FORGE_EVENTS_DIR"] = str(N / "events")
REV = "466d87bef4688af6209937433ef056baa4a5d51f"
assert subprocess.check_output(["git", "-C", str(R), "rev-parse", "HEAD"], text=True).strip() == REV
assert not subprocess.check_output(["git", "-C", str(R), "status", "--porcelain"], text=True).strip()
src = Q / "wwdg-024a3fa/state/workorders/WWDG-LL-v02-002/workspace"
manifest_before = C.sha256_bytes((src / ".forge-run/manifest.json").read_bytes())
assert manifest_before == "b5372d46aa479903e90e7132145dd015ac96a3d2361ec960385cda488cfaa04d", "FROZEN_CANDIDATE_CHANGED"
ws = N / "external-verification-fixture"
assert not ws.exists()
shutil.copytree(src, ws)
manifest = json.loads((ws / ".forge-run/manifest.json").read_bytes())
ctx = S.Context(ws)
intents = []
for n, row in enumerate(manifest["semantic_required_operations"]):
    f = next(
        f
        for r in ctx.domain["registers"]
        if r["register_id"] == row["register"]
        for f in r["fields"]
        if f["field_id"] == row["field"]
    )
    intents.append({**row, "intent_id": f"mandatory-{n}", "source_fact_ids": [f["fact_id"]]})
assert len(intents) == 12
artifacts = {}
for operation in ("validate_intents", "derive_tests", "derive_contracts"):
    out, request, work = ctx.validate(intents, "external-joint-" + operation, operation=operation)
    (N / (operation + "-outcome.json")).write_bytes(C.canonical_bytes(out.record()))
    assert out.admissible and out.status == "PASS", out.record()
    contract = K.materialize(out, request, ctx.domain_raw, work, ctx.pin)
    if operation == "derive_tests":
        artifacts["oracle"] = O.materialize(out, contract, ctx.domain_raw, work)
    if operation == "derive_contracts":
        artifacts["obligations"] = OB.materialize(out, contract, ctx.domain_raw, work)
rec = {
    "schema": "forge-c/lrtx-register-oracle/1",
    "contract_semantic_digest": contract.semantic_digest,
    "domain_sha256": contract.domain_sha256,
    "engine": ctx.pin.expected(),
    "operations": list(contract.operations),
    "case_of_intent": {it["intent_id"]: "external-case-" + str(n) for n, it in enumerate(intents)},
    "oracle": artifacts["oracle"],
}
ob = {
    "schema": "forge-c/lrtx-register-obligations/1",
    "contract_semantic_digest": contract.semantic_digest,
    "domain_sha256": contract.domain_sha256,
    "engine": ctx.pin.expected(),
    "obligations": artifacts["obligations"],
}
for name, value in [(SO.FILE, rec), (register_wp.OBLIGATIONS_FILE, ob)]:
    p = ws / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(C.canonical_bytes(value))
for verify in (SO.verified, register_wp.verified):
    value, issues = verify(ws)
    assert value is not None and not issues, issues
operators = mutation.register_ops(ws)
assert operators
# Compile the fingerprinted ST functions against the existing generated plain-memory host adapter.
copied = []
for row in manifest["delivered"]:
    source = Path(manifest["delivery_intake"]["store"]) / "files" / row["path"]
    raw = source.read_bytes()
    assert C.sha256_bytes(raw) == row["sha256"]
    target = ws / row["path"]
    assert target.resolve().is_relative_to(ws)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    copied.append({"path": row["path"], "sha256": row["sha256"]})
functions = [
    "LL_WWDG_Enable",
    "LL_WWDG_IsEnabled",
    "LL_WWDG_SetCounter",
    "LL_WWDG_GetCounter",
    "LL_WWDG_SetPrescaler",
    "LL_WWDG_GetPrescaler",
    "LL_WWDG_SetWindow",
    "LL_WWDG_GetWindow",
    "LL_WWDG_EnableIT_EWKUP",
    "LL_WWDG_IsEnabledIT_EWKUP",
    "LL_WWDG_ClearFlag_EWKUP",
    "LL_WWDG_IsActiveFlag_EWKUP",
]
assert set(functions) == set(manifest["delivery"]["scope"]["functions"])
cases = artifacts["oracle"]["cases"]
lines = [
    "#include <stdint.h>",
    "#include <stdio.h>",
    "#define FORGE_HOST_DEVICE_IMPLEMENTATION",
    '#include "forge_host_device.h"',
    '#include "stm32n6xx_ll_wwdg.h"',
    "int main(void) { volatile uint32_t *regs=(volatile uint32_t *)&forge_host_wwdg;",
    "uint32_t b[sizeof(WWDG_TypeDef)/4U]; unsigned i;",
]
for n, case in enumerate(cases):
    index = int(case["intent_id"].split("-")[-1])
    it = intents[index]
    word = int(case["offset"], 0) // 4
    args = "&forge_host_wwdg"
    if index in (2, 4, 6):
        args += ", " + it["logical_value"] + "U"
    call = functions[index] + "(" + args + ")"
    lines += [
        "for(i=0;i<sizeof(WWDG_TypeDef)/4U;i++) regs[i]=0xA5A50000U|i;",
        f"regs[{word}U]={case['initial']}U;",
        "for(i=0;i<sizeof(WWDG_TypeDef)/4U;i++) b[i]=regs[i];",
        "{ uint32_t result=0U; unsigned frame=1U;",
        "result=(uint32_t)" + call + ";" if case["expected_return"] is not None else "(void)" + call + ";",
        f"for(i=0;i<sizeof(WWDG_TypeDef)/4U;i++) if(i!={word}U && regs[i]!=b[i]) frame=0U;",
        f'printf("{n} %u %u %u\\n",(unsigned)regs[{word}U],(unsigned)result,frame);',
        "}",
    ]
lines += ["return 0; }"]
program = N / "host-assessment.c"
program.write_text("\n".join(lines) + "\n")
compiler = "/mnt/data/forge-c/toolchains/LLVM-19.1.7-Linux-X64/bin/clang"
argv = [
    compiler,
    "-std=c11",
    "-O2",
    "-fno-strict-aliasing",
    *cmsis.host_flags(ws),
    "-I" + str(ws / "software/ll"),
    str(program),
    "-o",
    str(N / "host-assessment"),
]
compiled = subprocess.run(argv, capture_output=True, timeout=30)
(N / "host-compile.stdout").write_bytes(compiled.stdout)
(N / "host-compile.stderr").write_bytes(compiled.stderr)
assert compiled.returncode == 0, "HOST_ASSESSMENT_BUILD_FAILED"


def limited():
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))


observed = subprocess.run([str(N / "host-assessment")], capture_output=True, text=True, timeout=10, preexec_fn=limited)
(N / "host-observations.txt").write_text(observed.stdout)
assert observed.returncode == 0
rows = [list(map(int, line.split())) for line in observed.stdout.splitlines()]
assert len(rows) == len(cases) and [x[0] for x in rows] == list(range(len(cases)))
comparisons = []
for case, (_index, after, returned, frame) in zip(cases, rows, strict=True):
    form = int(case["intent_id"].split("-")[-1])
    expected_after = int(case["expected_after"], 16)
    expected_return = case["expected_return"]
    ok = after == expected_after and frame == 1 and (expected_return is None or returned == int(expected_return))
    comparisons.append(
        {
            "form": form,
            "function": functions[form],
            "initial": case["initial"],
            "expected_after": case["expected_after"],
            "observed_after": f"0x{after:08x}",
            "expected_return": expected_return,
            "observed_return": returned if expected_return is not None else None,
            "other_words_preserved": frame == 1,
            "status": "PASS_MODEL_COMPARISON" if ok else "REGISTER_IMAGE_MODEL_MISMATCH",
        }
    )
bad = [c for c in comparisons if c["status"] != "PASS_MODEL_COMPARISON"]
summary = {
    "schema": "forge-c/014-native-consumer-assessment/1",
    "source_revision": REV,
    "host": "omniverse2",
    "reproducer_sha256": C.sha256_bytes(Path(__file__).read_bytes()),
    "scope": "EXTERNAL_VERIFICATION_FIXTURE_NOT_PRODUCT_PHASE_OR_MODEL_RUN",
    "engine": ctx.pin.expected(),
    "original_candidate": "WWDG-LL-v02-002",
    "source_manifest_sha256": manifest_before,
    "domain_sha256": contract.domain_sha256,
    "joint_required_operations": 12,
    "engine_run_requests": ctx.calls,
    "oracle_reverification": "PASS",
    "obligation_reverification": "PASS",
    "mutation_operators": len(operators),
    "native_compilation": "PASS",
    "model_cases": len(cases),
    "cases_matching_model": len(cases) - len(bad),
    "cases_mismatching_model": len(bad),
    "mismatching_functions": sorted({c["function"] for c in bad}),
    "comparisons": comparisons,
    "model_scope": (
        "Plain memory register words, one call, no hardware side effects; "
        "mismatches do not establish ST silicon behavior or hardware incorrectness."
    ),
    "status": "ABSTRACT_MODEL_MISMATCH" if bad else "PASS_CONSUMER_AND_ABSTRACT_MODEL_ONLY",
    "model_calls": 0,
    "product_attempts": 0,
    "driver_ready": "NOT_RUN",
    "self_healing": "NOT_PROVEN",
    "deployment": "NOT_ACTIVATED",
    "copied_source_digests": copied,
    "generated_harness_sha256": C.sha256_bytes(program.read_bytes()),
    "generated_host_core_stub": "EXISTING_FACTORY_CMSIS_ADAPTER",
}
assert C.sha256_bytes((src / ".forge-run/manifest.json").read_bytes()) == manifest_before
assert not subprocess.check_output(["git", "-C", str(R), "status", "--porcelain"], text=True).strip()
p = N / "summary.json"
p.write_bytes(C.canonical_bytes(summary))
store = LessonStore()
eid = E.capture(
    store,
    "external-native-consumer-assessment-466d87b:" + N.name,
    "SOURCE_VERIFICATION_MODEL_ASSESSMENT",
    "BLOCKED" if bad else "PASS",
    facts={
        "consumer_checks": "PASS",
        "joint_forms": 12,
        "model_cases": len(cases),
        "mismatch_count": len(bad),
        "mismatching_functions": summary["mismatching_functions"],
        "model_calls": 0,
        "product_attempts": 0,
    },
    source_refs=[str(p) + "#sha256=" + C.sha256_bytes(p.read_bytes())],
    cohort={"study": "native-consumer-assessment-466d87b", "evaluation_holdout": False},
)
E.consolidate(store, limit=32, inference_budget=0)
with store._conn() as c:
    disposition = json.loads(c.execute("SELECT record FROM learning_dispositions WHERE experience_id=?", (eid,)).fetchone()[0])
(N / "learning-capture.json").write_bytes(
    C.canonical_bytes(
        {"experience_id": eid, "disposition": disposition, "qualified_lessons_added": 0, "learning_benefit": "NOT_MEASURED"}
    )
)
print(
    json.dumps(
        {
            k: summary[k]
            for k in (
                "status",
                "joint_required_operations",
                "oracle_reverification",
                "obligation_reverification",
                "mutation_operators",
                "model_cases",
                "cases_matching_model",
                "cases_mismatching_model",
                "mismatching_functions",
                "model_calls",
            )
        }
    ),
    flush=True,
)
raise SystemExit(2 if bad else 0)
