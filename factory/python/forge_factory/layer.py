"""ADR-0009 — driver layer of a work order: `LL` (header-only register access), `HAL` (on a PROVIDED, frozen LL
from an earlier LL work order) or the legacy combined `LL+HAL` (one run builds both).

Owner decision 2026-10-16: build LL first and HAL afterwards in separate runs, to keep each run small. The layer is
recorded in `.forge-run/manifest.json`; tools, prompts, scaffolds and inspections read it from there.
"""
from __future__ import annotations

import json
from pathlib import Path

LAYERS = ("LL", "HAL", "LL+HAL")
LL_HEADER = "software/ll/stm32n6xx_ll_rcc.h"
LL_TU = "software/src/stm32n6xx_ll_rcc.c"  # generated compile unit of the header-only LL (LL layer only)
HAL_H = "software/hal/stm32n6xx_hal_rcc.h"
HAL_C = "software/hal/stm32n6xx_hal_rcc.c"


def layer_of(ws: Path) -> str:
    try:
        v = json.loads((Path(ws) / ".forge-run/manifest.json").read_text()).get("layer") or "LL+HAL"
    except (OSError, ValueError):
        return "LL+HAL"
    return v if v in LAYERS else "LL+HAL"


TRACE_PROFILE = "owner-2026-10-17"  # EASA-OR-001..011: SWC per layer, unit specs (ReqIF), Doxygen, six matrices
HAL_UNIT_ISOLATION = "ll-fake-v1"  # CAPA-038: HAL unit tests run on a generated test double of the provided LL API
REGISTER_CONTRACT = "rc-v1"  # owner decision 2026-10-19 (option B): machine-readable register contract feeds the oracle


def hal_unit_isolation(ws: Path) -> bool:
    """HAL work orders prepared after CAPA-038 carry `hal_unit_isolation`; older runs keep the RAM register array."""
    try:
        m = json.loads((Path(ws) / ".forge-run/manifest.json").read_text())
    except (OSError, ValueError):
        return False
    return m.get("layer") == "HAL" and m.get("hal_unit_isolation") == HAL_UNIT_ISOLATION


def register_contract_enabled(ws: Path) -> bool:
    """Work orders prepared after 2026-10-19 carry `register_contract`; older runs keep the sentence-parsing oracle."""
    try:
        return json.loads((Path(ws) / ".forge-run/manifest.json").read_text()).get("register_contract") == REGISTER_CONTRACT
    except (OSError, ValueError):
        return False


def swtrace_enabled(ws: Path) -> bool:
    """Work orders prepared after the owner addendum carry `trace_profile`; older runs/fixtures keep their rules."""
    try:
        return json.loads((Path(ws) / ".forge-run/manifest.json").read_text()).get("trace_profile") == TRACE_PROFILE
    except (OSError, ValueError):
        return False


def provided(ws: Path) -> list[dict]:
    """Components provided read-only to this work order (HAL layer: the LL header), with their sha256."""
    try:
        return list(json.loads((Path(ws) / ".forge-run/manifest.json").read_text()).get("provided") or [])
    except (OSError, ValueError):
        return []


# ---- feature 009: peripheral identity from the work order's profile (RCC when the manifest names none) ---------------
def profile(ws: Path | None = None) -> dict:
    from .peripheral import load, of_ws

    return of_ws(ws) if ws is not None else load()


def ll_header(ws: Path | None = None) -> str:
    return f"software/ll/{profile(ws)['ll']['header']}"


def ll_tu(ws: Path | None = None) -> str:
    return f"software/src/{profile(ws)['ll']['compile_unit']}"


def hal_h(ws: Path | None = None) -> str:
    return f"software/hal/{profile(ws)['hal']['header']}"


def hal_c(ws: Path | None = None) -> str:
    return f"software/hal/{profile(ws)['hal']['source']}"


def register_prefix(ws: Path | None = None) -> str:
    """RM register-name prefix, e.g. RCC (RCC_CR) or IWDG (IWDG_KR)."""
    return profile(ws)["register_prefix"]


def register_block(ws: Path | None = None) -> str:
    return profile(ws)["ll"]["register_block"]


def api_header(layer: str, ws: Path | None = None) -> str:
    """The header whose functions the tests call."""
    return ll_header(ws) if layer == "LL" else hal_h(ws)


def api_prefix(layer: str, ws: Path | None = None) -> str:
    p = profile(ws)
    return p["ll"]["function_prefix"] if layer == "LL" else p["hal"]["function_prefix"]


def components(layer: str, ws: Path | None = None) -> tuple[str, ...]:
    p = profile(ws)
    ll, hal = Path(p["ll"]["header"]).stem, Path(p["hal"]["header"]).stem
    return (ll,) if layer == "LL" else (hal, ll)


def ll_measure_unit(header_text: str, ws: Path | None = None) -> str | None:
    """CAPA-013/016/018: a build-only C unit with one non-inline instance per LL static header function, whatever its
    parameter list (r84 used `(volatile uint32_t *rcc)`), so size and stack tools measure the header-only LL."""
    import re

    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", header_text, flags=re.S)
    prof = profile(ws)
    out = ["/* GENERATED measurement unit (build only): one non-inline instance per LL function */",
           f'#include "{prof["ll"]["header"]}"']
    n = 0
    fn = re.escape(prof["ll"]["function_prefix"])
    for m in re.finditer(r"static\s+(?:inline\s+)?([A-Za-z_][\w\s]*?[\w*])\s*\b(" + fn + r"\w+)\s*\(([^)]*)\)\s*\{", code):
        ret, name, params = " ".join(m.group(1).split()), m.group(2), m.group(3).strip()
        args = [] if params in ("", "void") else [
            re.search(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*$", p.strip()).group(1) for p in params.split(",")]
        call = f"{name}({', '.join(args)})"
        sig = f"{ret} forge_measure_{name}({params or 'void'})"
        out += [f"{sig};", f"{sig} {{ {'' if ret == 'void' else 'return '}{call}; }}"]
        n += 1
    return "\n".join(out) + "\n" if n else None


LL_TU_TEXT = """/* Compile unit GENERATED by forge_factory (ADR-0009) for the header-only RCC LL driver.
 * It only includes the LL header so that the compilers, static analysis and size measurement see every
 * static inline access function; it contains no driver logic. */
#include "stm32n6xx_ll_rcc.h"
"""


def ll_tu_text(ws: Path | None = None) -> str:
    p = profile(ws)
    return LL_TU_TEXT.replace("RCC LL driver", f"{p['register_prefix']} LL driver").replace(
        "stm32n6xx_ll_rcc.h", p["ll"]["header"])
