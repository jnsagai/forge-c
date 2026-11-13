"""Feature 017 FR-032/SC-012: the model service is factory-agnostic.

(a) nothing under ``model_tier`` imports ``forge_factory``; (b) its schema copies are byte-identical to
``config/schemas/model-service``; (c) no model_tier source uses factory concepts as configuration keys.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MT = ROOT / "factory/python/model_tier"
MT_SCHEMAS = MT / "schemas"
CFG_SCHEMAS = ROOT / "config/schemas/model-service"
FACTORY_KEY = re.compile(r"\b(work_order|workorder|run_id|node_id|lane)\b")
_FORGE = re.compile(r"^forge_factory(\.|$)")
_KEY_METHODS = {"get", "setdefault", "pop"}


def sources() -> list[Path]:
    return sorted(p for p in MT.rglob("*.py") if "__pycache__" not in p.parts)


def forge_imports(tree: ast.AST) -> list[str]:
    """Imports (absolute or relative) of forge_factory, plus dynamic imports by string constant."""
    bad = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            bad += [a.name for a in n.names if _FORGE.match(a.name)]
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            if _FORGE.match(mod) or (not mod and any(_FORGE.match(a.name) for a in n.names)):
                bad.append(mod or ",".join(a.name for a in n.names))
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and _FORGE.match(n.value):
            bad.append(n.value)
    return bad


def factory_keys(tree: ast.AST) -> list[str]:
    """String constants used as dict keys, subscript keys or ``.get/.setdefault/.pop`` keys that name factory concepts."""
    keys: list[ast.AST] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            keys += [k for k in n.keys if k is not None]
        elif isinstance(n, ast.Subscript):
            keys.append(n.slice)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _KEY_METHODS and n.args:
            keys.append(n.args[0])
    return [k.value for k in keys if isinstance(k, ast.Constant) and isinstance(k.value, str) and FACTORY_KEY.search(k.value)]


def test_model_tier_has_sources():
    names = {p.name for p in sources()}
    assert {"gpu.py", "ramstage.py", "neighbour.py"} <= names


@pytest.mark.parametrize("path", sources(), ids=lambda p: str(p.relative_to(MT)))
def test_no_forge_factory_import(path):
    assert forge_imports(ast.parse(path.read_text(), str(path))) == []


@pytest.mark.parametrize("path", sources(), ids=lambda p: str(p.relative_to(MT)))
def test_no_factory_concept_keys(path):
    assert factory_keys(ast.parse(path.read_text(), str(path))) == []


def test_schema_copies_identical():
    mt = {p.name for p in MT_SCHEMAS.iterdir() if p.is_file()}
    cfg = {p.name for p in CFG_SCHEMAS.iterdir() if p.is_file()}
    assert mt and mt == cfg
    differ = [n for n in sorted(mt) if (MT_SCHEMAS / n).read_bytes() != (CFG_SCHEMAS / n).read_bytes()]
    assert differ == []


@pytest.mark.parametrize("src", [
    "import forge_factory", "import forge_factory.modelservice as m", "from forge_factory import x",
    "from forge_factory.modelservice.client import C", "from .. import forge_factory", "importlib.import_module('forge_factory.x')",
])
def test_import_scanner_catches(src):
    assert forge_imports(ast.parse(src))


@pytest.mark.parametrize("src", ["import forge_factoryish", "from . import identity", "x = 'forge-factory'"])
def test_import_scanner_allows(src):
    assert forge_imports(ast.parse(src)) == []


@pytest.mark.parametrize("src", ["d = {'run_id': 1}", "x = cfg['lane']", "cfg.get('work_order')", "d.setdefault('node_id', 0)",
                                 "d = {'workorder': 1}"])
def test_key_scanner_catches(src):
    assert factory_keys(ast.parse(src))


@pytest.mark.parametrize("src", ["d = {'tenant': 1, 'lanes_total': 2}", "x = cfg['model']", "'''docstring about a lane and run_id'''",
                                 "print('lane')"])
def test_key_scanner_allows(src):
    assert factory_keys(ast.parse(src)) == []
