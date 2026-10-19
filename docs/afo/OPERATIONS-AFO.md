# AFO operations: host prerequisites, installation and modes (AFO-T011)

These are owner/operator steps. AFO and its agents never run `sudo`, never edit `/etc` and never install units on
their own. Every command below is for the operator to review and run.

## 1. Host facts observed on 2026-10-19

| Fact | Observed | Consequence for 24/7 |
|---|---|---|
| User lingering | `Linger=yes` | User services survive logout. |
| Data root | `/media/jefferson/11c42dee-…/forge-c` on `/dev/loop10` (ext4, UUID `11c42dee-73a3-4c2b-ab42-a0440011d9e0`) | The volume is an image file, not a partition. |
| Image file | `/media/jefferson/Lexar/.s-core-build/build-volume-v1.ext4` on USB drive `sdc1` (exFAT, UUID `002B-CE31`) | The volume shares the image with another project's build data. |
| How it is mounted | The desktop auto-mounts the drive at login (udisks), then a loop mount runs with `autoclear`. There is no fstab entry or mount unit. | **After a reboot nothing is mounted until someone logs in. Headless 24/7 operation is not possible yet.** |
| systemd user manager | `degraded`, from units of other projects and a desktop indexer | Not caused by Forge-C. Left untouched. |

## 2. Make the data volume available at boot (operator, needs sudo)

Pick one option and test it in a maintenance window. AFO only checks the result: `RequiresMountsFor=` on every unit,
plus the preflight sentinel.

- **Option A (recommended): give the volume its own drive or partition** (internal disk or a dedicated USB disk) and
  mount it by UUID in `/etc/fstab`, with `nofail,x-systemd.device-timeout=30s`.
- **Option B: keep the image on the Lexar drive.** Mount the exFAT drive by UUID, then the image as a loop mount
  that depends on it:

  ```
  UUID=002B-CE31  /media/jefferson/Lexar  exfat  uid=1000,gid=1000,nofail,x-systemd.device-timeout=30s  0 0
  /media/jefferson/Lexar/.s-core-build/build-volume-v1.ext4  /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0  ext4  loop,nofail,x-systemd.requires-mounts-for=/media/jefferson/Lexar  0 2
  ```

  Keep in mind that the drive is removable. Pulling it stops every Forge-C service through `RequiresMountsFor`, and
  the services stay stopped (fail closed) until it returns. They never write to the bare mount point.

Then record the volume once, after the mount works:

```
. scripts/forge-env.sh && python -m forge_factory.afo.host init
python -m forge_factory.afo.host preflight     # must print "ok": true
```

## 3. Credentials (least privilege)

- **DeepSeek key:** stays in the isolated cloud Fabro server's vault (`scripts/forge_cloud_bench.sh`). Units never
  read it. The gateway runs without it.
- **Codex:** the factory login is in `$FORGE_DATA_ROOT/codex-home`, mode 0700, separate from the owner's `~/.codex`.
- **Anything new:** use `systemd-creds` or an `EnvironmentFile=` with mode 0600 outside git. No agent role gets
  read access to those paths (MCP path scopes), and no secret goes in a unit file or in the repository.

## 4. Install the units (operator)

```
. scripts/forge-env.sh
python -m forge_factory.afo.services render --out /tmp/afo-units      # read them first
python -m forge_factory.afo.services verify                          # systemd-analyze --user verify
python -m forge_factory.afo.services install                          # writes ~/.config/systemd/user, enables nothing
```

Switching a live service to its unit is a maintenance-window step, one service at a time:

1. Stop the running process **by PID**. Never use `pkill` or a name pattern: other projects run their own Fabro and
   Ollama on this host.
2. `systemctl --user enable --now forge-<service>.service`, then check its health URL.
3. Run the restart drill for that service. AFO-T014 is PARTIAL until each managed service has passed it.

Enable `forge-conductor.service` and `forge-afo-watchdog.timer` last. `scripts/forge_services.sh` keeps working for
anything not yet switched.

## 5. Modes

- **The shipped policy is OBSERVE_ONLY.** The Conductor reads, simulates and records only.
- **PILOT or ACTIVE** needs three things:
  - the policy sets `mode` and `authorization_ref`;
  - the owner writes `config/factory/afo-authorizations/<id>.json` (contracts/authorization.schema.json), bound to
    the policy's sha256 (`python -m forge_factory.afo.policy`), and signs it with their own SSH key:
    `python -m forge_factory.afo.authz sign config/factory/afo-authorizations/<id>.json --key ~/.ssh/<owner key>`;
  - the owner's public key is in `config/factory/afo-allowed-signers` as
    `<approver> namespaces="forge-afo-authorization" <public key>`.
- **Revoking:** add the id to `config/factory/afo-authorizations/revoked.txt`, or set `revoked_utc`.
- **AFO ACTIVE never switches CRE mode.** Actions that CRE owns also need CRE's own authorization.

## 6. Watching it

- `systemctl --user status forge-conductor`
- `python -m forge_factory.afo.services status`
- **Heartbeat:** `$FORGE_STATE_DIR/afo/conductor.heartbeat`
- **Alerts:** `$FORGE_STATE_DIR/afo/alerts.jsonl`
- **Every decision AFO takes:** `$FORGE_STATE_DIR/afo/decisions.jsonl`

## 7. Factory Maintainer proposals (M5, ADR-AFO-003)

- Disabled by policy (`maintenance.enable_factory_maintainer: false`, `allow_proposal_pr: false`).
- When enabled, the Conductor prepares a case per order in WAITING_EXTERNAL_CHANGE. A case is an isolated worktree
  under the sandbox volume.
- After the maintainer agent submits, the operator runs:
  - `python -m forge_factory.afo.cli maintainer-process <proposal_id> [--capa CAPA-NNN]`: veto, baseline
    reproducer, CAPA link and CRE evaluation. It can take about 1 h.
  - `python -m forge_factory.afo.cli maintainer-publish <proposal_id>`: local branch `afo/proposal/<id>`; a draft
    PR only if `allow_proposal_pr` is on.
- Merging is a human decision outside AFO.
- After an approved change is deployed: `python -m forge_factory.afo.cli external-change <order_id> --revision <sha>
  --approval-ref <PR/decision> --reason "..."`. Otherwise the order ends BLOCKED after
  `budgets.max_order_wall_seconds`.

## 8. Dead letters and alerts (M6)

- Every order finalized BLOCKED gets exactly one dead-letter case: reason code, required action, artifact refs with
  hashes. Its alert is enqueued in the same transaction.
- **Case states.** A case moves `OPEN → ACKNOWLEDGED → CLOSED`, by the operator only. The record itself is immutable,
  and the database refuses edits and deletes.
  ```
  python -m forge_factory.afo.cli dead-letter-ack <case_id> --reason "looking at it"
  python -m forge_factory.afo.cli dead-letter-close <case_id> --reason "re-submitted as <order>"
  ```
- **Notices.** `$FORGE_STATE_DIR/conductor/notifications.jsonl` (0600) gets one line per announcement, mirrored to
  the 002 ledger (channel `human`).
  - A repeat within `notifications.dedupe_window_seconds` only counts. A fact still being reported one window after
    its last delivery is announced once more.
  - The watchdog's stale-heartbeat alerts stay in `$FORGE_STATE_DIR/afo/alerts.jsonl`.
- A dead-letter case is bookkeeping, not a release state. The archive stays BLOCKED and never counts as READY.

## 9. Dashboard Autonomy view and operator controls (M6)

- **Read-only views:** `/api/v1/afo/{summary,orders,orders/<id>,dead-letters,proposals,operations}` with the
  existing viewer and auditor tokens. Operator actions are visible to auditors only.
  - They read through a read-only database connection, so they never write or lock the queue.
- **Pause, drain, resume from the dashboard:** use `POST /api/v1/afo/operator/{pause,drain,resume}` with the JSON
  body `{"reason": "..."}` and `Authorization: Bearer <operator token>`.
  - The viewer and auditor tokens and the session cookie are refused. Every refusal is audited.
  - Issue or rotate the operator token as the state-directory owner:
    `python -m forge_factory.afo.cli operator-token --reason "rotate"`. The token is printed once; the old one stops
    working.
- The CLI controls (`pause`, `drain`, `resume`) do the same thing and are recorded the same way.

## 10. Backup, restore and rollback

- **Backup** (online, consistent, 0600, integrity-checked):
  `python -m forge_factory.afo.cli backup <dest>.sqlite3 --reason "nightly"`.
- **Restore** into a NEW path only. A live store is never overwritten.
  ```
  python -c "from pathlib import Path; from forge_factory.afo.queue import Store; print(Store.restore(Path('<backup>'), Path('<new path>')))"
  ```
  Stop the Conductor first. Then move the restored file into `$FORGE_STATE_DIR/conductor/` and start the Conductor
  again. Reconciliation adopts or quarantines the in-flight attempts.
- **Roll back the factory:**
  1. Pause.
  2. Check out the last approved revision in the deployment worktree.
  3. Restart the services by PID or unit.
  4. Resume.

  Orders already running keep the revision recorded in their attempt; new attempts use the deployed revision.
- **Roll back the mode:** set `mode: OBSERVE_ONLY` in `config/factory/afo-policy.yaml`. That needs no signature.
  Revoke the authorization (section 5) if it should not be reused.

## 11. Security

- Agents reach only their MCP operations. They hold no shell, no git, no GitHub and no operator token.
- The Factory Maintainer's candidate code runs as the sandbox UID `maintainer`, with no network and no credentials.
- Every proposal goes through the git-diff veto and the independent 004 promotion gate. The broker can create a
  branch or a draft PR only (ADR-AFO-003).
- Tokens live only in `$FORGE_STATE_DIR/dashboard/` (0600). Rotate the operator token after any suspected exposure.

## 12. Incidents

| Signal | Meaning | Action |
|---|---|---|
| Watchdog `HEARTBEAT_STALE` | Conductor hung or dead | systemd restarts it; if it repeats, `pause` and read the journal |
| Orders stay QUEUED, `deferred` events | A dependency is down (Fabro, gateway, MCP, volume) | Fix the dependency; backoff is bounded and resumes by itself |
| `database is locked` in the Conductor log | Another writer holds the store | Find it (`fuser`), stop it by PID; the Conductor retries next cycle |
| Notices stay PENDING | The notice log cannot be written (disk full) | Free space; delivery resumes and nothing is lost |
| Attempt `UNKNOWN` / order quarantined | A launch outcome cannot be proven | Read the reconciliation events; never relaunch by hand |

## 13. Maintenance window

1. `drain`, so running work reaches a safe point.
2. Wait until no order is ADMITTED, RUNNING or VALIDATING.
3. Do the work.
4. `resume`.

Restart and reboot drills (AFO-T014, T015, T034, T069) run only in an owner-approved window.

## 14. Readiness and soak (M7)

- **Readiness:** `python -c "from forge_factory.afo import readiness, soak; import json; print(json.dumps(readiness.assess(), indent=1))"`.
  The levels come from evidence only. Missing data means NOT_DEMONSTRATED, and the assessment never changes the mode.
- **Soak:** it needs your authorization.
  1. `python -m forge_factory.afo.soak start soak-24h-1 --target-hours 24 --interval 60 --authorization-ref <OD id>`
  2. `python -m forge_factory.afo.soak run soak-24h-1`
  3. `python -m forge_factory.afo.soak report soak-24h-1`

  Only real, contiguous wall-clock time counts. Gaps, clock jumps and reboots count as unknown exposure.
