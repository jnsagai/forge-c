"""Robot Framework keyword library for Forge-C SWE.6 requirement-based tests on the Renode STM32N6 model.

Test cases (agent-written, one per requirement, tagged with its SWR id) call these deterministic keywords:

    Run Target Scenario    scn_hsi.c    scenario=default      # build scenario + driver for Cortex-M55, run in Renode
    Target Check Should Pass    3                             # TCHECK id 3 passed in the last run
    All Target Checks Should Pass                             # last run completed, >0 checks, 0 failures
    Driver Flash Size Should Be At Most    4096               # measured .text+.data of the HAL objects (bytes)
    Driver Static RAM Should Be At Most    64                 # measured .data+.bss (bytes)
    Driver Stack Should Be At Most    128                     # worst-case call chain from gcc -fcallgraph-info=su

Register-access log (owner 2026-11-02): the peripheral model records every register read/write of the last run with
the phase the scenario set with FORGE_ACCESS_PHASE(p) (forge_target_test.h; phase 0 = from reset until the first
FORGE_ACCESS_PHASE). A prohibition is verified on that log, never on final register contents:

    Register Accesses Before First Call Should Be Empty       # no access in phase 0; FORGE_ACCESS_PHASE(1U)
                                                              # directly before the first LL/HAL call
    Register Accesses In Phase Should Be Empty    2           # no access while phase 2 was set
    Register Access Log Should Not Contain    phase=2    access=W    offset=0x018    # no matching entry

Scenario C files live in software/tests/software/ and use forge_target_test.h (TCHECK, mailbox). `scenario` is
"default" (RCC_SR ready flags follow RCC_CR enable bits) or "never_ready" (waits must time out).
Results are simulated target evidence (behavioural RCC model), not silicon verification.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from robot.api import logger
from robot.api.deco import keyword, library


def _measure_unit(header_text: str, ws: Path | None = None) -> str | None:
    """Same generator as forge_factory.layer.ll_measure_unit (CAPA-018); this library runs outside the package."""
    import sys

    pkg = str(Path(__file__).resolve().parents[2] / "python")  # factory/python of this checkout
    if pkg not in sys.path:
        sys.path.append(pkg)
    from forge_factory.layer import ll_measure_unit

    return ll_measure_unit(header_text, ws)


@library(scope="SUITE")
class ForgeTarget:
    def __init__(self, workspace: str = "."):
        self.ws = Path(workspace).resolve()
        self.wd = self.ws / "build" / "robot-target"
        self.last: dict | None = None
        self.last_name = ""
        self.last_src: Path | None = None
        self.last_accesses: list[dict] | None = None

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
        res, _out = run_image(renode, elf, scenario, self.wd, self.ws)
        if res is None or not res["magic_ok"] or not res["done"]:
            raise AssertionError(f"{src.name} [{scenario}] produced no complete result on the target model")
        from forge_factory.mcp.servers.sim import access_log_path, read_access_log

        self.last, self.last_name, self.last_src = res, f"{src.name} [{scenario}]", src
        self.last_accesses = read_access_log(access_log_path(elf, self.wd))
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

    def _accesses(self, phase: int | None = None) -> list[dict]:
        """The last run's register-access log; a phase the scenario never sets is refused (no vacuous pass)."""
        self._need()
        if self.last_accesses is None:
            raise AssertionError(f"ACCESS_LOG_MISSING: {self.last_name} left no register-access log")
        src = self.last_src.read_text(errors="replace") if self.last_src else ""
        marks = {int(m) for m in re.findall(r"\bFORGE_ACCESS_PHASE\(\s*(\d+)[uU]?\s*\)", src)}
        if phase is not None and phase != 0 and phase not in marks:
            raise AssertionError(f"ACCESS_PHASE_NOT_SET: {self.last_name} never calls FORGE_ACCESS_PHASE({phase}U)")
        return self.last_accesses

    @staticmethod
    def _show(entries: list[dict]) -> str:
        return "; ".join(f"#{e['index']} {e['access']} {e['offset']:#05x}={e['value']:#010x} phase {e['phase']}"
                         + (f" pc {e['pc']:#010x}" if e["pc"] is not None else "") for e in entries[:6]) \
            + (f" (+{len(entries) - 6} more)" if len(entries) > 6 else "")

    @keyword("Register Accesses Before First Call Should Be Empty")
    def register_accesses_before_first_call_should_be_empty(self) -> None:
        log = self._accesses()
        if not re.search(r"\bFORGE_ACCESS_PHASE\(", self.last_src.read_text(errors="replace")):
            raise AssertionError(f"ACCESS_PHASE_NOT_SET: {self.last_name} marks no first call: put "
                                 "FORGE_ACCESS_PHASE(1U) directly before the first LL/HAL call")
        early = [e for e in log if e["phase"] == 0]
        if early:
            raise AssertionError(f"{self.last_name}: {len(early)} register access(es) before the first call: "
                                 f"{self._show(early)}")
        if not log:  # the marked call was never observed: an empty log proves nothing about the window
            raise AssertionError(f"ACCESS_FIRST_CALL_NOT_OBSERVED: {self.last_name} logged no register access at all")

    @keyword("Register Accesses In Phase Should Be Empty")
    def register_accesses_in_phase_should_be_empty(self, phase: int) -> None:
        hit = [e for e in self._accesses(int(phase)) if e["phase"] == int(phase)]
        if hit:
            raise AssertionError(f"{self.last_name}: {len(hit)} register access(es) in phase {int(phase)}: "
                                 f"{self._show(hit)}")

    @keyword("Register Access Log Should Not Contain")
    def register_access_log_should_not_contain(self, phase: str = "*", access: str = "*", offset: str = "*") -> None:
        if phase == access == offset == "*":
            raise AssertionError("ACCESS_FILTER_EMPTY: give phase=, access= (R|W) and/or offset=")
        if access not in ("*", "R", "W"):
            raise AssertionError(f"ACCESS_FILTER_INVALID: access={access} (R|W)")
        log = self._accesses(None if phase == "*" else int(phase))
        hit = [e for e in log if (phase == "*" or e["phase"] == int(phase)) and (access == "*" or e["access"] == access)
               and (offset == "*" or e["offset"] == int(str(offset), 0))]
        if hit:
            raise AssertionError(f"{self.last_name}: {len(hit)} matching register access(es) "
                                 f"(phase={phase} access={access} offset={offset}): {self._show(hit)}")

    @keyword("Simulation Performance Should Meet Budget")
    def simulation_performance_should_meet_budget(self) -> None:
        from forge_factory.afo.durable import digest
        from forge_factory.simulation_performance import selected

        budget = selected(self.ws)
        measurement = self._need().get("performance") or {}
        if not budget:
            raise AssertionError("SIM_PERF_NO_DECLARED_BUDGET")
        if self.last_src != self.ws / budget["test_source"]:
            raise AssertionError(f"SIM_PERF_WRONG_SCENARIO: Run Target Scenario    {budget['test_source']}; "
                                 "only the declared test receives entry/return instrumentation")
        if not measurement:
            raise AssertionError("SIM_PERF_MEASUREMENT_MISSING: rerun the declared instrumented target test")
        if measurement.get("budget_sha256") != digest(budget):
            raise AssertionError("SIM_PERF_BUDGET_CHANGED: rerun the declared test with the current budget")
        if measurement.get("status") != "PASS":
            raise AssertionError("SIM_PERF_MEASUREMENT_FAILED: no complete passing measurement; "
                                 "inspect the independent entry/return measurement issues")
        self.all_target_checks_should_pass()

    def _objects(self, extra: list[str] | None = None, sub: str = "size") -> list[str]:
        cc = shutil.which("arm-none-eabi-gcc")
        if not cc:
            raise AssertionError("GNU Arm toolchain missing")
        out = self.wd / sub
        out.mkdir(parents=True, exist_ok=True)
        objs = []
        from forge_factory.brownfield.cmsis import delivered_unit, target_flags
        from forge_factory.delivery_first import include_flags

        units = [*sorted((self.ws / "software/hal").glob("*.c")), *self._ll_units(out)]
        if not units:  # CAPA-061 (b007): a header-only delivery (ST LL) is measured through its scope wrappers
            u = delivered_unit(self.ws, out)
            units = [u] if u else []
        if not units:  # CAPA-061: nothing built is never a 0-byte PASS of a flash, RAM or stack budget
            raise AssertionError("no driver unit to measure (no HAL source, no LL unit, no delivered scope)")
        if sub == "stack":  # CAPA-063 (h004): the HAL's external time base is charged as a leaf reference
            units += self._time_base_unit(out)
        for c in units:
            o = out / (c.stem + ".o")
            r = subprocess.run([cc, "-mcpu=cortex-m55", "-mthumb", "-mfloat-abi=hard", "-std=c11", "-Os",
                                "-ffunction-sections", "-fdata-sections", f"-I{self.ws / 'software/hal'}",
                                f"-I{self.ws / 'software/ll'}", *target_flags(self.ws), *include_flags(self.ws),
                                *(extra or []), "-c", str(c),
                                "-o", str(o)],
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
        from forge_factory.layer import ll_header

        hdr = self.ws / ll_header(self.ws)
        if layer != "LL" or not hdr.is_file():
            return []
        text = _measure_unit(hdr.read_text(errors="replace"), self.ws)
        if text is None:
            return []
        unit = out / "forge_ll_measure.c"
        unit.write_text(text)
        return [unit]

    def _time_base_unit(self, out: Path) -> list[Path]:
        """CAPA-063 (h004): a HAL whose waits are bounded by an external time base (profile hal.time_base, e.g.
        HAL_GetTick) calls a function outside the driver, so the stack bound was unknown. The call chain is measured
        with a reference LEAF implementation (a free-running counter, as in the tests); the assumption that the
        system's time base is a leaf no deeper than this reference is logged with the result. Stack only: the
        reference is never counted in the driver's flash or RAM."""
        from forge_factory.layer import profile

        tb = profile(self.ws)["hal"].get("time_base")
        if not tb:
            return []
        self.assumptions = [f"external time base {tb}() measured as a reference leaf (free-running counter); the "
                            f"system's {tb}() must be a leaf of no larger frame"]
        unit = out / "forge_time_base_reference.c"
        unit.write_text(f"#include <stdint.h>\nuint32_t {tb}(void);\nuint32_t {tb}(void)\n{{\n"
                        "    static uint32_t forge_ticks;\n    forge_ticks++;\n    return forge_ticks;\n}\n")
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
        self.assumptions = []
        stack, unbounded = self._stack()
        for a in self.assumptions:  # CAPA-063: stated in the Robot log, never silent
            logger.info(f"ASSUMPTION: {a}")
        if unbounded:
            raise AssertionError(f"driver stack not bounded: {'; '.join(unbounded[:3])}")
        if stack > int(limit_bytes):
            raise AssertionError(f"driver worst-case stack {stack} B exceeds {limit_bytes} B")
        return stack
