PYTHON ?= python3
.PHONY: test profile release-gate

test:
	$(PYTHON) -m unittest discover -s tests -v

profile:
	$(PYTHON) tools/validate_profile.py profiles/stm32n6-rcc-pilot.json

release-gate:
	$(PYTHON) tools/quality_gate.py --profile profiles/stm32n6-rcc-pilot.json --trace evidence/trace.json --metrics evidence/metrics.json --checks evidence/checks.json
