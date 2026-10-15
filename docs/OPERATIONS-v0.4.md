# Forge-C v0.4 — Operations, recovery and offline review guide

Status: implementation guide for the open-source, local-first factory. Nothing in this guide, and no package the
factory produces, constitutes ISO 26262 / ASIL B approval, ASPICE capability determination or a production release.

## 1. Ubuntu workstation setup (no sudo, no paid services)

| Component | Version (pinned) | How |
|---|---|---|
| Python | 3.13 (≥3.12) | `scripts/bootstrap_factory.sh` → venv on `FORGE_DATA_ROOT`, hash-locked `requirements/forge-factory.lock` |
| LLVM / Clang | 19.1.7 | official release tarball, attestation digest verified (ADR-0001), on `PATH` via `scripts/forge-env.sh` |
| GNU Arm Embedded | 10.3-2021.07 (`arm-none-eabi-gcc`) | distro package; Cortex-M55 target profile |
| Cppcheck | 2.7 + MISRA addon (subset) | distro package |
| Ollama | 0.34.0 standalone | data volume, `:11435`, 16 k context (ADR-0005) |
| Model | qwen3:8b (Apache-2.0) | `ollama pull qwen3:8b` into `FORGE_DATA_ROOT/ollama-models` |
| Fabro | 0.362.0-nightly.0 (`a192bce`) | `~/.fabro/bin/fabro` (shared install; Forge-C uses its own server/storage, ADR-0002) |

```bash
. scripts/forge-env.sh                 # always first: data root, venv, LLVM 19, isolated Fabro CLI home
./scripts/bootstrap_factory.sh "$FORGE_VENV"
python -m forge_factory.inventory       # tool/licence inventory + CycloneDX SBOM (evidence/v0.4/inventory/)
./scripts/forge_services.sh start       # ollama :11435 -> llm-gateway :11436 -> fabro server :32290
./scripts/install_supervisor.sh         # model-free supervisor as a user systemd service (watchdog)
python -m forge_factory.dashboard.app &  # read-only dashboard on 127.0.0.1:8765
```
Fresh Fabro server secrets are generated in `<storage>/server.env` (0600). The CLI always runs with
`HOME=$FORGE_FABRO_HOME` (helper `forge_fabro`) so other projects' `~/.fabro` state is never touched.

## 2. Running a work order (one command, no human prompt)

```bash
python -m forge_factory.workorder --example examples/0002-arm_55_rcc_st --wo WO-0002 [--detach]
```
Flow: inputs hashed into an isolated git workspace → agent + MCP preflight (BLOCKED ⇒ immediate BLOCKED package,
no agent starts) → generated SWE.1–SWE.6 workflow (author → freeze gate → [SWE.3 guideline verification node] →
independent inspector → inspection gate → bounded rework router) → Release Manager → deterministic finalizer.
Every terminal path, including crashes, budget cancellation and Fabro's failure-cycle breaker, is packaged by the
supervisor's external finalizer.

## 3. Service lifecycle

| Action | Command |
|---|---|
| status | `scripts/forge_services.sh status`, `systemctl --user status forge-supervisor` |
| restart model only | `scripts/forge_services.sh restart-ollama` |
| stop everything | `scripts/forge_services.sh stop; systemctl --user stop forge-supervisor` |
| disable supervisor | `systemctl --user disable --now forge-supervisor` |
| container-only fallback | run `python -m forge_factory.supervisor.service` under any restart-always supervisor (Docker `--restart=always`, s6, supervisord); `sd_notify` is a no-op without `NOTIFY_SOCKET` |

The supervisor makes **zero** model calls: a socket-level guard blocks and counts any connection to model ports
(`health.json: model_calls`). It polls every 60 s (15–300 s valid), dispatches bounded repairs, runs the token
governor and the external finalizer.

## 4. Backup and restore

State lives under `FORGE_DATA_ROOT` (default the loop10 volume):

| Path | Content | Backup |
|---|---|---|
| `state/supervisor/incidents.sqlite3` | incident ledger (append-only history) | `sqlite3 .backup` or copy while supervisor stopped; WAL files included |
| `state/knowledge/lessons.sqlite3` | lesson store | same |
| `state/events/` | factory JSONL segments + `events.sqlite3` | segments are the source of truth; DB can be rebuilt by replay (idempotent) |
| `archives/` | write-once review packages (0444) | copy; verify with `verify_archive` / `sha256sum -c` |
| `infra/` | repair-surface git repo | `git bundle create infra.bundle --all` |
| `fabro/storage` | Fabro server storage + `server.env` | stop server, copy directory (contains secrets: protect) |

Restore: stop services, restore files, start services; replay events with `Collector().ingest_segment()`.

## 5. Trace retention and privacy

Capture levels and retention are in `config/factory/trace-policy.yaml`; changes are hot-reloaded and **rejected**
if they would disable audit (<INFO), security (<WARN), reasoning-capture-off or redaction. Dashboard filters are
display-only. Purge: `EventStore().purge(policy)` (audit retained ≥ 365 days). Raw AI prompt/response capture is off;
Qwen reasoning is suppressed at the gateway and never stored.

## 6. Dashboard authentication

Tokens: `state/dashboard/tokens.json` (0600) with roles `viewer` (no security/audit channels) and `auditor`.
Open `http://127.0.0.1:8765/login?token=<token>`. All API endpoints are GET/read-only; bind is loopback only.
Expose remotely only behind an authenticated reverse proxy.

## 7. Upgrade and rollback

* Never upgrade Fabro/Ollama/model/toolchain inside an active baseline: pin in `evidence/v0.4/inventory`, re-run
  `python tests/spec/validate_design.py`, the factory suite (`make factory-test`) and a T004 live probe on the new
  version before switching; record an ADR.
* Lessons tied to a regressed tool version: `LessonStore().invalidate_tool_version(tool, version)` (retracts and
  lists impacted runs).
* Infra repairs are promoted by compare-and-swap of `infra/main`; rollback = `git update-ref refs/heads/main <old>`.

## 8. Failure runbook

| Symptom | Deterministic signal | Action |
|---|---|---|
| Fabro down | incident `fabro/READINESS_FAILURE` after 2 polls | external repair worker dispatched; if exhausted → `REQUIRES_OFFLINE_ATTENTION`; `scripts/forge_services.sh start` |
| Agent loops on tool errors | `TURN_BUDGET_EXHAUSTED` / `TOKEN_BUDGET_EXHAUSTED` events | governor cancels; package BLOCKED; inspect `.forge-run/gates/gate-log.jsonl` |
| Run ended without package | supervisor log `external finalizer packaged …` | none — automatic |
| Tools appear as text in model output | context truncation | verify `OLLAMA_CONTEXT_LENGTH=16384` (`/api/ps`) |
| MCP op denied `NO_AUTHORIZATION_TICKET` | security event | check hook config in `.forge-run/workflow.toml`; never bypass |

## 9. Offline reviewer instructions

1. Obtain the archive and its `.sha256` from separate channels; verify the archive hash.
2. `python -c "from forge_factory.release.finalize import verify_archive; print(verify_archive(Path('<zip>')))"`
   (recomputes every member hash against the embedded `SHA256SUMS.txt`).
3. Read `REVIEW_SUMMARY.md`, `missing_artifacts.json`, `evidence/quality/final-gates.json` (every check is derived
   from recorded tool evidence), `evidence/safety/known_limitations.md`, inspection records, raw tool logs
   (`evidence/evidence-raw/`), operational inventory (`evidence/operations/`).
4. Perform independent engineering, safety and process review. A machine `READY_FOR_OFFLINE_REVIEW` is not approval.

## 10. Known safety-tool and evidence gaps (declared, not hidden)

* MISRA C: Cppcheck addon subset only; no compliance claim; rule texts not bundled.
* CBMC, Frama-C, Renode, an STM32N6 HwSim model, Unity/CMock: not installed → operations DISABLED; formal and
  target verification NOT PERFORMED; packages remain BLOCKED on `target_verification`.
* Host unit/integration tests and LLVM MC/DC coverage are host evidence only.
* Footprint is object-level / relocatable-image level, not a linked firmware image with startup and linker script.
* HSI, safety allocation, errata and silicon revision are not provided for the STM32N6 pilot.
* Tool qualification (ISO 26262-8 §11) is not performed for any tool or for the factory itself.

## External Fabro Monitor (`~/fabro_dashboard`) integration

Forge-C also appears in the existing LAN **Fabro Monitor** (`http://master.local:8787`, user service `fabro-monitor`).
That repo's code is unchanged; only its untracked `config.local.json` was extended (backup
`config.local.json.bak-20261015`):
- source `forge-c` → `http://127.0.0.1:32290/api/v1`, token read from Forge-C's isolated Fabro CLI
  `$FORGE_FABRO_HOME/.fabro/auth.json` (never sent to the browser);
- project `forge-c` (`Forge-C Fabric`) with `path=$FORGE_STATE_DIR` and `queue_globs: workorders/*/dashboard/queue.json`.

The model-free supervisor writes one queue record per work order on every poll
(`forge_factory.dashboard.fabro_monitor_export`; run once manually with
`python -m forge_factory.dashboard.fabro_monitor_export`). Items are SWE.1–SWE.6 plus the finalizer. Status comes
only from the deterministic gate log and package record, never from agent claims. The Fabro run status in the
**Runs** tab is a workflow outcome. A run can be `succeeded` while its product package is `BLOCKED`, which the
**Queues** tab shows. The monitor has no login; it is read-only and LAN-only.
