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
