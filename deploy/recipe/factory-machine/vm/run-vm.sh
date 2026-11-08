#!/usr/bin/env bash
# Forge-C factory machine as a VM on Omniverse2 (feature 017, User Story 5, T062; research R9).
#
# BLOCKED until the omniverse2 user is in group kvm (owner 2026-11-08: an admin can add it). /dev/kvm is NEVER passed
# through Docker (that would bypass the host's deliberate restriction of /dev/kvm; research R9, "Not used").
#
# Boots the pinned Ubuntu 22.04 cloud image (overlay; the base stays read-only) with a cloud-init seed ISO built by
# genisoimage from cloud-init/user-data.yaml + meta-data, 16 vCPU / 64 GB (params factory_vcpu / factory_ram_gib), the
# data disk on vdb (mounted at /srv/forge-c by cloud-init). Network: qemu user-mode with restrict=on, so the guest has
# no route to the host or anywhere else except two explicit forwards:
#   hostfwd  127.0.0.1:$FORGE_VM_SSH_PORT -> guest :22                      (SSH in, host loopback only)
#   guestfwd $FORGE_VM_CHANNEL_ADDR:18480 -> host 127.0.0.1:$FORGE_CHANNEL_HOST_PORT  (the model channel, nothing else)
# Inside the VM the model channel is http://$FORGE_VM_CHANNEL_ADDR:18480/v1.
# First boot needs the apt/PyPI mirrors and the pinned release URLs: --provision boots once with restrict=off.
#
# Usage: run-vm.sh [--dry-run] [--provision] | --render-seed DIR
#   --dry-run       print the genisoimage/qemu-img/qemu commands; change nothing (exit 3 if still BLOCKED)
#   --provision     first boot with outbound access for provisioning (setup only; ONPREM "Network")
#   --render-seed   write the rendered user-data and meta-data into DIR (no kvm needed; no ISO, no VM)
#
# Parameters (environment):
#   FORGE_KVM_DEVICE           /dev/kvm
#   FORGE_QEMU                 qemu-system-x86_64   (host package or pinned image, as the admin approves)
#   FORGE_VM_DIR               /mnt/data/forge-c/model-service/factory-vm   overlay, data disk, seed, console log
#   FORGE_VM_BASE_IMAGE        /mnt/data/forge-c/model-service/images/ubuntu-22.04-server-cloudimg-amd64.img
#   FORGE_VM_BASE_IMAGE_SHA256 (lock images.factory_vm_base.sha256)   verified before every boot; missing = REFUSED
#   FORGE_VM_VCPU              16          FORGE_VM_RAM_GIB 64          FORGE_VM_DATA_SIZE 250G
#   FORGE_VM_SSH_PORT          2222        FORGE_VM_SSH_PUBKEY_FILE ~/.ssh/id_ed25519.pub
#   FORGE_VM_CHANNEL_ADDR      10.0.2.100  FORGE_CHANNEL_HOST_PORT 18480 (tenant gateway on the host loopback)
#   FORGE_PROVISION_ENV_FILE   (empty)     FORGE_* pins/repo for provision.sh (no secrets), embedded in the seed
#   FORGE_LOCK_FILE            ../../recipe.lock.json
#
# Exit codes: 0 started / rendered, 2 usage, 3 BLOCKED (kvm or tools missing), 4 REFUSED (pin or image check).
set -euo pipefail

DRY_RUN=0; PROVISION=0; RENDER_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --provision) PROVISION=1 ;;
    --render-seed) RENDER_DIR="${2:?--render-seed needs a directory}"; shift ;;
    -h|--help) sed -n '2,38p' "$0"; exit 0 ;;
    *) echo "run-vm: unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MACHINE_DIR="$(dirname "$HERE")"
FORGE_KVM_DEVICE="${FORGE_KVM_DEVICE:-/dev/kvm}"
FORGE_QEMU="${FORGE_QEMU:-qemu-system-x86_64}"
FORGE_VM_DIR="${FORGE_VM_DIR:-/mnt/data/forge-c/model-service/factory-vm}"
FORGE_VM_BASE_IMAGE="${FORGE_VM_BASE_IMAGE:-/mnt/data/forge-c/model-service/images/ubuntu-22.04-server-cloudimg-amd64.img}"
FORGE_VM_VCPU="${FORGE_VM_VCPU:-16}"
FORGE_VM_RAM_GIB="${FORGE_VM_RAM_GIB:-64}"
FORGE_VM_DATA_SIZE="${FORGE_VM_DATA_SIZE:-250G}"
FORGE_VM_ROOT_SIZE="${FORGE_VM_ROOT_SIZE:-50G}"   # ONPREM "OS disk 50 GB"; cloud-init grows the root partition to it
FORGE_VM_SSH_PORT="${FORGE_VM_SSH_PORT:-2222}"
FORGE_VM_SSH_PUBKEY_FILE="${FORGE_VM_SSH_PUBKEY_FILE:-$HOME/.ssh/id_ed25519.pub}"
FORGE_VM_CHANNEL_ADDR="${FORGE_VM_CHANNEL_ADDR:-10.0.2.100}"
FORGE_CHANNEL_HOST_PORT="${FORGE_CHANNEL_HOST_PORT:-18480}"
FORGE_PROVISION_ENV_FILE="${FORGE_PROVISION_ENV_FILE:-}"
FORGE_LOCK_FILE="${FORGE_LOCK_FILE:-$MACHINE_DIR/../recipe.lock.json}"
USER_DATA="$MACHINE_DIR/cloud-init/user-data.yaml"
PROVISION_SH="$MACHINE_DIR/provision.sh"

blocked() { echo "BLOCKED: $*"; exit 3; }
refuse() { echo "REFUSED: $*" >&2; exit 4; }

render_seed() {  # render_seed <dir>: user-data with the markers replaced, and meta-data
  local out="$1" pub="" envf=""
  [ -f "$FORGE_VM_SSH_PUBKEY_FILE" ] && pub="$(head -n1 "$FORGE_VM_SSH_PUBKEY_FILE")"
  [ -n "$FORGE_PROVISION_ENV_FILE" ] && envf="$FORGE_PROVISION_ENV_FILE"
  mkdir -p "$out"
  python3 -I - "$USER_DATA" "$PROVISION_SH" "$FORGE_LOCK_FILE" "$envf" "$pub" "$out" <<'PY'
import base64, pathlib, re, sys
ud, prov, lock, envf, pub, out = sys.argv[1:7]
b64 = lambda p: base64.b64encode(pathlib.Path(p).read_bytes()).decode() if p and pathlib.Path(p).is_file() else ""
env = pathlib.Path(envf).read_text() if envf else "FORGE_SITE=omniverse2\n"
if re.search(r"(?i)(api[_-]?key|password|secret|token)\s*=", env):
    sys.exit("REFUSED: provision env file looks like it holds a credential; it may hold pins and FORGE_* parameters only")
if any(c in pub for c in '"\\\n'):
    sys.exit("REFUSED: ssh public key contains quote/backslash/newline")
text = pathlib.Path(ud).read_text()
for k, v in {"FORGE_PROVISION_SH_B64": b64(prov), "FORGE_RECIPE_LOCK_B64": b64(lock),
             "FORGE_PROVISION_ENV_B64": base64.b64encode(env.encode()).decode(), "FORGE_SSH_PUBKEY": pub}.items():
    text = text.replace(f"@@{k}@@", v)
o = pathlib.Path(out)
(o / "user-data").write_text(text)
(o / "meta-data").write_text("instance-id: forge-factory-1\nlocal-hostname: forge-factory\n")
PY
  chmod 0600 "$out/user-data"
  echo "seed rendered: $out/user-data $out/meta-data"
}

if [ -n "$RENDER_DIR" ]; then render_seed "$RENDER_DIR"; exit 0; fi

# ------------------------------------------------------------------------------------------------- the kvm gate
KVM_OK=1
{ [ -r "$FORGE_KVM_DEVICE" ] && [ -w "$FORGE_KVM_DEVICE" ]; } || KVM_OK=0
if [ "$KVM_OK" = 0 ] && [ "$DRY_RUN" = 0 ]; then
  blocked "/dev/kvm not accessible (needs kvm group, owner 2026-11-08)"
fi

SEED_DIR="$FORGE_VM_DIR/seed"; SEED_ISO="$FORGE_VM_DIR/seed.iso"
OVERLAY="$FORGE_VM_DIR/root-overlay.qcow2"; DATA_DISK="$FORGE_VM_DIR/data.qcow2"
if [ "$PROVISION" = 1 ]; then RESTRICT=off; else RESTRICT=on; fi
NETDEV="user,id=n0,restrict=$RESTRICT,hostfwd=tcp:127.0.0.1:$FORGE_VM_SSH_PORT-:22"
NETDEV="$NETDEV,guestfwd=tcp:$FORGE_VM_CHANNEL_ADDR:18480-cmd:socat - TCP:127.0.0.1:$FORGE_CHANNEL_HOST_PORT"
QEMU_CMD=("$FORGE_QEMU" -name forge-factory -machine q35,accel=kvm -cpu host
  -smp "$FORGE_VM_VCPU" -m "${FORGE_VM_RAM_GIB}G"
  -drive "file=$OVERLAY,if=virtio,format=qcow2"
  -drive "file=$DATA_DISK,if=virtio,format=qcow2"
  -drive "file=$SEED_ISO,media=cdrom,readonly=on"
  -netdev "$NETDEV" -device virtio-net-pci,netdev=n0
  -display none -serial "file:$FORGE_VM_DIR/console.log" -pidfile "$FORGE_VM_DIR/qemu.pid" -daemonize)
SEED_CMD=(genisoimage -quiet -output "$SEED_ISO" -volid cidata -joliet -rock "$SEED_DIR/user-data" "$SEED_DIR/meta-data")
OVERLAY_CMD=(qemu-img create -f qcow2 -F qcow2 -b "$FORGE_VM_BASE_IMAGE" "$OVERLAY" "$FORGE_VM_ROOT_SIZE")
DATA_CMD=(qemu-img create -f qcow2 "$DATA_DISK" "$FORGE_VM_DATA_SIZE")

if [ "$DRY_RUN" = 1 ]; then
  echo "PLAN: verify sha256 of $FORGE_VM_BASE_IMAGE"
  echo "PLAN: render seed into $SEED_DIR (user-data from cloud-init/user-data.yaml, meta-data)"
  printf 'PLAN:'; printf ' %q' "${SEED_CMD[@]}"; echo
  printf 'PLAN:'; printf ' %q' "${OVERLAY_CMD[@]}"; echo " (if absent)"
  printf 'PLAN:'; printf ' %q' "${DATA_CMD[@]}"; echo " (if absent)"
  printf 'PLAN:'; printf ' %q' "${QEMU_CMD[@]}"; echo
  echo "channel inside the VM: http://$FORGE_VM_CHANNEL_ADDR:18480/v1 (restrict=$RESTRICT)"
  if [ "$KVM_OK" = 0 ]; then blocked "/dev/kvm not accessible (needs kvm group, owner 2026-11-08)"; fi
  exit 0
fi

# ------------------------------------------------------------------------------------------------- tools, image
for t in "$FORGE_QEMU" qemu-img genisoimage socat python3; do
  command -v "$t" >/dev/null 2>&1 || blocked "$t not installed (host package or pinned image; admin approval, research R9)"
done
sha="${FORGE_VM_BASE_IMAGE_SHA256:-}"
if [ -z "$sha" ] && [ -f "$FORGE_LOCK_FILE" ]; then
  sha="$(python3 -I -c 'import json,sys; print(((json.load(open(sys.argv[1])).get("images") or {}).get("factory_vm_base") or {}).get("sha256") or "")' "$FORGE_LOCK_FILE")"
fi
[[ "$sha" =~ ^[0-9a-f]{64}$ ]] || refuse "base image SHA-256 missing (FORGE_VM_BASE_IMAGE_SHA256 or lock images.factory_vm_base.sha256)"
[ -f "$FORGE_VM_BASE_IMAGE" ] || refuse "base image absent: $FORGE_VM_BASE_IMAGE (fetch it with the recipe; not downloaded here)"
echo "$sha  $FORGE_VM_BASE_IMAGE" | sha256sum -c --status || refuse "base image SHA-256 mismatch: $FORGE_VM_BASE_IMAGE"
[ -f "$FORGE_VM_DIR/qemu.pid" ] && kill -0 "$(cat "$FORGE_VM_DIR/qemu.pid")" 2>/dev/null && { echo "factory VM already running"; exit 0; }

mkdir -p "$FORGE_VM_DIR"; chmod 0700 "$FORGE_VM_DIR"
render_seed "$SEED_DIR"
"${SEED_CMD[@]}"
[ -f "$OVERLAY" ] || "${OVERLAY_CMD[@]}"
[ -f "$DATA_DISK" ] || "${DATA_CMD[@]}"
"${QEMU_CMD[@]}"
echo "factory VM started (restrict=$RESTRICT): ssh -p $FORGE_VM_SSH_PORT forge@127.0.0.1; channel http://$FORGE_VM_CHANNEL_ADDR:18480/v1"
