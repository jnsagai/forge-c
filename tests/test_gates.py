"""Tests of fail-closed quality gates. All generated fixtures are synthetic tests, not safety evidence."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from validate_profile import validate as validate_profile
from trace_gate import validate as validate_trace
from footprint_gate import validate as validate_footprint
from checks_gate import validate as validate_checks, MANDATORY
from quality_gate import validate as validate_quality


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "driver.c").write_text("int driver_demo(void) { return 0; }\n", encoding="utf-8")
        (self.root / "evidence").mkdir()
        self.raw = "evidence/raw.txt"
        (self.root / self.raw).write_text("real-output-in-synthetic-test-fixture\n", encoding="utf-8")
        self.digest = hashlib.sha256((self.root / self.raw).read_bytes()).hexdigest()
        self.profile = {
            "profile_id": "TEST-001", "status": "approved", "driver": "test_rcc", "asil": "B",
            "target": {"part_number": "TEST-MCU-1", "core": "cortex-m55", "silicon_revision": "R1", "board": "BOARD-1"},
            "hsi": {"contract_id": "HSI-001", "status": "approved", "approved_by": "ENGINEER"},
            "source_documents": [{"id": "RM", "revision": "R1", "sha256": "a" * 64, "approved": True}],
            "safety_allocation": {"status": "approved", "technical_safety_requirement_ids": ["TSR-001"],
                                  "software_safety_requirement_ids": ["SSR-001"], "safe_state_contract_id": "SSC-1",
                                  "approved_by": "SAFETY"},
            "toolchain": {"compiler": "arm-none-eabi-gcc", "version": "14-test", "reproducible_image_digest": "sha256:abcdef123456"},
            "budgets": {"flash_bytes": 4000, "static_ram_bytes": 64, "stack_bytes": 128,
                        "api_cycle_limits": {"clock_enable": 1500}},
            "budgets_status": "approved",
            "approval": {"design_approver": "ARCH-APPROVER", "safety_approver": "SAFE-APPROVER", "baseline_id": "B-001"}
        }
        base_items = [("SYS-001", "system_requirement"), ("SR-001", "software_requirement"),
                      ("SA-001", "architecture"), ("DD-001", "detailed_design"),
                      ("UNIT-001", "software_unit"), ("TC-UNIT-001", "unit_test"),
                      ("TC-INT-001", "integration_test"), ("TC-SW-001", "software_test"),
                      ("VR-UNIT-001", "verification_result"), ("VR-INT-001", "verification_result"),
                      ("VR-SW-001", "verification_result")]
        items = [{"id": a, "type": b} for a, b in base_items]
        for item in items:
            if item["type"] == "software_unit":
                item["source_file"] = "driver.c"
            if item["type"] == "verification_result":
                item.update({"result": "PASS", "evidence_file": self.raw, "evidence_sha256": self.digest})
        edges = [("SYS-001", "SR-001", "derives"),
                 ("SR-001", "SA-001", "allocated_to"),
                 ("SA-001", "DD-001", "refined_by"),
                 ("DD-001", "UNIT-001", "implemented_by"),
                 ("UNIT-001", "TC-UNIT-001", "verified_by"),
                 ("SA-001", "TC-INT-001", "verified_by"),
                 ("SR-001", "TC-SW-001", "verified_by"),
                 ("TC-UNIT-001", "VR-UNIT-001", "has_result"),
                 ("TC-INT-001", "VR-INT-001", "has_result"),
                 ("TC-SW-001", "VR-SW-001", "has_result")]
        self.trace = {"baseline_id": "B-001",
                      "safety_allocations": [{"software_safety_requirement_id": "SSR-001",
                                              "software_requirement_ids": ["SR-001"], "reviewed": True}],
                      "items": items, "links": [
            {"source": s, "target": d, "relation": r, "reviewed": True} for s, d, r in edges]}
        self.metrics = {
            "status": "measured", "target_part_number": "TEST-MCU-1", "toolchain_version": "14-test",
            "loadable_flash_bytes": 3000, "static_ram_bytes": 40, "max_stack_bytes": 60, "stack_proven": True,
            "heap_calls": 0, "api_worst_case_cycles": {"clock_enable": 1000}, "cycle_source": "real_hardware",
            "build_log": self.raw, "build_log_sha256": self.digest,
            "measurement_record": self.raw, "measurement_sha256": self.digest
        }
        self.checks = {key: {"status": "PASS", "log": self.raw, "sha256": self.digest} for key in MANDATORY}

    def test_complete_synthetic_fixture_passes_structurally(self):
        self.assertEqual([], validate_profile(self.profile))
        self.assertEqual([], validate_trace(self.trace, self.root))
        self.assertEqual([], validate_footprint(self.profile, self.metrics, self.root))
        self.assertEqual([], validate_checks(self.checks, self.root))

    def test_draft_profile_blocked(self):
        self.profile["status"] = "draft"
        self.assertIn("profile not approved", validate_profile(self.profile))

    def test_missing_safety_allocation_blocked(self):
        self.profile["safety_allocation"]["technical_safety_requirement_ids"] = []
        self.assertNotEqual([], validate_profile(self.profile))

    def test_excess_flash_blocked(self):
        self.metrics["loadable_flash_bytes"] = 4100
        self.assertTrue(any("exceeds" in e for e in validate_footprint(self.profile, self.metrics, self.root)))

    def test_non_hardware_timing_blocked_on_release(self):
        self.metrics["cycle_source"] = "Renode"
        self.assertNotEqual([], validate_footprint(self.profile, self.metrics, self.root))
        self.assertEqual([], validate_footprint(self.profile, self.metrics, self.root, require_hardware_cycles=False))

    def test_unproven_stack_blocked(self):
        self.metrics["stack_proven"] = False
        self.assertNotEqual([], validate_footprint(self.profile, self.metrics, self.root))

    def test_invalid_evidence_hash_blocked(self):
        self.checks["host_unit"]["sha256"] = "0" * 64
        self.assertTrue(any("SHA256" in e for e in validate_checks(self.checks, self.root)))

    def test_missing_trace_link_blocked(self):
        self.trace["links"] = [e for e in self.trace["links"] if e["relation"] != "allocated_to"]
        self.assertNotEqual([], validate_trace(self.trace, self.root))

    def test_unreviewed_trace_link_blocked(self):
        self.trace["links"][0]["reviewed"] = False
        self.assertNotEqual([], validate_trace(self.trace, self.root))

    def test_unverified_unit_result_blocked(self):
        self.trace["items"][-3]["result"] = "NOT_RUN"
        self.assertNotEqual([], validate_trace(self.trace, self.root))

    def test_unchecked_human_review_blocked_release(self):
        self.checks.pop("independent_review")
        self.assertNotEqual([], validate_checks(self.checks, self.root, phase="release"))
        self.assertEqual([], validate_checks(self.checks, self.root, phase="candidate"))

    def test_path_traversal_blocked(self):
        self.metrics["build_log"] = "../../etc/passwd"
        self.assertNotEqual([], validate_footprint(self.profile, self.metrics, self.root))

    def test_missing_safety_requirement_allocation_blocked(self):
        from trace_gate import validate_safety_allocations
        self.trace["safety_allocations"] = []
        self.assertNotEqual([], validate_safety_allocations(self.trace, self.profile))

    def test_quality_gate_e2e_structural(self):
        for key, item in (("profile", self.profile), ("trace", self.trace), ("metrics", self.metrics), ("checks", self.checks)):
            (self.root / f"{key}.json").write_text(json.dumps(item), encoding="utf-8")
        args = [str(self.root / f"{i}.json") for i in ("profile", "trace", "metrics", "checks")]
        self.assertEqual([], validate_quality(*args, root=self.root))
        self.checks["target_hil"]["status"] = "NOT_RUN"
        (self.root / "checks.json").write_text(json.dumps(self.checks), encoding="utf-8")
        self.assertNotEqual([], validate_quality(*args, root=self.root, phase="release"))
        self.assertEqual([], validate_quality(*args, root=self.root, phase="candidate"))


if __name__ == "__main__":
    unittest.main()
