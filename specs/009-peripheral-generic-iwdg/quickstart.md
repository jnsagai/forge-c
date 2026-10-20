# Quickstart: Peripheral-generic factory

```bash
cd /home/jefferson/forge-c && . scripts/forge-env.sh
export PYTHONPATH=$PWD/factory/python:$PWD/factory/python/tests
python -m pytest -q -p no:cacheprovider factory/python/tests/test_peripheral_*.py
```

These tests check:
- the RCC equivalence (graphs, scaffolds and generated register maps unchanged);
- that the IWDG chapter parses into 7 registers with multi-bit fields;
- the profile validation;
- the register-contract `write` op.

**IWDG intake** (no agents):

```bash
python -m forge_factory.workorder --example examples/0009a-iwdg-ll --wo WO-0009A-INTAKE --intake-only
```

Expected: the manifest records `peripheral: iwdg` and the profile hash, and the generated prompts and file names
mention no RCC identifier.
