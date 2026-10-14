PYTHON ?= python3
.PHONY: test profile release-gate

test:
	$(PYTHON) -m unittest discover -s tests -v

profile:
	$(PYTHON) tools/validate_profile.py profiles/stm32n6-rcc-pilot.json

release-gate:
	$(PYTHON) tools/quality_gate.py --profile profiles/stm32n6-rcc-pilot.json --trace evidence/trace.json --metrics evidence/metrics.json --checks evidence/checks.json

# ---- Forge-C v0.4 factory (T003) ----
FACTORY_ENV = . scripts/forge-env.sh &&
.PHONY: factory-bootstrap factory-test factory-lint factory-typecheck factory-cov design-check
factory-bootstrap:
	$(FACTORY_ENV) ./scripts/bootstrap_factory.sh "$$FORGE_VENV"
factory-test:
	$(FACTORY_ENV) python -m pytest factory/python/tests
factory-lint:
	$(FACTORY_ENV) ruff check factory/python
factory-typecheck:
	$(FACTORY_ENV) mypy factory/python/forge_factory
factory-cov:
	$(FACTORY_ENV) python -m pytest factory/python/tests --cov=forge_factory --cov-report=term-missing:skip-covered
design-check:
	$(FACTORY_ENV) python tests/spec/validate_design.py
