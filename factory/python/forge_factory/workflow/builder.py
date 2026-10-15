"""T009/T046/T047 — generate the v0.4 unattended SWE.1–SWE.6 Fabro workflow (DOT) + run binding.

Graph per phase n:  (SWE.3: swe3_ll_author ->) swe{n}_author -> swe{n}_author_gate -[ok]->
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

MAX_VISITS = 4  # 1 + maximum_rework_cycles (3) from the v0.3 checklists


def _q(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def gate_cmd(phase: str, step: str, check: str = "") -> str:
    pp = REPO_ROOT / "factory" / "python"
    extra = f" --check {check}" if check else ""
    return (f"PYTHONPATH={pp} {sys.executable} -m forge_factory.inspection.gate --workspace . "
            f"--phase {phase} --step {step}{extra}")


def author_prompt(n: int) -> str:
    from .prompts import author_prompt as ap

    return ap(f"SWE.{n}")


def inspector_prompt(n: int) -> str:
    from .prompts import inspector_prompt as ip

    return ip(f"SWE.{n}")


def finalize_cmd(work_order: str) -> str:
    pp = REPO_ROOT / "factory" / "python"
    return f"PYTHONPATH={pp} {sys.executable} -m forge_factory.release.finalize --workspace . --run-id {work_order}"


def build(work_order: str, phases: list[str] | None = None, goal: str | None = None,
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
    prev = "start"
    for phase in phases:
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
            from .prompts import ll_author_prompt

            entry = "swe3_ll_author"
            nodes[entry] = {"role": "swe3-author", "phase": phase}
            L += [f'  {entry} [label="SWE.3 LL author", max_visits=1, timeout="900s", prompt="{_q(ll_author_prompt())}"]',
                  f"  {entry} -> {a}"]
        L.append(f"  {prev} -> {entry}" + (' [condition="outcome=succeeded"]' if prev != "start" else ""))
        L.append(f"  {a} -> {ag}")
        if phase == "SWE.3":
            v = "swe3_verify"
            L.append(f'  {v} [shape=parallelogram, label="SWE.3 HAL guideline verification node", '
                     f'script="{_q(gate_cmd(phase, "verify", "hal_guideline"))}"]')
            L += [f'  {ag} -> {v} [condition="outcome=succeeded"]', f'  {ag} -> {rt}',
                  f'  {v} -> {ins} [condition="outcome=succeeded"]', f'  {v} -> {rt}']
        else:
            L += [f'  {ag} -> {ins} [condition="outcome=succeeded"]', f'  {ag} -> {rt}']
        L += [f"  {ins} -> {ig}", f'  {ig} -> {rt}',
              f'  {rt} -> {a} [condition="outcome=succeeded"]', f'  {rt} -> finalize']
        prev = ig
    nodes["release_manager"] = {"role": "release-manager"}
    L += ['  release_manager [label="Release Manager (inventory only)", max_visits=1, prompt="Call use_skill with '
          'skill_name release-manager and follow it. Final reply: compact JSON only."]',
          f'  {prev} -> release_manager [condition="outcome=succeeded"]',
          "  release_manager -> finalize", "  finalize -> exit", "}"]
    return "\n".join(L) + "\n", nodes


def binding_for(work_order: str, workspace: str, nodes: dict) -> Binding:
    return Binding(work_order, workspace, nodes)
