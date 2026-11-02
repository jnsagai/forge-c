"""Owner 2026-11-02 "Allow access logging": the simulated peripheral models record every register read/write, and a
register-access prohibition ("shall not read or write any register before the first call / outside a function") is
verified on that log - a write that restores the original value, or a read, is invisible in final register contents.

Unit level (CPython, no Renode): the observer appended to every Forge-C model leaves the model's behaviour unchanged,
logs index/R|W/offset/value/phase/pc and keeps the RAM counters forge_target_test.h reads; the log parser refuses
malformed or gapped logs; the Robot keywords refuse vacuous passes. Renode level: a correct driver passes the C-side
(TCHECK on FORGE_ACCESS_COUNT*) and Robot-side checks, a seeded early/between-call access is detected by both while
the final register contents are identical."""
import importlib.util
import random
import sys
import types
from pathlib import Path

import pytest
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT
from forge_factory.mcp.servers import robot_policy, sim

MODELS = sorted(p.name for p in sim.SIM_DIR.glob("*_model.py"))
BASE = sim.ACCESS_LOG_BASE


class _Req:
    pass


class _Bus:
    """The SystemBus the observer sees: RAM words, and a CPU context unless the access comes from the monitor."""

    def __init__(self):
        self.ram, self.pc = {}, 0x34000100

    def ReadDoubleWord(self, a):  # noqa: N802 - Renode API name
        return self.ram.get(a, 0)

    def WriteDoubleWord(self, a, v):  # noqa: N802
        self.ram[a] = v & 0xFFFFFFFF

    def GetCurrentCPU(self):  # noqa: N802
        if self.pc is None:
            raise Exception("Can't verify current CPU in the given context.")  # noqa: TRY002 - Renode raises this
        pc = types.SimpleNamespace(RawValue=self.pc)
        return types.SimpleNamespace(PC=pc)


def _runner(text: str, log: Path | None, monkeypatch):
    """Execute a model script the way Renode's PythonPeripheral does: one scope, the whole script per request."""
    env = types.SimpleNamespace(GetEnvironmentVariable=lambda k: str(log) if log and k == "FORGE_ACCESS_LOG" else None)
    monkeypatch.setitem(sys.modules, "System", types.SimpleNamespace(Environment=env))
    bus = _Bus()
    ns = {"self": types.SimpleNamespace(GetMachine=lambda: types.SimpleNamespace(SystemBus=bus))}
    code = compile(text, "model", "exec")

    def call(kind, off=0, val=0):
        r = _Req()
        r.IsInit, r.IsRead, r.IsWrite = kind == "init", kind == "read", kind == "write"
        r.Offset, r.Value = off, val
        ns["request"] = r
        exec(code, ns)  # noqa: S102 - the repository's own simulator model
        return r.Value

    call("init")
    return call, bus, ns


def _sequence(seed: int, size: int) -> list[tuple[str, int, int]]:
    rng = random.Random(seed)  # noqa: S311 - deterministic test stimulus
    offs = [0, 4, 8, 0xC, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28, 0x30, 0x3C, 0x40, 0x44, 0x48, 0x4C, 0x50]
    if size > 0x1000:
        offs += [0x210, 0x250, 0x800, 0xA50, 0x1000, 0x1250]
    return [(rng.choice(("read", "write")), rng.choice(offs), rng.getrandbits(32)) for _ in range(200)]


@pytest.mark.parametrize("name", MODELS)
def test_the_observer_leaves_every_model_unchanged_and_logs_every_access(name, tmp_path, monkeypatch):
    base = (sim.SIM_DIR / name).read_text()
    size = 0x2000 if name == "rcc_model.py" else 0x400
    plain, _, plain_ns = _runner(base, None, monkeypatch)
    log = tmp_path / "a.log"
    observed, bus, ns = _runner(sim.observed_model(base), log, monkeypatch)
    seq = _sequence(len(name), size)
    phases = []
    for k, (kind, off, val) in enumerate(seq):
        if k % 50 == 0:  # the test moves to a new phase (a RAM write the model never sees)
            bus.ram[BASE] = k // 50
        phases.append(bus.ram.get(BASE, 0))
        assert observed(kind, off, val) == plain(kind, off, val), (name, k, kind, hex(off))
    entries = sim.read_access_log(log)
    assert [(e["access"], e["offset"], e["phase"], e["pc"]) for e in entries] == [
        ("R" if kind == "read" else "W", off, ph, 0x34000100) for (kind, off, _v), ph in zip(seq, phases, strict=True)]
    for e, (kind, _off, val) in zip(entries, seq, strict=True):
        if kind == "write":
            assert e["value"] == val  # the value the CPU wrote, not the model's view of it
    assert bus.ram[BASE + 4] == len(seq)
    assert [bus.ram.get(BASE + 8 + 4 * p, 0) for p in range(4)] == [phases.count(p) for p in range(4)]
    assert not any(k.startswith("forge_acc") or k == "ACCESS_LOG_BASE" for k in plain_ns)  # no name the model uses
    assert any(k.startswith("forge_acc") for k in ns)


def test_reads_log_the_value_the_model_returned_and_monitor_accesses_have_no_pc(tmp_path, monkeypatch):
    log = tmp_path / "a.log"
    call, bus, _ = _runner(sim.observed_model((sim.SIM_DIR / "gpio_model.py").read_text()), log, monkeypatch)
    assert call("read", 0x00) == 0xABFFEFFF  # GPIOA MODER reset value
    bus.pc = None  # monitor access (no CPU context)
    call("write", 0x18, 0x20)
    assert call("read", 0x14) == 0x20  # BSRR set ODR bit 5
    assert [(e["access"], e["offset"], e["value"], e["pc"]) for e in sim.read_access_log(log)] == [
        ("R", 0x00, 0xABFFEFFF, 0x34000100), ("W", 0x18, 0x20, None), ("R", 0x14, 0x20, None)]


def test_without_a_log_path_the_observer_only_counts(monkeypatch):
    call, bus, _ = _runner(sim.observed_model((sim.SIM_DIR / "iwdg_model.py").read_text()), None, monkeypatch)
    call("write", 0, 0x5555)
    call("read", 0xC)
    assert bus.ram[BASE + 4] == 2 and bus.ram[BASE + 8] == 2


def test_the_log_parser_refuses_missing_malformed_and_gapped_logs(tmp_path):
    p = tmp_path / "x.access.log"
    assert sim.read_access_log(p) is None  # no observation is never an empty (passing) log
    p.write_text("")
    assert sim.read_access_log(p) == []
    p.write_text("0 W 0x004 0x00000005 1 0x34000100\n1 R 0x00C 0x00000001 2 -\n")
    assert sim.read_access_log(p)[1] == {"index": 1, "access": "R", "offset": 0xC, "value": 1, "phase": 2, "pc": None}
    p.write_text("0 W 0x004 0x00000005 1 -\n2 R 0x00C 0x00000001 2 -\n")
    with pytest.raises(ValueError, match="ACCESS_LOG_NOT_CONTIGUOUS"):
        sim.read_access_log(p)
    p.write_text("0 X 0x004 5 1 -\n")
    with pytest.raises(ValueError, match="ACCESS_LOG_MALFORMED"):
        sim.read_access_log(p)
    assert sim.access_log_path(Path("/w/scn_a_default.elf"), Path("/w")) == Path("/w/scn_a_default.access.log")


def _library(ws: Path):
    spec = importlib.util.spec_from_file_location("forge_target_acc", REPO_ROOT / "factory/sim/stm32n6/ForgeTarget.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ForgeTarget(str(ws))


def _fake_run(lib, src: Path, entries):
    lib.last = {"magic_ok": True, "passed": 1, "failed": 0, "done": True, "failed_ids": []}
    lib.last_name, lib.last_src, lib.last_accesses = src.name, src, entries


def _e(i, acc, off, phase):
    return {"index": i, "access": acc, "offset": off, "value": 0, "phase": phase, "pc": None}


def test_the_robot_keywords_check_the_log_and_refuse_vacuous_passes(tmp_path):
    lib = _library(tmp_path)
    src = tmp_path / "scn.c"
    src.write_text("FORGE_ACCESS_PHASE(1U); LL_X_Init(); FORGE_ACCESS_PHASE(2U);\n")
    good = [_e(0, "W", 0x4, 1), _e(1, "R", 0xC, 1)]
    _fake_run(lib, src, good)
    lib.register_accesses_before_first_call_should_be_empty()
    lib.register_accesses_in_phase_should_be_empty(2)
    lib.register_access_log_should_not_contain(phase="2", access="W")
    lib.register_access_log_should_not_contain(offset="0x018")
    with pytest.raises(AssertionError, match="ACCESS_PHASE_NOT_SET"):
        lib.register_accesses_in_phase_should_be_empty(3)  # the scenario never sets phase 3
    with pytest.raises(AssertionError, match="matching register access"):
        lib.register_access_log_should_not_contain(phase="1", access="W", offset="0x4")
    with pytest.raises(AssertionError, match="ACCESS_FILTER_EMPTY"):
        lib.register_access_log_should_not_contain()
    _fake_run(lib, src, [_e(0, "W", 0x8, 0), *[{**e, "index": e["index"] + 1} for e in good]])
    with pytest.raises(AssertionError, match=r"1 register access\(es\) before the first call: #0 W 0x008"):
        lib.register_accesses_before_first_call_should_be_empty()
    _fake_run(lib, src, [*good, _e(2, "R", 0xC, 2)])
    with pytest.raises(AssertionError, match="in phase 2"):
        lib.register_accesses_in_phase_should_be_empty("2")
    _fake_run(lib, src, [])
    with pytest.raises(AssertionError, match="ACCESS_FIRST_CALL_NOT_OBSERVED"):
        lib.register_accesses_before_first_call_should_be_empty()
    _fake_run(lib, src, None)
    with pytest.raises(AssertionError, match="ACCESS_LOG_MISSING"):
        lib.register_accesses_in_phase_should_be_empty(2)
    src.write_text("LL_X_Init();\n")
    _fake_run(lib, src, good)
    with pytest.raises(AssertionError, match="ACCESS_PHASE_NOT_SET"):
        lib.register_accesses_before_first_call_should_be_empty()


def test_the_robot_policy_and_scaffold_offer_the_access_keywords(tmp_path):
    from forge_factory.workflow import robot_scaffold

    suite = tmp_path / "t.robot"
    suite.write_text("*** Settings ***\nLibrary    ForgeTarget\n\n*** Test Cases ***\nSWR-001 no early access\n"
                     "    [Tags]    SWR-001\n    Run Target Scenario    scn_a.c\n"
                     "    Register Accesses Before First Call Should Be Empty\n"
                     "    Register Accesses In Phase Should Be Empty    2\n"
                     "    Register Access Log Should Not Contain    phase=2    access=W\n")
    assert robot_policy.check_suite(suite) == []
    for kw in ("Register Accesses Before First Call Should Be Empty", "Register Accesses In Phase Should Be Empty",
               "Register Access Log Should Not Contain"):
        assert kw in robot_scaffold.HEADER


def test_prohibitions_get_the_access_log_rule_and_the_host_says_it_cannot_observe_them():
    from forge_factory.lrtx import swe5

    assert swe5.has_prohibition("The LL shall not write any register before the first call.")
    assert swe5.has_prohibition("If no instance is passed, the LL shall not write to IWDG_RLR.")
    assert swe5.has_prohibition("passes when the register-access log is empty before the first call.")
    assert not swe5.has_prohibition("The LL shall set RCC_CR.HSION and shall not modify RCC_CR.HSEON.")
    assert "FORGE_ACCESS_COUNT()" in swe5.TARGET_ACCESS_RULE and "FORGE_ACCESS_COUNT_IN(" in swe5.TARGET_ACCESS_RULE
    assert "no access log" in swe5.HOST_ACCESS_RULE


# ---- Renode: the log on the real simulator --------------------------------------------------------------------
LL = """
static inline void LL_IWDG_EnableWriteAccess(void) { ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x00005555U; }
static inline void LL_IWDG_SetPrescaler(uint32_t p) { ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] = (p & LL_IWDG_PR_PR_MSK); }
static inline uint32_t LL_IWDG_GetPrescaler(void) { return ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] & LL_IWDG_PR_PR_MSK; }
"""
# EARLY/BETWEEN: the seeded defect. A write that restores the reset value of IWDG_RLR and a read of IWDG_SR before the
# first call, and a read between the calls - final register contents (TCHECK 3) are the same as for a correct driver.
SCN = """#include "stm32n6xx_ll_iwdg.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
int main(void) { uint32_t pr; FORGE_TEST_BEGIN();
%(early)s
  TCHECK(1, FORGE_ACCESS_COUNT() == 0U);
  FORGE_ACCESS_PHASE(1U);
  LL_IWDG_EnableWriteAccess(); LL_IWDG_SetPrescaler(4U);
  FORGE_ACCESS_PHASE(2U);
%(between)s
  TCHECK(2, FORGE_ACCESS_COUNT_IN(2U) == 0U);
  FORGE_ACCESS_PHASE(3U);
  pr = LL_IWDG_GetPrescaler();
  FORGE_ACCESS_PHASE(4U);
  TCHECK(3, (pr == 4U) && (ll_iwdg_regs[LL_IWDG_RLR_OFFSET / 4U] == 0x00000FFFU));
  TCHECK(4, (FORGE_ACCESS_COUNT_IN(1U) == 2U) && (FORGE_ACCESS_COUNT_IN(3U) == 1U));
  FORGE_TEST_END(); return 0; }
"""
SEED_EARLY = ("  ll_iwdg_regs[LL_IWDG_RLR_OFFSET / 4U] = 0x00000FFFU;\n"
              "  (void)ll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U];")
SEED_BETWEEN = "  (void)ll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U];"


@pytest.mark.skipif(sim.renode_bin() is None or not __import__("shutil").which("arm-none-eabi-gcc"),
                    reason="Renode / GNU Arm not installed")
def test_renode_detects_a_seeded_access_before_the_first_call_and_passes_a_correct_driver(tmp_path, monkeypatch):
    from forge_factory.inspection import regmap

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    ws, _ = WO.prepare(REPO_ROOT / "examples/0009a-iwdg-ll", "WO-IWDG-ACCESS-LOG")
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        "## Register table\n\n| Register | Offset |\n|---|---|\n| IWDG_KR | 0x000 |\n| IWDG_PR | 0x004 |\n"
        "| IWDG_RLR | 0x008 |\n| IWDG_SR | 0x00C |\n")
    regmap.generate(ws)
    h = ws / "software/ll/stm32n6xx_ll_iwdg.h"
    h.write_text(h.read_text().replace(regmap.functions_marker(ws), regmap.functions_marker(ws) + LL))
    scn = ws / "software/tests/software"
    scn.mkdir(parents=True)
    (scn / "scn_good.c").write_text(SCN % {"early": "", "between": ""})
    (scn / "scn_seeded.c").write_text(SCN % {"early": SEED_EARLY, "between": SEED_BETWEEN})
    lib = _library(ws)

    good = lib.run_target_scenario("scn_good.c")
    assert good == {"magic_ok": True, "passed": 4, "failed": 0, "done": True, "failed_ids": []}
    log = lib.last_accesses
    assert [(e["access"], e["offset"], e["value"], e["phase"]) for e in log] == [
        ("W", 0x0, 0x5555, 1), ("W", 0x4, 4, 1), ("R", 0x4, 4, 3), ("R", 0x8, 0xFFF, 4)]
    assert all(e["pc"] is not None and 0x34000000 <= e["pc"] < 0x341F0000 for e in log)  # the CPU's access PCs
    lib.register_accesses_before_first_call_should_be_empty()
    lib.register_accesses_in_phase_should_be_empty(2)
    lib.register_access_log_should_not_contain(phase="3", access="W")

    seeded = lib.run_target_scenario("scn_seeded.c")
    assert seeded["failed_ids"] == [1, 2] and seeded["passed"] == 2  # C side: TCHECK 1 and 2 catch it ...
    assert 3 not in seeded["failed_ids"]  # ... while the final register contents look exactly like a correct run
    with pytest.raises(AssertionError, match=r"2 register access\(es\) before the first call: #0 W 0x008=0x00000fff "
                                             r"phase 0 pc 0x[0-9a-f]{8}; #1 R 0x00c"):
        lib.register_accesses_before_first_call_should_be_empty()
    with pytest.raises(AssertionError, match=r"1 register access\(es\) in phase 2: #4 R 0x00c"):
        lib.register_accesses_in_phase_should_be_empty(2)
