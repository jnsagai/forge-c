# Quickstart: validating factory-prepared run inputs

Prerequisites: Omniverse2 clone of `feat/019-factory-prepared-inputs`, `uv` on PATH.

1. Unit tests (no model, no line):
   `cd factory/python && uv run --frozen pytest -q -p no:cacheprovider tests/test_f019_*.py tests/test_owner_supervised_hal_lineage.py`
   Expected: derived campaign validates and equals the ladder; `after` waits without provided_from; HAL waits for
   its LL SWE.6 and builds on it; missing spec -> INPUT_GAP and later steps wait; phase growth chains SWE.2 from a
   passed SWE.1; allowance accepts only own-LL SWE.6 provided_from; floor ladder view from an audit row.
2. Regression: the allowance/campaign/planner suites; compare failures with the base commit (environment-bound
   `DURABLE_DATA_VOLUME_NOT_READY` failures are known).
3. Design check: `python3 tests/spec/validate_design.py`.
4. Deploy (owner lane): push the merge to the campaign branch; the deployer timer gates (CRE) and deploys unattended.
   Expected in the deploy record: `campaign_source: DERIVED`; in the guardian audit: `wwdg-ll` QUEUED/RUNNING at SWE.2
   with `resume_from` L44F (SC-005), `wwdg-hal` WAITING `DEPENDS_ON:wwdg-ll:SWE.6:PASS`, `spi-ll` WAITING `AFTER:...`.
5. Floor: the owner-lane panel shows the ladder strip with the same states.
