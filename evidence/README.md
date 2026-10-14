# Evidence directory

This directory deliberately has no production evidence. Populate from **real tool invocations** and authenticated review records for a particular build/driver/baseline.

Mandatory files for the example quality gate:
- `metrics.json` matching `templates/metrics.example.json` (real hardware/ELF evidence)
- `trace.json` matching `templates/trace.example.json` (approved links)
- `checks.json` matching `templates/checks.example.json` (tool and reviewer evidence)

Until verified real inputs exist, the factory must fail with `RELEASE_BLOCKED`.
