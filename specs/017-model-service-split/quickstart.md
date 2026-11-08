# Quickstart: validating the model-service split

These checks prove that the feature works. Each one names the requirement or success criterion it proves. Paths are relative to the repository root; host values come from `deploy/recipe/params/omniverse2.yaml`.

## 0. Prerequisites

- The factory test environment: `cd factory/python && uv sync`.
- On Omniverse2: Docker with NVIDIA CDI, about 120 GB free on `/mnt/data` for the weights and images, and the recipe secret file (mode 0600) holding the tenant keys and the engine key. Neither file is in the repository.
- No GPU window is needed for steps 1 to 3.

## 1. Offline checks (no GPU, no host)

```bash
cd factory/python
uv run pytest tests/test_modelservice_*.py tests/test_llm_gateway_external.py -q
uv run python3 ../../tests/spec/validate_design.py
```

What these tests show:

| Area | Expected result |
| --- | --- |
| Tenant gateway (fake engine) | Requests without a key or with a wrong key get 401 (FR-009). A tenant over its share gets 429 `share_exhausted`. A tenant with a guaranteed share still gets its share while a neighbour saturates (FR-010, SC-003). No content appears in the outcome log (FR-012) |
| Identity | A changed weight digest gets 409 `identity_mismatch`, and the gateway refuses to start (FR-011) |
| External mode | Zero calls to the server start/stop/swap code and zero GPU-lock or lease acquisitions (FR-001). Each failure maps to its distinct reason (FR-005). An over-limit request is refused before sending (FR-006). `mode: owned` tests are unchanged (FR-007) |
| Capture | Switch off: zero bytes written. Switch on: one record per call, with no reasoning and no secret (FR-022 to FR-024, SC-007) |

## 2. Recipe checks (no GPU)

```bash
uv run python -m forge_factory.modelservice.recipe plan  --site omniverse2
uv run python -m forge_factory.modelservice.recipe verify --site omniverse2   # downloads checked against the lock
```

- `verify` exits non-zero and names the file on any SHA-256 mismatch (FR-017).
- `plan --site production` lists every parameter. Each shows its production value or `confirmed: false`, and no secret value is printed (FR-018, SC-008).

## 3. Factory machine stand-in isolation (no GPU)

Start the factory container from the recipe, then run these checks from inside it (FR-021, User Story 5):

| Check | Expected result |
| --- | --- |
| No GPU device | `nvidia-smi` fails and no `/dev/nvidia*` devices exist |
| No host model paths | Host model paths are absent |
| Only the model channel | Connecting to any host port other than the tenant gateway fails |
| Stand-in report | It lists what the container does not prove |

## 4. First window: model tier smoke test (needs a window; owner lane paused, then restored)

```bash
uv run python -m forge_factory.modelservice.window run --plan smoke --max-minutes <owner limit>
```

Expected steps in the window record:

1. `drain_requested` → `lane_idle` → `lane_model_stopped` → `gpu_free_verified`
2. `tier_started` → `identity_verified`
3. Smoke qualification and neighbour contention
4. `tier_stopped` → `gpu_free_verified` → `lane_model_restarted` → `lane_resumed`

Further expectations:

- The KV capacity check: at least 2 × 65,536 tokens, or the stated fallback (research R2).
- `GET /forge/v1/identity` matches the lock (User Story 2, scenario 4).
- With `sim-neighbour` saturating, the factory's calls never fail (SC-003).
- The window outcome is `COMPLETED`. On any failure it is `ABORTED_RESTORED`, with the owner lane running again.

## 5. Qualification (one or more windows)

```bash
uv run python -m forge_factory.modelservice.window run --plan qualification --max-minutes <owner limit>
uv run python -m forge_factory.modelservice.qualify report --out <evidence dir>
```

- The report validates against `contracts/qualification-report.schema.json`.
- Every passed SWE phase appears with both setups (SC-005); a missing side is `NOT_RUN`.
- Deviations are listed with their production values.
- Any blocking finding has a CAPA id (FR-016).
- 100% of the candidate run's calls carry an identity fingerprint (SC-002).
- The audit trail shows zero model-server or GPU actions by factory components (SC-001).

## 6. Rebuild drill (SC-004)

1. Tear down the model tier and the factory machine, keeping the data volume.
2. Run `recipe apply --site omniverse2`, then `recipe drift`.

Expected: 0 drift findings and the same identity fingerprint. Record the time taken.

## 7. Cutover (owner only; not part of autonomous validation)

The cutover needs all of these:

- the owner's approval of a `QUALIFIED_FOR_OWNER_REVIEW` report;
- a transport proof for the new gateway, re-measured and signed by the owner;
- a rehearsed way back (SC-006).

None of this is automated by Claude.
