# Quickstart: validating the Factory KPI Control Room

These are the validation scenarios that prove the feature end to end. Contracts: `contracts/`. Entities and
rules: `data-model.md`.

## Prerequisites

```bash
cd <repo>   # or the feature worktree
. scripts/forge-env.sh
export PYTHONPATH=$PWD/factory/python:$PWD/factory/python/tests FORGE_REPO_ROOT=$PWD
```

The dashboard tokens are in `$FORGE_STATE_DIR/dashboard/tokens.json`.

## 1. Automated checks

```bash
pytest -q -p no:cacheprovider factory/python/tests/test_controlroom_*.py
ruff check factory/python/forge_factory/controlroom
python tests/spec/validate_design.py
```

Expected: all pass. These tests cover:

- **Andon derivation** from fixture gate logs: RUNNING, REWORK, BLOCKED with the recorded reason, IDLE, STOPPED.
- **Scorecard equality** with `kpi.engine.snapshot` on a frozen event set (SC-003).
- **NOT_MEASURED** for missing inputs, including OEE without baselines and cost without a price.
- **Replay idempotence:** the same records twice give identical values (SC-004).
- **SPC limits** against hand-computed references, and INSUFFICIENT_DATA below the minimum.
- **Pareto order** and cumulative shares.
- **Usage:** Fabro native plus ACP proxy records, with "not reported" never counted as zero.
- **Alerts:** stable IDs, and violations are not filterable (SC-005).
- **API:** read-only (no POST under `/api/v1/control-room`), auth required, export CSV/JSON.
- **SSE latency:** after a gate-log line is appended, the `floor` event arrives within 5 s in at least 95 of
  100 trials (SC-001).
- **No model calls** while serving: the model clients are patched to fail if called (SC-007).

## 2. Live check on this host

```bash
python -m forge_factory.dashboard.app --port 8766    # separate port; the running 8765 instance is untouched
# open http://127.0.0.1:8766/control-room, sign in with the viewer token
```

Expected:

- Seven station columns (SWE.1–SWE.6, Shipping). Each shows an andon label and colour, the units and the
  oldest wait.
- Recent work orders such as LL r167 (BLOCKED at SWE.4, "rework budget exhausted (3 failed cycles)") appear
  with their recorded reason.
- The scorecard for today, 7 days and 30 days shows READY and BLOCKED separately. OEE shows NOT_MEASURED
  ("no calibrated baseline") when no baseline exists.
- The usage panel shows author tokens for ACP nodes as "not reported" for runs before the proxy usage change,
  and as reported afterwards. Cost shows NOT_MEASURED for subscription models.
- With no running work order and no new record for `staleness_s`, the board shows NO_WIP, and no stale banner
  appears unless something is supposedly running.

## 3. Live replay (real time)

Start a work order (Codex authors + Claude inspectors):

```bash
eval "$(scripts/forge_cloud_bench.sh env)"
cd factory/python && python -m forge_factory.workorder --example ../../examples/0002a-arm_55_rcc_ll \
    --wo <WO-ID> --model deepseek-flash --provider deepseek --acp-authors codex --acp-inspectors claude --detach
```

Watch the Control Room without reloading. The unit moves SWE.1 → … with amber during rework, red with the
reason if blocked, and appears under Shipping with READY or BLOCKED when finalized.

## 4. Layout

At browser width 390 px: no horizontal scrolling, and the stations collapse to a list. Every andon state reads as
text, not colour alone. If a headless browser is available, `test_controlroom_api.py::test_layout_*` checks
`scrollWidth <= clientWidth` at 390 and 1440 px. Otherwise the check is recorded NOT_RUN.
