# Owner-lane controls for qualification windows (T012)

This was surveyed read-only on 2026-11-08, in the repository at the base commit and on Omniverse2. The window controller (T014) may use only the controls marked **use**. Every one of them is existing and unsigned.

## Telling the lanes apart

| Lane | How to recognise it |
| --- | --- |
| **Owner lane** | The GPU process is `.../swe1-fabro-20261031/lrtx/ollama-0.34.0/lib/ollama/llama-server` (41.8 GiB). Its cgroup is a transient unit `app.slice/forge-c-owner-development-<rev>-guard<pid>-<date>.service` (`Restart=no`, `KillMode=process`), whose main process is the `owner_supervised_development` guardian. It runs in a private network namespace: llama-server 11457, gateway 11456, ollama 11455; Fabro is relayed to the host on 32397. |
| **Production lane** | The gateway listens on host port 11460 in a session scope, not a unit. Its intent file is `~/.local/state/forge-c-production-014/operations.json`. |
| **Observer** | `forge-line-conductor-local.service` is in OBSERVE mode. It shares the owner lane's state directory and its intent file `~/.config/forge-c/line-local/operations-intent.json`. |

- **Port 11457 exists in both network namespaces.** Lanes are therefore identified by `/proc/<pid>/cgroup` and `/proc/<pid>/ns/net`, never by port.
- The controller refuses to start if any GPU compute process is outside the owner lane's cgroup, for example the production lane.

## Steps

| Step | Control | Evidence | Reference | Use? |
| --- | --- | --- | --- | --- |
| 1. Drain | Admission hold: `Store.set_control(paused="1")` on `lrtx/state/supervisor/line-queue.sqlite3`, with `FORGE_OPERATIONS_INTENT` unset. This is the deployer's `hold-admission-once.py` pattern. | `control()['paused']=='1'`; intent file bytes unchanged | `afo/queue.py:535-559`; `afo/line_orders.py:1349-1352` | **use** |
| 2. Idle check | Every ledger check must hold: no order in RUNNING/ADMITTED/VALIDATING/WAITING_RECOVERY/QUEUED; inference holder empty; liveness RELEASED; request ledger QUIESCENT; outbox resolved. The gateway `/health` must show `inflight == waiting == 0` (read inside the namespace). No live Fabro run on 32397. | All of the above true | `afo/owner_profile_bootstrap.py:66-84` (`quiet_ledger`); `llm_gateway.py:373-377` | **use** (read-only) |
| 3. Stop the model server | **No control stops llama-server alone.** `stack serve`, `line_stack_lifecycle.stop` and the managed `stack stop` are refused or write the intent. The unmanaged stop sends raw SIGTERM and bypasses the lifecycle. The only clean way to free the GPU is the deployer's **whole-lane stop** tooling (per guardian, PLAN_ONLY by default): it stops the bridges, Fabro and the guardian, then the provider namespace, and leaves the intent unchanged. | No compute process in the owner cgroup (`nvidia-smi --query-compute-apps`); free VRAM | `lrtx/provider_process.py:232-290`; `autodeploy.py:283` (generator) | **use: whole-lane stop through deployer tooling only** |
| 4. Restart | The deployer's recover path: a new guardian with `--bootstrap-managed-profile` and a fresh ticket, which brings up Fabro and the stack and waits for health. It needs `paused=0` and intent RUNNING. | Stack status healthy for every service; the new guardian's audit log advances | `afo/owner_profile_bootstrap.py:374-385`; `autodeploy.py:965-985`, `1335-1359` | **use** |
| 5. Resume | `Store.set_control(paused="0")` (the `clear-hold-once.py` pattern). | `paused=='0'`; the guardian places the next order | `afo/queue.py:535` | **use** |

## Never use

- **`afo/operations.py` intent changes** (`synchronize`, pause/drain/resume/shutdown, `settle_shutdown`). Every change bumps the epoch, which permanently fences the live guardian (`INTENT_FENCED`) and the stack lifecycle. The intent is also shared with the observer.
- **Signed controls:** `afo-allowed-signers`, `afo-authorizations`, `development-inputs/*.proposed.yaml`, the control JSON and the guardian record. None of the steps above needs them.
- **Anything about the production lane.**

## Things that would fight the window

- **Owner autodeploy timer (every 10 minutes):** when the guardian is gone, `auto()` runs `recover()`, which takes the GPU back. With `paused=1` it latches `FAILED_LATCHED.json` instead. During a window, the controller holds `deploy.lock` with its own live PID (`SKIP locked`, `autodeploy.py:1337-1343`), and releases it only after the lane is restored.
- **Guardian:** it never restarts the stack by itself, but the admission hold must stay set while the lane is stopped.
- **Line watchdog:** it restarts only the observer unit when that unit has failed, never the stack.

## Consequences for the design

- **A window costs a whole owner-lane stop and restart.** That means one bootstrap: a new guardian record and a fresh ticket. Windows therefore run only when the lane is idle (the step 2 checks are all true) and are kept rare.
- **The controller is dry-run by default**, and it never generates or edits a deployer stop script. It calls the deployer's own generated tooling. If no tooling exists for the current guardian, the window is refused with `NO_DEPLOYER_STOP_TOOLING` (BLOCKED, never improvised).
- **The cutover (S6) removes the need for windows.** Once the owner lane is a tenant of the model service, the GPU belongs to the service permanently.
