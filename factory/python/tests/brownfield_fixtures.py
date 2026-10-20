"""Feature 008 test fixtures: brownfield work orders prepared from example 0008a (the r170 LL code delivered back)
and the r170 SWE.1/SWE.2 contract work products (tests/fixtures/brownfield/r170)."""
import json
import re
import shutil
from pathlib import Path

from forge_factory.common import REPO_ROOT

EX = REPO_ROOT / "examples/0008a-rcc-ll-delivered"
FIX = Path(__file__).parent / "fixtures/brownfield/r170"
HEADER = (EX / "delivery/stm32n6xx_ll_rcc.h").read_text()
SCOPE = json.loads((EX / "workorder.json").read_text())["delivery"]["scope"]["functions"]


def example_copy(tmp: Path, *, header: str | None = None, mutate=None, name: str = "ex") -> Path:
    """A copy of example 0008a (optionally with another header or a mutated spec) in tmp."""
    ex = tmp / name
    shutil.copytree(EX, ex)
    spec = json.loads((ex / "workorder.json").read_text())
    for item in spec["inputs"]:  # inputs are relative to the original example directory
        item["path"] = str((EX / item["path"]).resolve())
    if header is not None:
        (ex / "delivery/stm32n6xx_ll_rcc.h").write_text(header)
    if mutate:
        mutate(spec)
    (ex / "workorder.json").write_text(json.dumps(spec, indent=1))
    return ex


def pass_swe1(monkeypatch):
    """Pretend SWE.1 is frozen and inspected PASS (the inject node's precondition)."""
    from forge_factory.inspection import engine

    monkeypatch.setattr(engine.Store, "gate", lambda self, ph: {"decision": "PASS"})
    monkeypatch.setattr(engine.Store, "latest_baseline",
                        lambda self, ph: {"baseline_id": f"BL-{ph}-001", "baseline_hash": "h" * 64})


def add_contract(ws: Path) -> None:
    """The r170 SWE.1 register effects and SWE.2 api calls / architecture, as frozen work products."""
    for d, n in (("workproducts/SWE.1", "register_effects.json"), ("workproducts/SWE.2", "api_calls.json"),
                 ("workproducts/SWE.2", "software_architecture.md")):
        (ws / d).mkdir(parents=True, exist_ok=True)
        shutil.copy(FIX / n, ws / d / n)


def body(header: str, fn: str) -> str:
    return re.search(rf"static inline [^\n]*\b{fn}\(void\)\n\{{\n(.*?)\n\}}", header, re.S).group(1)


def remove_function(header: str, fn: str) -> str:
    start = header.find(f"static inline uint32_t {fn}(") if f"uint32_t {fn}(" in header else \
        header.find(f"static inline void {fn}(")
    end = header.find("}\n", start) + 2
    return header[:start] + header[end:]


MUTANTS = {
    "wrong_mask": (lambda h: h.replace(body(h, "LL_RCC_HSI_Enable"),
                                       body(h, "LL_RCC_HSI_Enable").replace("HSION_MSK", "HSEON_MSK"), 1),
                   None, "CONTRADICTION", "LL_RCC_HSI_Enable"),
    "missing_function": (lambda h: remove_function(h, "LL_RCC_HSE_IsReady"), "LL_RCC_HSE_IsReady", "NO_CODE",
                         "LL_RCC_HSE_IsReady"),
    "extra_function": (lambda h: h.replace("#endif", "static inline void LL_RCC_MSI_Enable(void)\n{\n    ll_rcc_regs["
                                           "LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_MSION_MSK;\n}\n#endif"),
                       "+LL_RCC_MSI_Enable", "NO_REQUIREMENT", "LL_RCC_MSI_Enable"),
    "wrong_register": (lambda h: h.replace(body(h, "LL_RCC_GPDMA1_Enable"), body(h, "LL_RCC_GPDMA1_Enable")
                                           .replace("AHB1ENR_OFFSET", "AHB1RSTR_OFFSET")
                                           .replace("AHB1ENR_GPDMA1EN_MSK", "AHB1RSTR_GPDMA1RST_MSK"), 1),
                       None, "CONTRADICTION", "LL_RCC_GPDMA1_Enable"),
    "overwritten_bit": (lambda h: h.replace(body(h, "LL_RCC_HSI_Enable"),
                                            body(h, "LL_RCC_HSI_Enable").replace("|=", "="), 1),
                        None, "CONTRADICTION", "LL_RCC_HSI_Enable"),
}


def scope_for(change: str | None) -> list[str]:
    if change is None:
        return list(SCOPE)
    if change.startswith("+"):
        return SCOPE + [change[1:]]
    return [f for f in SCOPE if f != change]
