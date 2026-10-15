"""Robot Framework keyword library for Forge-C SWE.6 requirement-based tests on the Renode STM32N6 model.

Test cases (agent-written, one per requirement, tagged with its SWR id) call these deterministic keywords:

    Run Target Scenario    scn_hsi.c    scenario=default      # build scenario + driver for Cortex-M55, run in Renode
    Target Check Should Pass    3                             # TCHECK id 3 passed in the last run
    All Target Checks Should Pass                             # last run completed, >0 checks, 0 failures
    Driver Flash Size Should Be At Most    4096               # measured .text+.data of the HAL objects (bytes)
    Driver Static RAM Should Be At Most    64                 # measured .data+.bss (bytes)

Scenario C files live in software/tests/software/ and use forge_target_test.h (TCHECK, mailbox). `scenario` is
"default" (RCC_SR ready flags follow RCC_CR enable bits) or "never_ready" (waits must time out).
Results are simulated target evidence (behavioural RCC model), not silicon verification.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from robot.api.deco import keyword, library


@library(scope="SUITE")
class ForgeTarget:
    def __init__(self, workspace: str = "."):
        self.ws = Path(workspace).resolve()
        self.wd = self.ws / "build" / "robot-target"
        self.last: dict | None = None
        self.last_name = ""

    def _scenario_file(self, source: str) -> Path:
        p = Path(source)
        cand = [p] if p.is_absolute() else [self.ws / "software/tests/software" / p, self.ws / p]
        for c in cand:
            if c.is_file():
                return c
        raise AssertionError(f"scenario source not found: {source}")

    @keyword("Run Target Scenario")
    def run_target_scenario(self, source: str, scenario: str = "default") -> dict:
        from forge_factory.mcp.servers.sim import build_image, renode_bin, run_image

        if scenario not in ("default", "never_ready"):
            raise AssertionError(f"unknown scenario {scenario} (default|never_ready)")
        renode = renode_bin()
        if not renode:
            raise AssertionError("Renode not installed")
        self.wd.mkdir(parents=True, exist_ok=True)
        src = self._scenario_file(source)
        elf = self.wd / f"{src.stem}_{scenario}.elf"
        ok, _log, errs = build_image(self.ws, src, elf)
        if not ok:
            raise AssertionError(f"build failed for {src.name}: {'; '.join(errs[:4])}")
        res, _out = run_image(renode, elf, scenario, self.wd)
        if res is None or not res["magic_ok"] or not res["done"]:
            raise AssertionError(f"{src.name} [{scenario}] produced no complete result on the target model")
        self.last, self.last_name = res, f"{src.name} [{scenario}]"
        return res

    def _need(self) -> dict:
        if self.last is None:
            raise AssertionError("no target scenario has been run in this suite")
        return self.last

    @keyword("Target Check Should Pass")
    def target_check_should_pass(self, check_id: int) -> None:
        r = self._need()
        if int(check_id) in r["failed_ids"]:
            raise AssertionError(f"check {check_id} failed in {self.last_name}")
        if r["passed"] == 0:
            raise AssertionError(f"no checks passed in {self.last_name}")

    @keyword("All Target Checks Should Pass")
    def all_target_checks_should_pass(self) -> None:
        r = self._need()
        if r["failed"] or r["passed"] == 0:
            raise AssertionError(f"{self.last_name}: {r['passed']} passed, {r['failed']} failed "
                                 f"(failed ids {r['failed_ids']})")

    def _sizes(self) -> dict[str, int]:
        cc, size = shutil.which("arm-none-eabi-gcc"), shutil.which("arm-none-eabi-size")
        if not cc or not size:
            raise AssertionError("GNU Arm toolchain missing")
        out = self.wd / "size"
        out.mkdir(parents=True, exist_ok=True)
        objs = []
        for c in sorted((self.ws / "software/hal").glob("*.c")):
            o = out / (c.stem + ".o")
            r = subprocess.run([cc, "-mcpu=cortex-m55", "-mthumb", "-mfloat-abi=hard", "-std=c11", "-Os",
                                "-ffunction-sections", "-fdata-sections", f"-I{self.ws / 'software/hal'}",
                                f"-I{self.ws / 'software/ll'}", "-c", str(c), "-o", str(o)],
                               capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                raise AssertionError(f"driver build failed: {r.stderr[-300:]}")
            objs.append(str(o))
        r = subprocess.run([size, "-t", *objs], capture_output=True, text=True, timeout=60)
        m = re.search(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+\d+\s+[0-9a-f]+\s+\(TOTALS\)", r.stdout, re.M)
        if not m:
            raise AssertionError("could not measure driver size")
        text, data, bss = (int(x) for x in m.groups())
        return {"flash": text + data, "ram": data + bss}

    @keyword("Driver Flash Size Should Be At Most")
    def driver_flash_size_should_be_at_most(self, limit_bytes: int) -> int:
        flash = self._sizes()["flash"]
        if flash > int(limit_bytes):
            raise AssertionError(f"driver flash {flash} B exceeds {limit_bytes} B")
        return flash

    @keyword("Driver Static RAM Should Be At Most")
    def driver_static_ram_should_be_at_most(self, limit_bytes: int) -> int:
        ram = self._sizes()["ram"]
        if ram > int(limit_bytes):
            raise AssertionError(f"driver static RAM {ram} B exceeds {limit_bytes} B")
        return ram
