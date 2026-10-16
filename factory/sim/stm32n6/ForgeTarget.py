"""Robot Framework keyword library for Forge-C SWE.6 requirement-based tests on the Renode STM32N6 model.

Test cases (agent-written, one per requirement, tagged with its SWR id) call these deterministic keywords:

    Run Target Scenario    scn_hsi.c    scenario=default      # build scenario + driver for Cortex-M55, run in Renode
    Target Check Should Pass    3                             # TCHECK id 3 passed in the last run
    All Target Checks Should Pass                             # last run completed, >0 checks, 0 failures
    Driver Flash Size Should Be At Most    4096               # measured .text+.data of the HAL objects (bytes)
    Driver Static RAM Should Be At Most    64                 # measured .data+.bss (bytes)
    Driver Stack Should Be At Most    128                     # worst-case call chain from gcc -fcallgraph-info=su

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
        self.last_src: Path | None = None

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
        self.last, self.last_name, self.last_src = res, f"{src.name} [{scenario}]", src
        return res

    def _need(self) -> dict:
        if self.last is None:
            raise AssertionError("no target scenario has been run in this suite")
        return self.last

    @keyword("Target Check Should Pass")
    def target_check_should_pass(self, check_id: int) -> None:
        r = self._need()
        # r72: SWR-018 "passed" on 'Target Check Should Pass    26' with no TCHECK 26 in the scenario: only failed ids
        # are reported by the target, so an undefined id must be refused here (no vacuous pass)
        defined = set(re.findall(r"\bTCHECK\(\s*(\d+)\s*,", self.last_src.read_text(errors="replace"))) \
            if self.last_src else set()
        if str(int(check_id)) not in defined:
            raise AssertionError(f"check {check_id} is not defined in {self.last_name} (no TCHECK({check_id}, ...))")
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

    def _objects(self, extra: list[str] | None = None, sub: str = "size") -> list[str]:
        cc = shutil.which("arm-none-eabi-gcc")
        if not cc:
            raise AssertionError("GNU Arm toolchain missing")
        out = self.wd / sub
        out.mkdir(parents=True, exist_ok=True)
        objs = []
        for c in [*sorted((self.ws / "software/hal").glob("*.c")), *self._ll_units(out)]:
            o = out / (c.stem + ".o")
            r = subprocess.run([cc, "-mcpu=cortex-m55", "-mthumb", "-mfloat-abi=hard", "-std=c11", "-Os",
                                "-ffunction-sections", "-fdata-sections", f"-I{self.ws / 'software/hal'}",
                                f"-I{self.ws / 'software/ll'}", *(extra or []), "-c", str(c), "-o", str(o)],
                               capture_output=True, text=True, timeout=120, cwd=out)
            if r.returncode != 0:
                raise AssertionError(f"driver build failed: {r.stderr[-300:]}")
            objs.append(str(o))
        return objs

    def _ll_units(self, out: Path) -> list[Path]:
        """CAPA-016 (r83): an LL work order has no HAL sources and its LL is header-only, so the driver measured as
        nothing ('no call graph produced'). Its compile unit plus a generated unit (build directory only) that
        instantiates every LL function non-inline are measured instead."""
        import json

        try:
            layer = json.loads((self.ws / ".forge-run/manifest.json").read_text()).get("layer")
        except (OSError, ValueError):
            layer = None
        hdr = self.ws / "software/ll/stm32n6xx_ll_rcc.h"
        if layer != "LL" or not hdr.is_file():
            return []
        code = re.sub(r"/\*.*?\*/|//[^\n]*", "", hdr.read_text(errors="replace"), flags=re.S)
        fns = re.findall(r"static\s+inline\s+(void|uint32_t)\s+(LL_RCC_\w+)\s*\(\s*void\s*\)", code)
        if not fns:
            return []
        lines = ["/* GENERATED measurement unit (build only, CAPA-016) */", '#include "stm32n6xx_ll_rcc.h"']
        for ret, name in fns:
            lines += [f"{ret} forge_measure_{name}(void);",
                      f"{ret} forge_measure_{name}(void) {{ {'return ' if ret != 'void' else ''}{name}(); }}"]
        unit = out / "forge_ll_measure.c"
        unit.write_text("\n".join(lines) + "\n")
        return [unit]

    def _sizes(self) -> dict[str, int]:
        size = shutil.which("arm-none-eabi-size")
        if not size:
            raise AssertionError("GNU Arm toolchain missing")
        objs = self._objects()
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

    def _stack(self) -> tuple[int, list[str]]:
        """Worst-case driver stack: deepest call chain over gcc's -fcallgraph-info=su graph (frames incl. saved
        registers). Indirect calls (ready-flag callbacks) are charged the deepest direct chain of the driver; a call
        to a function outside the driver, recursion or an unbounded dynamic frame makes the bound unknown (fail)."""
        objs = self._objects(["-fcallgraph-info=su"], "stack")
        frames: dict[str, int] = {}
        edges: dict[str, list[str]] = {}
        unbounded = []
        node = re.compile(r'^node: \{ title: "([^"]+)" label: "([^"]*)"', re.M)
        edge = re.compile(r'^edge: \{ sourcename: "([^"]+)" targetname: "([^"]+)"', re.M)
        for o in objs:
            ci = Path(o).with_suffix(".ci")
            text = ci.read_text(errors="replace") if ci.is_file() else ""
            for title, label in node.findall(text):
                m = re.search(r"(\d+) bytes \(([a-z,]+)\)", label)
                if m:
                    frames[title] = int(m.group(1))
                    if m.group(2) == "dynamic":
                        unbounded.append(f"dynamic frame: {title.rsplit(':', 1)[-1]}")
            for a, b in edge.findall(text):
                edges.setdefault(a, []).append(b)
        if not frames:
            unbounded.append("no call graph produced (no driver functions measured)")
        unknown = sorted({b.rsplit(":", 1)[-1] for v in edges.values() for b in v
                          if b != "__indirect_call" and b not in frames})
        unbounded += [f"calls function outside the driver: {u}" for u in unknown]

        def worst(n: str, indirect: int, path: tuple[str, ...] = ()) -> int:
            if n in path:
                unbounded.append(f"recursion: {n.rsplit(':', 1)[-1]}")
                return 0
            calls = [indirect if c == "__indirect_call" else worst(c, indirect, (*path, n))
                     for c in edges.get(n, []) if c == "__indirect_call" or c in frames]
            return frames.get(n, 0) + max(calls, default=0)

        direct = max((worst(n, 0) for n in frames), default=0)
        return max((worst(n, direct) for n in frames), default=0), sorted(set(unbounded))

    @keyword("Driver Stack Should Be At Most")
    def driver_stack_should_be_at_most(self, limit_bytes: int) -> int:
        stack, unbounded = self._stack()
        if unbounded:
            raise AssertionError(f"driver stack not bounded: {'; '.join(unbounded[:3])}")
        if stack > int(limit_bytes):
            raise AssertionError(f"driver worst-case stack {stack} B exceeds {limit_bytes} B")
        return stack
