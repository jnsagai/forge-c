"""Feature 009 FR-002 / PG-T006: the RCC work orders produce byte-identical workflow graphs and register-map output
after the peripheral refactor (goldens captured before it, tests/fixtures/peripheral/rcc_golden.json)."""
import hashlib
import json
from pathlib import Path

from forge_factory.common import REPO_ROOT
from peripheral_golden import graph_hashes

GOLD = json.loads((Path(__file__).parent / "fixtures/peripheral/rcc_golden.json").read_text())
RM = REPO_ROOT / "examples/0002-arm_55_rcc_st/inputs/RM0486-rev4-ch14-rcc.md"
ARCH = Path(__file__).parent / "fixtures/brownfield/r170/software_architecture.md"


def test_rcc_workflow_graphs_unchanged():
    assert graph_hashes() == {k: v for k, v in GOLD.items() if k.startswith("graph:")}


def test_rcc_register_map_generation_unchanged(tmp_path):
    from forge_factory.inspection import regmap
    from forge_factory.workorder import split_sections

    files, _ = split_sections(RM.read_text(), "RM0486")
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    (tmp_path / "workproducts/SWE.2").mkdir(parents=True)
    (tmp_path / "workproducts/SWE.2/software_architecture.md").write_text(ARCH.read_text())
    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    regmap.generate(tmp_path)
    for rel in ("software/ll/stm32n6xx_ll_rcc.h", "software/src/stm32n6xx_ll_rcc.c"):
        assert hashlib.sha256((tmp_path / rel).read_bytes()).hexdigest() == GOLD[f"regmap:{rel}"], rel
