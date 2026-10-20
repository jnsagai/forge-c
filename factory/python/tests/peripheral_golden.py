"""RCC golden outputs for feature 009 (captured on feat/008 0219f0d+77fe4cf before the peripheral refactor): the RCC
workflow graphs and the regenerated RCC register-map header must stay byte-identical (FR-002)."""
import hashlib
import sys

from forge_factory.workflow import builder

GRAPHS = {"ll": dict(layer="LL", trace=True), "hal": dict(layer="HAL", trace=True, isolation=True),
          "ll_brownfield": dict(layer="LL", trace=True, brownfield="FROZEN"),
          "hal_fix_allowed": dict(layer="HAL", trace=True, isolation=True, brownfield="FIX_ALLOWED"), "legacy": dict()}


def normalized_graph(**kw) -> str:
    g, _ = builder.build("WO-GOLD", chunk_lines=150, **kw)
    return g.replace(builder._env(), "<ENV>").replace(sys.executable, "<PY>")


def graph_hashes() -> dict[str, str]:
    return {f"graph:{k}": hashlib.sha256(normalized_graph(**kw).encode()).hexdigest() for k, kw in GRAPHS.items()}
