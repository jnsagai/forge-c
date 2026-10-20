"""T009/T046/T047 — generate the v0.4 unattended SWE.1–SWE.6 Fabro workflow (DOT) + run binding.

Graph per phase n:  (SWE.3: regmap -> ll -> hal -> fix ->; SWE.4: swe4_scaffold -> swe4_test_author ->)
                    swe{n}_author -> swe{n}_author_gate -[ok]->
                    (SWE.3: swe3_verify ->) swe{n}_inspector
                    -> swe{n}_inspect_gate -[ok]-> next phase ... ; any gate failure -> swe{n}_route
                    swe{n}_route -[ok: rework budget left]-> swe{n}_author | -[fail]-> finalize
After SWE.6: release_manager (agent, read-only) -> finalize (deterministic packager) -> exit.
Every terminal path reaches `finalize` (T046). Failure edges are the unconditional fallback (fail
closed: any non-success outcome reworks or blocks); success edges are `outcome=succeeded` conditions.
Agents never route: only command-node exit codes do.
No human gate nodes exist. Product (driver) defects loop in SWE phases; infrastructure faults are
handled by the external supervisor/repair path, not by this graph (T047).
"""
from __future__ import annotations

import sys

from ..common import REPO_ROOT
from ..inspection.engine import PHASES
from ..policy.authz import Binding

UPSTREAM_LOOPS = 2  # ADR-0008: run-wide cross-phase loop budget (= defects.UPSTREAM_LOOP_BUDGET)
REWORK_CYCLES = 3  # checklist policy maximum_rework_cycles
PROGRESS_EXTRA_CYCLES = 2  # owner decision 2026-10-18: rework-policy.yaml max_extra_cycles (gate.extra_cycles)
# Fabro kills the run when a node is entered beyond max_visits (probe P2, ADR-0008). The rework budget is per epoch
# (owner decision 2026-10-15): each upstream loop gives every phase 1 + REWORK_CYCLES (+ progress extension) visits.
MAX_VISITS = (1 + REWORK_CYCLES + PROGRESS_EXTRA_CYCLES) * (1 + UPSTREAM_LOOPS)
ONCE = 1 + UPSTREAM_LOOPS  # single-pass nodes (scaffolds' authors, LL/HAL authors) re-entered by upstream loops


def _q(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _env() -> str:
    """Fabro command nodes do not inherit the Forge-C environment: pass code and data locations explicitly
    (r47: the SWE.2 gate could not find the pinned PlantUML jar)."""
    import os
    import shlex

    from ..common import state_dir

    pp = REPO_ROOT / "factory" / "python"
    sd = state_dir()
    root = os.environ.get("FORGE_DATA_ROOT") or str(sd.parent)
    return f"PYTHONPATH={pp} FORGE_STATE_DIR={shlex.quote(str(sd))} FORGE_DATA_ROOT={shlex.quote(root)}"


def gate_cmd(phase: str, step: str, check: str = "") -> str:
    extra = f" --check {check}" if check else ""
    return (f"{_env()} {sys.executable} -m forge_factory.inspection.gate --workspace . "
            f"--phase {phase} --step {step}{extra}")


def author_prompt(n: int) -> str:
    from .prompts import author_prompt as ap

    return ap(f"SWE.{n}")


def inspector_prompt(n: int) -> str:
    from .prompts import inspector_prompt as ip

    return ip(f"SWE.{n}")


def scaffold_cmd() -> str:
    return f"{_env()} {sys.executable} -m forge_factory.workflow.scaffold --workspace ."


def robot_scaffold_cmd() -> str:
    return f"{_env()} {sys.executable} -m forge_factory.workflow.robot_scaffold --workspace ."


def unit_scaffold_cmd() -> str:
    return f"{_env()} {sys.executable} -m forge_factory.inspection.unit_scaffold --workspace ."


def regmap_cmd() -> str:
    return f"{_env()} {sys.executable} -m forge_factory.inspection.regmap --workspace ."


def finalize_cmd(work_order: str) -> str:
    return f"{_env()} {sys.executable} -m forge_factory.release.finalize --workspace . --run-id {work_order}"


CODE_NODES = ("swe3_ll_author", "swe3_hal_author", "swe3_fix_author", "swe3_author", "swe4_test_author", "swe4_author",
              "swe5_target_author", "swe6_test_author")
MODEL_ATTR = "model"  # Fabro 0.362 per-node model attribute (live-verified, ADR-0005 #15)


def build(work_order: str, phases: list[str] | None = None, goal: str | None = None,
          sections: dict[str, str] | None = None, code_model: str | None = None,
          chunk_lines: int = 40, layer: str = "LL+HAL", trace: bool = False,
          isolation: bool = False, brownfield: str | None = None) -> tuple[str, dict]:
    """`code_model`: optional local model for the C code/test author nodes only (trial profile, ADR-0005 #15).
    `chunk_lines`: max lines per write/edit call (40 for local models whose long tool calls are dropped)."""
    from . import prompts

    prompts.CHUNK["lines"] = chunk_lines
    prompts.LAYER["layer"] = layer  # ADR-0009: LL | HAL | LL+HAL
    prompts.TRACE["on"] = trace  # owner addendum 2026-10-17: trace rules for work orders with the trace profile
    prompts.ISOLATION["on"] = isolation and layer == "HAL"  # CAPA-038: HAL unit tests on the generated LL test double
    prompts.BROWNFIELD["mode"] = brownfield  # feature 008: delivered code (FROZEN | FIX_ALLOWED), None = greenfield
    dot, nodes = _build(work_order, phases, goal, sections)
    if code_model:
        for n in CODE_NODES:
            if n in nodes:
                dot = dot.replace(f"  {n} [label=", f'  {n} [{MODEL_ATTR}="{_q(code_model)}", label=', 1)
                nodes[n] = {**nodes[n], "model": code_model}
    return dot, nodes


def _build(work_order: str, phases: list[str] | None = None, goal: str | None = None,
           sections: dict[str, str] | None = None) -> tuple[str, dict]:
    from . import prompts

    prompts.SECTIONS.clear()
    prompts.SECTIONS.update(sections or {})
    phases = phases or PHASES
    nodes: dict[str, dict] = {}
    L = [f'digraph ForgeC_{work_order.replace("-", "_")} {{',
         f'  graph [goal="{_q(goal or "Forge-C v0.4 unattended SWE.1-SWE.6 candidate for offline review")}", '
         f'default_fidelity="compact", loop_restart_signature_limit="8"]',
         '  start [shape=Mdiamond, label="Start"]', '  exit [shape=Msquare, label="Exit (offline review package)"]',
         f'  finalize [shape=parallelogram, label="Deterministic finalizer (READY_FOR_OFFLINE_REVIEW|BLOCKED)", '
         f'script="{_q(finalize_cmd(work_order))}"]']
    # All six phases are always in the graph so that upstream loops (ADR-0008) can reach phases a resumed run
    # carried over; `start` enters at the first phase still to run.
    restart = phases[0]
    prev = "start"
    for phase in PHASES:
        n = int(phase[-1])
        a, ag, ins, ig, rt = (f"swe{n}_author", f"swe{n}_author_gate", f"swe{n}_inspector", f"swe{n}_inspect_gate",
                              f"swe{n}_route")
        nodes[a] = {"role": f"swe{n}-author", "phase": phase}
        nodes[ins] = {"role": f"swe{n}-inspector", "phase": phase}
        L += [f'  {a} [label="{phase} author", max_visits={MAX_VISITS}, timeout="1500s", prompt="{_q(author_prompt(n))}"]',
              f'  {ag} [shape=parallelogram, label="{phase} freeze gate", stdin_source="context.response.{a}", '
              f'script="{_q(gate_cmd(phase, "author"))}"]',
              f'  {ins} [label="{phase} inspector", max_visits={MAX_VISITS}, timeout="900s", prompt="{_q(inspector_prompt(n))}"]',
              f'  {ig} [shape=parallelogram, label="{phase} inspection gate", stdin_source="context.response.{ins}", '
              f'script="{_q(gate_cmd(phase, "inspect"))}"]',
              f'  {rt} [shape=parallelogram, label="{phase} bounded rework router", '
              f'script="{_q(gate_cmd(phase, "route"))}"]']
        entry = a
        if phase == "SWE.3":  # LL header in its own fresh context first; rework re-enters at the HAL author
            from .prompts import fix3_author_prompt, hal_author_prompt, ll_author_prompt

            layer = prompts.LAYER["layer"]
            regmap, ll, hal, fix = "swe3_regmap", "swe3_ll_author", "swe3_hal_author", "swe3_fix_author"
            # ADR-0009: LL layer = regmap + LL author; HAL layer = HAL author on the PROVIDED LL (no regmap: the
            # provided header is frozen); legacy LL+HAL = both authors
            chain = {"LL": [regmap, ll], "HAL": [hal], "LL+HAL": [regmap, ll, hal]}[layer] + [fix]
            units = "swe3_units"  # CAPA-028/029: deterministic unit-spec/design/MISRA scaffold (trace profile only)
            if prompts.TRACE["on"]:
                chain = chain + [units]
            check = "swe3_delivery_check"
            if prompts.BROWNFIELD["mode"]:  # feature 008: no code generator or code author; the fix node is rework only
                chain = [check]
            entry = chain[0]
            for n_ in chain:
                if n_ not in (regmap, units):
                    nodes[n_] = {"role": "swe3-author", "phase": phase}
            spec = {regmap: f'  {regmap} [shape=parallelogram, label="SWE.3 register map generator (RM0486, '
                            f'deterministic)", script="{_q(regmap_cmd())}"]',
                    ll: f'  {ll} [label="SWE.3 LL author", max_visits={ONCE}, timeout="900s", '
                        f'prompt="{_q(ll_author_prompt())}"]',
                    hal: f'  {hal} [label="SWE.3 HAL author", max_visits={ONCE}, timeout="1200s", '
                         f'prompt="{_q(hal_author_prompt())}"]',
                    fix: f'  {fix} [label="SWE.3 fix author (compile + deterministic checks)", '
                         f'max_visits={MAX_VISITS}, timeout="1500s", prompt="{_q(fix3_author_prompt())}"]',
                    units: f'  {units} [shape=parallelogram, label="SWE.3 unit specification and design scaffold '
                           f'(deterministic)", script="{_q(unit_scaffold_cmd())}"]',
                    check: f'  {check} [shape=parallelogram, label="SWE.3 delivered code check, trace-map seed '
                           f'(deterministic)", script="{_q(gate_cmd(phase, "verify", "delivery_check"))}"]'}
            if prompts.BROWNFIELD["mode"]:
                nodes[fix] = {"role": "swe3-author", "phase": phase}
                L += [spec[check], spec[fix], f'  {check} -> {a} [condition="outcome=succeeded"]',
                      f"  {check} -> finalize", f"  {fix} -> {a}"]
            else:
                L += [spec[n_] for n_ in chain] + [f"  {x} -> {y}" for x, y in zip(chain, chain[1:] + [a], strict=True)]
        if phase == "SWE.4":  # unit tests written in their own fresh context; rework re-enters at the SWE.4 author
            from .prompts import unit_test_author_prompt

            entry, ut = "swe4_scaffold", "swe4_test_author"
            nodes[ut] = {"role": "swe4-author", "phase": phase}
            L += [f'  {entry} [shape=parallelogram, label="SWE.4 unit-test harness generator (deterministic)", '
                  f'script="{_q(scaffold_cmd())}"]',
                  f'  {ut} [label="SWE.4 unit-test author", max_visits={ONCE}, timeout="1200s", '
                  f'prompt="{_q(unit_test_author_prompt())}"]', f"  {entry} -> {ut}", f"  {ut} -> {a}"]
        if phase == "SWE.5":  # Renode target tests in their own budget; rework re-enters at the SWE.5 author
            from .prompts import target_test_author_prompt

            entry = "swe5_target_author"
            nodes[entry] = {"role": "swe5-author", "phase": phase}
            L += [f'  {entry} [label="SWE.5 target-test author (Renode)", max_visits={ONCE}, timeout="1500s", '
                  f'prompt="{_q(target_test_author_prompt())}"]', f"  {entry} -> {a}"]
        if phase == "SWE.6":  # r56: Robot requirement tests in their own budget; rework re-enters at the SWE.6 author
            from .prompts import robot_test_author_prompt

            entry, ta = "swe6_scaffold", "swe6_test_author"  # r59: suite skeleton generated from the SWE.1 baseline
            nodes[ta] = {"role": "swe6-author", "phase": phase}
            L += [f'  {entry} [shape=parallelogram, label="SWE.6 Robot suite generator (deterministic)", '
                  f'script="{_q(robot_scaffold_cmd())}"]',
                  f'  {ta} [label="SWE.6 Robot test author (Renode)", max_visits={ONCE}, timeout="1500s", '
                  f'prompt="{_q(robot_test_author_prompt())}"]', f"  {entry} -> {ta}", f"  {ta} -> {a}"]
        if prev != "start" and prompts.BROWNFIELD["mode"] and phase == "SWE.2":
            # feature 008 (FR-007): the delivered code enters only after SWE.1 is frozen and inspected
            inj = "delivery_inject"
            L += [f'  {inj} [shape=parallelogram, label="Delivered code injected after SWE.1 (deterministic)", '
                  f'script="{_q(gate_cmd("SWE.1", "verify", "delivery_inject"))}"]',
                  f'  {prev} -> {inj} [condition="outcome=succeeded"]',
                  f'  {inj} -> {entry} [condition="outcome=succeeded"]', f"  {inj} -> finalize"]
        elif prev != "start":
            L.append(f'  {prev} -> {entry} [condition="outcome=succeeded"]')
        if phase == restart:
            L.append(f"  start -> {entry}")
        L.append(f"  {a} -> {ag}")
        if phase == "SWE.3":
            v = "swe3_verify"
            vcheck = "delivery" if prompts.BROWNFIELD["mode"] else "hal_guideline"
            L.append(f'  {v} [shape=parallelogram, label="SWE.3 {"delivered code" if vcheck == "delivery" else "HAL guideline"} '
                     f'verification node", script="{_q(gate_cmd(phase, "verify", vcheck))}"]')
            L += [f'  {ag} -> {v} [condition="outcome=succeeded"]', f'  {ag} -> {rt}',
                  f'  {v} -> {ins} [condition="outcome=succeeded"]', f'  {v} -> {rt}']
        else:
            L += [f'  {ag} -> {ins} [condition="outcome=succeeded"]', f'  {ag} -> {rt}']
        L += [f"  {ins} -> {ig}", f'  {ig} -> {rt}',
              f'  {rt} -> {"swe3_fix_author" if phase == "SWE.3" else a} [condition="outcome=succeeded"]',
              f'  {rt} -> upstream_swe1']
        prev = ig
    # ADR-0008 shared upstream chain (probe P1: outcome-only routing): earliest owner first, then the finalizer.
    # L12: the owner triages first (accept / reject_defect, no edits); a fully rejected loop returns to the phase
    # that reported it through the return chain, so nothing upstream is re-frozen (r70 cascade).
    from .prompts import triage_prompt

    for k, owner in ((1, "swe1_author"), (2, "swe2_author"), (3, "swe3_fix_author")):
        up, nxt = f"upstream_swe{k}", (f"upstream_swe{k + 1}" if k < 3 else "finalize")
        tri, tg = f"swe{k}_triage", f"swe{k}_triage_gate"
        nodes[tri] = {"role": f"swe{k}-author", "phase": f"SWE.{k}"}
        L += [f'  {up} [shape=parallelogram, label="Upstream loop to SWE.{k} (open defect, loop budget)", '
              f'script="{_q(gate_cmd(f"SWE.{k}", "upstream"))}"]',
              f'  {tri} [label="SWE.{k} defect triage (accept or reject, no edits)", max_visits={ONCE}, '
              f'timeout="600s", prompt="{_q(triage_prompt(k))}"]',
              f'  {tg} [shape=parallelogram, label="SWE.{k} triage gate (fix | return)", '
              f'script="{_q(gate_cmd(f"SWE.{k}", "triage"))}"]',
              f'  {up} -> {tri} [condition="outcome=succeeded"]', f"  {up} -> {nxt}", f"  {tri} -> {tg}",
              f'  {tg} -> {owner} [condition="outcome=succeeded"]', f"  {tg} -> return_swe2"]
    for n in range(2, 7):
        ret, nxt = f"return_swe{n}", (f"return_swe{n + 1}" if n < 6 else "finalize")
        entry = "swe3_fix_author" if n == 3 else f"swe{n}_author"
        L += [f'  {ret} [shape=parallelogram, label="Return to SWE.{n} (its defects were rejected)", '
              f'script="{_q(gate_cmd(f"SWE.{n}", "return"))}"]',
              f'  {ret} -> {entry} [condition="outcome=succeeded"]', f"  {ret} -> {nxt}"]
    nodes["release_manager"] = {"role": "release-manager"}
    L += ['  release_manager [label="Release Manager (inventory only)", max_visits=1, prompt="Call use_skill with '
          'skill_name release-manager and follow it. Final reply: compact JSON only."]',
          f'  {prev} -> release_manager [condition="outcome=succeeded"]',
          "  release_manager -> finalize", "  finalize -> exit", "}"]
    return "\n".join(L) + "\n", nodes


def binding_for(work_order: str, workspace: str, nodes: dict) -> Binding:
    return Binding(work_order, workspace, nodes)
