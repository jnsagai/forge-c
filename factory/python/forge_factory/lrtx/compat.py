"""LRTX-T004 (ADR-0013 compatibility): executable fixtures of the existing workflow/provider combinations.

    python factory/python/forge_factory/lrtx/compat.py --src <checkout> --out <fixtures.json>   # generate
    python factory/python/forge_factory/lrtx/compat.py --src <checkout> --compare <fixtures.json>

Runs as a plain script in a fresh process against the factory code of `--src` (the preserved baseline checkout or
the development tree): it imports only functions that exist at the baseline SHA (workflow builder, ACP attach, run
config rendering, model profile, MCP preflight in its static mode), so the same file freezes the baseline and checks
the candidate. Nothing is launched or written outside a temporary state directory. Normalization replaces only
machine-specific paths (checkout root, interpreter, state/data roots, workspace); every other byte is compared.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

# (example, work order id, provided LL needed) - greenfield LL/HAL RCC, brownfield FROZEN/FIX_ALLOWED/ST, IWDG LL/HAL
CASES = [("0002a-arm_55_rcc_ll", "WO-COMPAT-RCC-LL"), ("0002b-arm_55_rcc_hal", "WO-COMPAT-RCC-HAL"),
         ("0008a-rcc-ll-delivered", "WO-COMPAT-BF-LL"), ("0008b-rcc-hal-delivered", "WO-COMPAT-BF-HAL"),
         ("0008c-st-cube-rcc", "WO-COMPAT-ST"), ("0009a-iwdg-ll", "WO-COMPAT-IWDG-LL"),
         ("0009b-iwdg-hal", "WO-COMPAT-IWDG-HAL")]
# legacy default (local qwen3:8b, no ACP) | Codex authors | Codex authors + Claude inspectors (current production line)
VARIANTS = {"default": {"model": "qwen3:8b", "provider": "ollama", "acp_authors": False, "acp_inspectors": False},
            "acp_authors": {"model": "deepseek-flash", "provider": "deepseek", "acp_authors": True,
                            "acp_inspectors": False},
            "acp_both": {"model": "deepseek-flash", "provider": "deepseek", "acp_authors": True,
                         "acp_inspectors": True}}
WS = "/WORKSPACE"


def _sections(example: Path, spec: dict, split_sections) -> dict[str, str]:
    """The `inputs/index.md` section map workorder.prepare builds (RM documents split per section)."""
    lines: list[str] = []
    for item in spec["inputs"]:
        name = Path(item["path"]).name
        if name.startswith("RM") and name.endswith(".md"):
            lines += split_sections((example / item["path"]).read_text(encoding="utf-8"), name.split("-")[0])[1]
    secmap: dict[str, str] = {}
    for line in lines:
        parts = [x.strip() for x in line.split(" | ")]
        if len(parts) == 4 and parts[0][:1].isdigit() and parts[0] not in secmap:
            secmap[parts[0]] = parts[3]
    return secmap


def generate(src: Path) -> dict:
    src = src.resolve()
    sys.path.insert(0, str(src / "factory/python"))
    tmp = tempfile.mkdtemp(prefix="lrtx-compat-")
    # the checkout under test, not an inherited FORGE_REPO_ROOT; PATH is environmental (run-config MCP env)
    os.environ.update({"FORGE_STATE_DIR": f"{tmp}/state", "FORGE_DATA_ROOT": f"{tmp}/data", "FORGE_REPO_ROOT": str(src),
                       "PATH": "/usr/bin:/bin"})
    import forge_factory
    from forge_factory import acp, workorder

    if Path(forge_factory.__file__).resolve().parents[3] != src:
        raise RuntimeError(f"COMPAT_WRONG_SOURCE:{forge_factory.__file__} is not under {src}")
    from forge_factory.fabro.runconfig import render_run_toml
    from forge_factory.layer import HAL_UNIT_ISOLATION, TRACE_PROFILE  # noqa: F401 - both exist at the baseline
    from forge_factory.mcp.preflight import fabro_mcp_config
    from forge_factory.mcp.preflight import preflight as mcp_preflight
    from forge_factory.workflow.builder import binding_for, build

    repl = [(str(src), "<REPO>"), (sys.executable, "<PYTHON>"), (tmp, "<TMP>"), (WS, "<WS>")]

    def norm(text: str) -> str:
        for a, b in repl:
            text = text.replace(a, b)
        return text

    out: dict[str, dict] = {}
    for ex_name, wo in CASES:
        example = src / "examples" / ex_name
        spec = json.loads((example / "workorder.json").read_text())
        layer = spec.get("layer", "LL+HAL")
        delivery = spec.get("delivery") or {}
        secmap = _sections(example, spec, workorder.split_sections)
        for vname, v in VARIANTS.items():
            graph, nodes = build(wo, goal=f"{spec['driver']} (compat fixture)", sections=secmap,
                                 chunk_lines=40 if v["provider"] == "ollama" else 150, layer=layer, trace=True,
                                 isolation=layer == "HAL", brownfield=delivery.get("code_mode"),
                                 peripheral=spec.get("peripheral"),
                                 delivery_style=(delivery.get("build") or {}).get("style"))
            prof = workorder.model_profile(v["model"], v["provider"], None, nodes)
            converted: dict[str, list[str]] = {}
            if v["acp_authors"]:
                graph, converted["authors"] = acp.attach(graph, nodes, Path(WS))
            if v["acp_inspectors"]:
                graph, converted["inspectors"] = acp.attach(graph, nodes, Path(WS), roles=acp.NON_AUTHOR_ROLES,
                                                            agent="claude")
            roles = sorted({n["role"] for n in nodes.values()})
            servers = mcp_preflight(roles, live=False)["servers"]
            binding = binding_for(wo, WS, nodes)
            toml = render_run_toml("workflow.fabro", f"{wo} {spec['driver']}", Path(WS) / ".forge-run/binding.json",
                                   fabro_mcp_config(servers), model=v["model"], binding_id=binding.binding_id,
                                   provider=v["provider"])
            g = norm(graph)
            out[f"{ex_name}/{vname}"] = {
                "graph_sha256": hashlib.sha256(g.encode()).hexdigest(), "graph": g,
                "nodes": json.loads(norm(json.dumps(nodes, sort_keys=True))),
                "native_agent_nodes": acp.native_agent_nodes(graph), "acp_converted": converted,
                "binding": {"binding_id": binding.binding_id, "workspace": norm(binding.workspace)},
                "run_toml": norm(toml), "mcp_servers": servers,
                "model_profile": json.loads(norm(json.dumps(prof, sort_keys=True)))}
    return out


def compare(expected: dict, actual: dict) -> list[str]:
    diffs = []
    for key in sorted(set(expected) | set(actual)):
        if key not in actual or key not in expected:
            diffs.append(f"{key}: {'missing' if key not in actual else 'unexpected'}")
            continue
        for field in sorted(set(expected[key]) | set(actual[key])):
            if expected[key].get(field) != actual[key].get(field):
                diffs.append(f"{key}:{field}")
    return diffs


def load(path: Path) -> dict:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def dump(data: dict, path: Path) -> None:
    text = (json.dumps(data, indent=1, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(text, mtime=0) if path.suffix == ".gz" else text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--out", type=Path)
    g.add_argument("--compare", type=Path)
    a = ap.parse_args(argv)
    data = generate(a.src)
    if a.out:
        dump(data, a.out)
        print(json.dumps({"status": "WRITTEN", "cases": len(data), "out": str(a.out)}))
        return 0
    diffs = compare(load(a.compare), data)
    print(json.dumps({"status": "PASS" if not diffs else "FAIL", "cases": len(data), "diffs": diffs[:50]}))
    return 0 if not diffs else 1


if __name__ == "__main__":
    raise SystemExit(main())
