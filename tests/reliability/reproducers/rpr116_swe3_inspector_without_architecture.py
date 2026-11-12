"""RPR-116 (Fabro runs WO-F014-CMP-SWE3-OBL-20261102-08 and WO-F014-CMP-SWE3-IWDG-20261102-08, cloud comparison line,
loop10, 2026-11-02): CRC IDR 0014i (greenfield LL, instance mode) and IWDG LL 0009h (register-block array), structured
SWE.3. The structured SWE.3 inspector received only the SWE.3 baseline files
plus the SWE.1 requirements: not the frozen SWE.2 architecture/interface baseline that SWE3-01/03 judge against, not the
instance-mode device header the code includes, and no frozen baseline record (SWE3-06 change/trace provenance). It
failed SWE3-01/03/06 for the missing evidence three times: BLOCKED STUCK SAME_ITEM_FAILED_3X (IWDG: SWE3-01 "The
supplied sources omit the frozen SWE.2 architecture and interface baseline" in all three rounds).

Scenario: the real lrtx.review.evidence on a scratch workspace with frozen SWE.1/SWE.2/SWE.3 baseline records and their
files, once without an instance declaration (IWDG) and once with one (CRC; the validated declaration is stubbed, the
work-order inputs are small fixture files written here).
Symptom: the SWE.3 inspector sources lack the frozen SWE.2 architecture, the declared device header/API contract or
the baseline records."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "the structured SWE.3 inspector does not receive the frozen SWE.2 architecture, instance inputs or baseline record"
INST = {"parameter": "CRCx", "macro": "CRC", "type_name": "CRC_TypeDef", "device_header": "forge_crc_device.h",
        "api_contract": "IDR-API.h", "host_object": "forge_host_crc"}
FILES = {
    "SWE.1": {"workproducts/SWE.1/software_requirements.md": "- **SWR-001** When ... the CRC LL driver shall write.\n"},
    "SWE.2": {"workproducts/SWE.2/software_architecture.md": "# Software architecture\nSWC-LL-01 stm32n6xx_ll_crc\n",
              "workproducts/SWE.2/api_calls.json": "{\"calls\": []}\n",
              "workproducts/SWE.2/architecture_static.puml": "@startuml\n@enduml\n",
              "workproducts/SWE.2/architecture_static.svg": "<svg/>\n"},
    "SWE.3": {"software/ll/stm32n6xx_ll_crc.h": "#include \"forge_crc_device.h\"\n",
              "workproducts/SWE.3/unit_specifications.md": "USPEC-LL-01-01\n"},
}
INPUTS = {"inputs/forge_crc_device.h": "typedef struct { volatile uint32_t IDR; } CRC_TypeDef;\n",
          "inputs/IDR-API.h": "static inline void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData);\n"}


def _workspace(ws: Path, instance: bool) -> None:
    from forge_factory.common import canonical_json, sha256_bytes, sha256_file

    for rel, text in [*INPUTS.items(), *(kv for ph in FILES.values() for kv in ph.items())]:
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    hashes = {}
    for phase, up in (("SWE.1", []), ("SWE.2", ["SWE.1"]), ("SWE.3", ["SWE.1", "SWE.2"])):
        files = {rel: sha256_file(ws / rel) for rel in FILES[phase]}
        hashes[phase] = sha256_bytes(canonical_json(files))
        rec = {"schema": "forge-c/baseline/0.4", "baseline_id": f"BL-{phase}-001", "phase": phase,
               "author_role": f"swe{phase[-1]}-author", "baseline_hash": hashes[phase], "files": files,
               "upstream": {u: hashes[u] for u in up}, "frozen_at": "2026-11-02T17:05:00Z"}
        (ws / "configuration/baselines" / phase).mkdir(parents=True, exist_ok=True)
        (ws / "configuration/baselines" / phase / f"BL-{phase}-001.json").write_text(json.dumps(rec, indent=1))
    iface = {"schema": "forge-c/typed-register-interface/1", "device_header": "inputs/forge_crc_device.h",
             "api_contract": "inputs/IDR-API.h", "manual": "inputs/RM0486-rev4-ch26-crc.md", "type_name": "CRC_TypeDef",
             "members": [{"register": "CRC_IDR", "member": "IDR", "width_bits": 32}]}
    manifest = {"work_order": "WO-RPR-116", "layer": "LL", "scope": ["CRC_IDR write/read"], "target": {},
                "budgets": {}, "upstream": None,
                "operation_scope": {"schema": "forge-c/operation-scope/1", "instance": {
                    "schema": "forge-c/ll-instance/1", "parameter": "CRCx", "macro": "CRC",
                    "host_object": "forge_host_crc", "register_interface": iface}}}
    if not instance:
        del manifest["operation_scope"]
    (ws / ".forge-run").mkdir(parents=True, exist_ok=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest, indent=1))


def _sources(instance: bool) -> dict:
    from forge_factory import layer, operation_scope
    from forge_factory.lrtx import review

    layer.ll_instance = lambda _ws=None: dict(INST) if instance else None
    operation_scope.instance_of = layer.ll_instance
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        _workspace(ws, instance)
        bl, srcs = review.evidence(ws, "SWE.3")
    if bl.get("baseline_id") != "BL-SWE.3-001" or "software/ll/stm32n6xx_ll_crc.h" not in {s["path"] for s in srcs}:
        raise LookupError("the SWE.3 baseline was not the inspected evidence")
    return {s["path"]: s["text"] for s in srcs}


def main() -> int:
    try:
        legacy, inst = _sources(False), _sources(True)
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{type(exc).__name__}:{str(exc)[:120]}")
        return 2
    need = ["workproducts/SWE.2/software_architecture.md", "workproducts/SWE.2/api_calls.json",
            "configuration/baselines/SWE.3/BL-SWE.3-001.json", "configuration/baselines/SWE.2/BL-SWE.2-001.json"]
    if any(p not in t for t in (legacy, inst) for p in need) or \
            any(p not in inst for p in ("inputs/forge_crc_device.h", "inputs/IDR-API.h")):
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    arch = FILES["SWE.2"]["workproducts/SWE.2/software_architecture.md"]
    if all(t["workproducts/SWE.2/software_architecture.md"] == arch for t in (legacy, inst)):
        print("SYMPTOM_ABSENT")
        return 0
    print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:architecture source text differs from the frozen file")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
