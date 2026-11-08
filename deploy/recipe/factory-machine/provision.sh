#!/usr/bin/env bash
# Forge-C factory machine provisioning (feature 017, User Story 5, T058; docs/ONPREM-DEPLOYMENT.md "Software on the VM").
#
# Provisions an Ubuntu 22.04 machine (the production VM, the Omniverse2 VM once `kvm` is granted, or the container
# stand-in built by container/Dockerfile) as the Forge-C factory machine. Idempotent: every step checks its state first.
# NO GPU software: no NVIDIA driver, no CUDA, no container toolkit. Inference runs on the separate model service and
# the only route to it is the model channel (FR-021).
#
# Usage: provision.sh [--dry-run] [--container]
#   --dry-run    print the planned steps and the pin status; change nothing; exit 0 (also when pins are missing).
#   --container  container stand-in: skip the steps that need systemd or a block device (lingering, data volume mount).
#
# Parameters (environment; defaults are the values of deploy/recipe/params/<site>.yaml where one exists):
#   FORGE_SITE               omniverse2                     site name (params/<site>.yaml), recorded only
#   FORGE_USER               forge                          non-root service account (ONPREM "Accounts"); never given sudo here
#   FORGE_UID                (system)                       fixed uid; the container uses the bind-mount owner's uid
#   FORGE_DATA_DIR           /srv/forge-c                   data volume mount point (params factory_data_volume, production)
#   FORGE_DATA_DEVICE        (empty)                        block device to mount at FORGE_DATA_DIR; empty = cloud-init/platform mounts it
#   FORGE_PREFIX             /opt/forge-c                   install prefix for toolchains, Fabro and the factory checkout
#   FORGE_CACHE_DIR          /var/cache/forge-c/downloads   verified download cache; pre-seed it for offline setup
#   FORGE_LOCK_FILE          ../recipe.lock.json            recipe lock (pins); also looked up next to this script
#   FORGE_PYTHON_VERSION     3.13                           Python installed with uv (uv verifies its own downloads)
#   FORGE_UV_VERSION         0.12.17                        uv release
#   FORGE_LLVM_VERSION       19.1.7                         LLVM/Clang release tarball
#   FORGE_GNU_ARM_VERSION    10.3-2021.07                   GNU Arm Embedded toolchain release tarball
#   FORGE_FABRO_VERSION      0.362.0                        Fabro workflow engine (recipe.lock.json fabro_version)
#   FORGE_REPO_URL           (required)                     git URL of the Forge-C repository (internal git server in production)
#   FORGE_REVISION           lock factory_revision          40-hex commit to check out (no branch names: pinned)
#   FORGE_EXTRA_APT          (empty)                        extra apt packages (GPU packages are refused)
#   FORGE_PROVISION_STOP_AFTER  (empty)                     "pins": stop after pin verification, before any change
#
# Pins: every downloaded artefact is verified by SHA-256 before it is used, and the script REFUSES (exit 4) before any
# change when a checksum is missing. Never skipped. Precedence: env FORGE_PIN_<NAME>_URL / FORGE_PIN_<NAME>_SHA256, then
# recipe.lock.json, then (URL only) the upstream release URL. NAME is UV, LLVM, GNU_ARM, FABRO. Lock shape:
#   "toolchain": {
#     "uv":      {"version": "0.12.17",      "url": "...", "sha256": "TODO_PIN"},
#     "llvm":    {"version": "19.1.7",       "url": "...", "sha256": "TODO_PIN"},
#     "gnu_arm": {"version": "10.3-2021.07", "url": "...", "sha256": "TODO_PIN"},
#     "fabro":   {"version": "0.362.0",      "url": "TODO_PIN", "sha256": "TODO_PIN"}
#   }
# Any value that is empty, null or starts with TODO_PIN counts as missing.
#
# Exit codes: 0 done (or dry-run / stop-after), 2 usage, 4 refused (pins), 5 unsupported machine or not root.
set -euo pipefail

DRY_RUN=0
CONTAINER=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --container) CONTAINER=1 ;;
    -h|--help) sed -n '2,46p' "$0"; exit 0 ;;
    *) echo "provision: unknown argument: $arg" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FORGE_SITE="${FORGE_SITE:-omniverse2}"
FORGE_USER="${FORGE_USER:-forge}"
FORGE_UID="${FORGE_UID:-}"
FORGE_DATA_DIR="${FORGE_DATA_DIR:-/srv/forge-c}"
FORGE_DATA_DEVICE="${FORGE_DATA_DEVICE:-}"
FORGE_PREFIX="${FORGE_PREFIX:-/opt/forge-c}"
FORGE_CACHE_DIR="${FORGE_CACHE_DIR:-/var/cache/forge-c/downloads}"
FORGE_PYTHON_VERSION="${FORGE_PYTHON_VERSION:-3.13}"
FORGE_UV_VERSION="${FORGE_UV_VERSION:-0.12.17}"
FORGE_LLVM_VERSION="${FORGE_LLVM_VERSION:-19.1.7}"
FORGE_GNU_ARM_VERSION="${FORGE_GNU_ARM_VERSION:-10.3-2021.07}"
FORGE_FABRO_VERSION="${FORGE_FABRO_VERSION:-0.362.0}"
FORGE_FORMAL_VERSION="${FORGE_FORMAL_VERSION:-frama-c-33.0}"
FORGE_FORMAL_PREFIX="${FORGE_FORMAL_PREFIX:-/mnt/data/forge-c/toolchains/opam/root/forge-c}"
FORGE_REPO_URL="${FORGE_REPO_URL:-}"
FORGE_REVISION="${FORGE_REVISION:-}"
FORGE_REPO_DIR="${FORGE_REPO_DIR:-$FORGE_PREFIX/forge-c}"
FORGE_EXTRA_APT="${FORGE_EXTRA_APT:-}"
FORGE_PROVISION_STOP_AFTER="${FORGE_PROVISION_STOP_AFTER:-}"

if [ -z "${FORGE_LOCK_FILE:-}" ]; then
  for c in "$SCRIPT_DIR/../recipe.lock.json" "$SCRIPT_DIR/recipe.lock.json"; do
    if [ -f "$c" ]; then FORGE_LOCK_FILE="$c"; break; fi
  done
fi
FORGE_LOCK_FILE="${FORGE_LOCK_FILE:-}"

# Ubuntu 22.04 packages from "Software on the VM" plus what this script needs (curl, xz, bzip2, jq, socat for the
# in-container model-channel relay). Renode is not in the Ubuntu 22.04 archive: it is not installed here.
APT_PACKAGES=(ca-certificates curl xz-utils bzip2 jq git socat util-linux
  gcc g++ make cmake ninja-build cppcheck gcovr cbmc nginx python3 python3-venv libgmp10 zlib1g)
# Frama-C is not in the Ubuntu 22.04 archive: it comes as the pinned `formal` archive (Frama-C 33.0 + Alt-Ergo from
# the factory's opam switch, unpacked at the same absolute prefix it was built for), like on the factory host.
if [ -n "$FORGE_EXTRA_APT" ]; then
  # shellcheck disable=SC2206
  APT_PACKAGES+=($FORGE_EXTRA_APT)
fi

log() { printf '%s\n' "$*"; }
step() { log "== $*"; }
run() {
  if [ "$DRY_RUN" = 1 ]; then log "PLAN: $*"; else log "RUN: $*"; "$@"; fi
}
forge_home() { getent passwd "$FORGE_USER" | cut -d: -f6 || echo "/home/$FORGE_USER"; }
as_forge() { run runuser -u "$FORGE_USER" -- env HOME="$(forge_home)" PATH="$FORGE_PREFIX/bin:/usr/local/bin:/usr/bin:/bin" "$@"; }
refuse() { log "REFUSED: $*" >&2; exit 4; }

# ---------------------------------------------------------------------------------------------------------- preflight
step "preflight (site=$FORGE_SITE container=$CONTAINER dry_run=$DRY_RUN)"
for p in "${APT_PACKAGES[@]}"; do
  case "$p" in *nvidia*|*cuda*|*nouveau*) refuse "GPU package requested ($p): the factory machine has no GPU software (FR-021)" ;; esac
done
# ------------------------------------------------------------------------------------------------ pins (no changes)
step "pins (lock: ${FORGE_LOCK_FILE:-none})"
lock_get() {  # lock_get <dotted.key.path>; prints "" when the lock or the key is absent
  [ -n "$FORGE_LOCK_FILE" ] && [ -f "$FORGE_LOCK_FILE" ] || { echo ""; return 0; }
  # a bare container base has no python3 before the apt step: then only explicit FORGE_PIN_* values count (the
  # caller derives them from the lock); every download is still verified against its SHA-256 and missing pins refuse
  command -v python3 >/dev/null 2>&1 || { echo ""; return 0; }
  python3 -I -c 'import json,sys
v=json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."):
    v=v.get(k) if isinstance(v,dict) else None
print("" if v is None or isinstance(v,(dict,list)) else v)' "$FORGE_LOCK_FILE" "$1"
}
missing_pin() { case "$1" in ""|None|null|TODO_PIN*) return 0 ;; *) return 1 ;; esac; }

declare -A PIN_URL PIN_SHA PIN_VER
PIN_VER[uv]="$FORGE_UV_VERSION"; PIN_VER[llvm]="$FORGE_LLVM_VERSION"
PIN_VER[gnu_arm]="$FORGE_GNU_ARM_VERSION"; PIN_VER[fabro]="$FORGE_FABRO_VERSION"; PIN_VER[formal]="$FORGE_FORMAL_VERSION"
DEFAULT_URL_uv="https://github.com/astral-sh/uv/releases/download/$FORGE_UV_VERSION/uv-x86_64-unknown-linux-gnu.tar.gz"
DEFAULT_URL_llvm="https://github.com/llvm/llvm-project/releases/download/llvmorg-$FORGE_LLVM_VERSION/LLVM-$FORGE_LLVM_VERSION-Linux-X64.tar.xz"
DEFAULT_URL_gnu_arm="https://developer.arm.com/-/media/Files/downloads/gnu-rm/$FORGE_GNU_ARM_VERSION/gcc-arm-none-eabi-$FORGE_GNU_ARM_VERSION-x86_64-linux.tar.bz2"
DEFAULT_URL_fabro=""   # no verified upstream URL recorded yet: must come from the lock (TODO_PIN)
DEFAULT_URL_formal=""  # built from the factory opam switch: lock or mirror only

problems=()
lock_fabro="$(lock_get fabro_version)"
if ! missing_pin "$lock_fabro" && [ "$lock_fabro" != "$FORGE_FABRO_VERSION" ]; then
  problems+=("fabro_version: lock says $lock_fabro, script pins $FORGE_FABRO_VERSION")
fi
for name in uv llvm gnu_arm fabro formal; do
  NAME="$(echo "$name" | tr '[:lower:]' '[:upper:]')"
  env_url_var="FORGE_PIN_${NAME}_URL"; env_sha_var="FORGE_PIN_${NAME}_SHA256"
  lock_ver="$(lock_get "toolchain.$name.version")"
  lock_url="$(lock_get "toolchain.$name.url")"
  lock_sha="$(lock_get "toolchain.$name.sha256")"
  def_var="DEFAULT_URL_$name"
  url="${!env_url_var:-}"; missing_pin "$url" && url="$lock_url"; missing_pin "$url" && url="${!def_var}"
  sha="${!env_sha_var:-}"; missing_pin "$sha" && sha="$lock_sha"
  if ! missing_pin "$lock_ver" && [ "$lock_ver" != "${PIN_VER[$name]}" ]; then
    problems+=("$name: lock version $lock_ver != pinned ${PIN_VER[$name]}")
  fi
  if missing_pin "$url"; then problems+=("$name: download URL missing (set $env_url_var or toolchain.$name.url)"); fi
  if missing_pin "$sha"; then
    problems+=("$name: SHA-256 missing (set $env_sha_var or toolchain.$name.sha256)")
  elif ! [[ "$sha" =~ ^[0-9a-f]{64}$ ]] || [ "$sha" = "$(printf '0%.0s' {1..64})" ]; then
    problems+=("$name: SHA-256 malformed or placeholder: $sha")
  fi
  PIN_URL[$name]="$url"; PIN_SHA[$name]="$sha"
  log "pin $name ${PIN_VER[$name]} url=${url:-MISSING} sha256=${sha:-MISSING}"
done
[ -n "$FORGE_REVISION" ] || FORGE_REVISION="$(lock_get factory_revision)"
missing_pin "$FORGE_REPO_URL" && problems+=("repo: FORGE_REPO_URL missing")
if missing_pin "$FORGE_REVISION"; then problems+=("repo: FORGE_REVISION / factory_revision missing")
elif ! [[ "$FORGE_REVISION" =~ ^[0-9a-f]{40}$ ]]; then problems+=("repo: revision must be a 40-hex commit, not $FORGE_REVISION"); fi
log "pin repo url=${FORGE_REPO_URL:-MISSING} revision=${FORGE_REVISION:-MISSING}"

if [ "${#problems[@]}" -gt 0 ]; then
  for p in "${problems[@]}"; do log "PIN MISSING: $p"; done
  if [ "$DRY_RUN" = 1 ]; then
    log "dry-run: ${#problems[@]} pin problem(s); a real run would REFUSE here, before any change"
  else
    refuse "${#problems[@]} pin problem(s); nothing was changed (verification is never skipped)"
  fi
fi
if [ "$FORGE_PROVISION_STOP_AFTER" = "pins" ]; then
  log "STOP after pin verification (FORGE_PROVISION_STOP_AFTER=pins); nothing was changed"
  exit 0
fi
os_id="$(. /etc/os-release 2>/dev/null && echo "${ID:-}:${VERSION_ID:-}")" || os_id="unknown"
if [ "$os_id" != "ubuntu:22.04" ]; then
  if [ "$DRY_RUN" = 1 ]; then log "NOTE: this machine is $os_id; provisioning targets ubuntu:22.04"; else log "unsupported OS $os_id (needs ubuntu:22.04)" >&2; exit 5; fi
fi
if [ "$(uname -m)" != "x86_64" ]; then
  if [ "$DRY_RUN" = 1 ]; then log "NOTE: arch $(uname -m); pins are for x86_64"; else log "unsupported arch $(uname -m)" >&2; exit 5; fi
fi
if [ "$DRY_RUN" = 0 ] && [ "$(id -u)" != 0 ]; then log "provision must run as root (cloud-init or docker build)" >&2; exit 5; fi

# ---------------------------------------------------------------------------------------------------- apt packages
step "apt packages (Ubuntu 22.04 archive; no GPU packages)"
missing_pkgs=()
for p in "${APT_PACKAGES[@]}"; do
  dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || missing_pkgs+=("$p")
done
if [ "${#missing_pkgs[@]}" -gt 0 ]; then
  run env DEBIAN_FRONTEND=noninteractive apt-get update -q
  run env DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends "${missing_pkgs[@]}"
else
  log "ok: all ${#APT_PACKAGES[@]} packages installed"
fi

# --------------------------------------------------------------------------------------------------- service account
step "service account $FORGE_USER"
if id "$FORGE_USER" >/dev/null 2>&1; then
  log "ok: $FORGE_USER exists"
else
  run useradd --create-home --shell /bin/bash ${FORGE_UID:+--uid "$FORGE_UID"} "$FORGE_USER"
fi
if [ "$CONTAINER" = 1 ]; then
  log "skip (container): lingering needs systemd-logind"
elif [ -e "/var/lib/systemd/linger/$FORGE_USER" ]; then
  log "ok: lingering enabled"
else
  run loginctl enable-linger "$FORGE_USER"
fi

# ------------------------------------------------------------------------------------------------------ data volume
step "data volume $FORGE_DATA_DIR"
if [ "$CONTAINER" = 1 ]; then
  log "skip (container): the data volume is bind-mounted at run time (compose.yaml)"
elif [ -n "$FORGE_DATA_DEVICE" ]; then
  if grep -qs "[[:space:]]$FORGE_DATA_DIR[[:space:]]" /etc/fstab; then
    log "ok: fstab entry for $FORGE_DATA_DIR"
  else
    run sh -c "printf '%s %s ext4 defaults,nofail 0 2\n' '$FORGE_DATA_DEVICE' '$FORGE_DATA_DIR' >> /etc/fstab"
  fi
  run mkdir -p "$FORGE_DATA_DIR"
  mountpoint -q "$FORGE_DATA_DIR" 2>/dev/null && log "ok: mounted" || run mount "$FORGE_DATA_DIR"
else
  log "note: FORGE_DATA_DEVICE empty; the mount is cloud-init's (mounts:) or the platform's"
fi
run mkdir -p "$FORGE_DATA_DIR"
run chown "$FORGE_USER:" "$FORGE_DATA_DIR"
run chmod 0750 "$FORGE_DATA_DIR"

# -------------------------------------------------------------------------------------- verified release tarballs
fetch_verified() {  # fetch_verified <name> -> sets FETCHED to the verified cache path
  local name="$1" url="${PIN_URL[$1]}" sha="${PIN_SHA[$1]}" file
  url="${url:-UNPINNED-URL}"; sha="${sha:-UNPINNED-SHA256}"   # only reachable in --dry-run (a real run refused earlier)
  file="$FORGE_CACHE_DIR/$sha-$(basename "${url%%\?*}")"
  FETCHED="$file"
  if [ -f "$file" ] && [ "$DRY_RUN" = 0 ] && echo "$sha  $file" | sha256sum -c --status; then
    log "ok: $name cached and verified"; return 0
  fi
  run mkdir -p "$FORGE_CACHE_DIR"
  run curl -fsSL --proto '=https,http' --retry 3 -o "$file.part" "$url"   # http only for a local mirror: the SHA-256 is the check
  if [ "$DRY_RUN" = 1 ]; then log "PLAN: verify sha256 $sha of $file.part, then rename"; return 0; fi
  if ! echo "$sha  $file.part" | sha256sum -c --status; then
    rm -f "$file.part"; refuse "$name: SHA-256 mismatch for $url (expected $sha)"
  fi
  mv -f "$file.part" "$file"
}
install_tarball() {  # install_tarball <name> <dest> <strip>
  local name="$1" dest="$2" strip="$3" sha="${PIN_SHA[$1]}"
  if [ -f "$dest/.forge-pin" ] && [ "$(cat "$dest/.forge-pin")" = "$sha" ]; then log "ok: $name installed at $dest"; return 0; fi
  fetch_verified "$name"
  run rm -rf "$dest.new"
  run mkdir -p "$dest.new"
  run tar -xf "$FETCHED" -C "$dest.new" --strip-components="$strip" --no-same-owner
  run sh -c "printf '%s\n' '$sha' > '$dest.new/.forge-pin'"
  run rm -rf "$dest"
  run mv "$dest.new" "$dest"
}
step "uv $FORGE_UV_VERSION, LLVM $FORGE_LLVM_VERSION, GNU Arm $FORGE_GNU_ARM_VERSION, Fabro $FORGE_FABRO_VERSION"
run mkdir -p "$FORGE_PREFIX/bin" "$FORGE_PREFIX/toolchains"
install_tarball uv "$FORGE_PREFIX/uv-$FORGE_UV_VERSION" 1
install_tarball llvm "$FORGE_PREFIX/toolchains/llvm-$FORGE_LLVM_VERSION" 1
install_tarball gnu_arm "$FORGE_PREFIX/toolchains/gcc-arm-none-eabi-$FORGE_GNU_ARM_VERSION" 1
install_tarball fabro "$FORGE_PREFIX/fabro-$FORGE_FABRO_VERSION" 0   # keeps fabro-x86_64-unknown-linux-musl/fabro
FABRO_BIN="$FORGE_PREFIX/fabro-$FORGE_FABRO_VERSION/fabro-x86_64-unknown-linux-musl/fabro"
run ln -sfn "$FORGE_PREFIX/uv-$FORGE_UV_VERSION/uv" "$FORGE_PREFIX/bin/uv"
run ln -sfn "$FABRO_BIN" "$FORGE_PREFIX/bin/fabro"
install_tarball formal "$FORGE_FORMAL_PREFIX" 1   # Frama-C + Alt-Ergo at the prefix their absolute paths expect
for t in frama-c frama-c-script alt-ergo; do run ln -sfn "$FORGE_FORMAL_PREFIX/bin/$t" "$FORGE_PREFIX/bin/$t"; done
if [ "$DRY_RUN" = 0 ]; then
  "$FORGE_FORMAL_PREFIX/bin/frama-c" -version 2>&1 | grep -q "${FORGE_FORMAL_VERSION#frama-c-}" || refuse "frama-c -version is not $FORGE_FORMAL_VERSION"
fi
if [ "$DRY_RUN" = 0 ]; then
  FABRO_NO_UPGRADE_CHECK=1 "$FABRO_BIN" --version 2>&1 | grep -q "$FORGE_FABRO_VERSION" || refuse "fabro --version is not $FORGE_FABRO_VERSION"
fi

step "environment profile"
PROFILE="/etc/profile.d/forge-c.sh"
PROFILE_BODY="# Forge-C factory machine (managed by provision.sh)
export PATH=\"$FORGE_PREFIX/bin:$FORGE_PREFIX/toolchains/llvm-$FORGE_LLVM_VERSION/bin:$FORGE_PREFIX/toolchains/gcc-arm-none-eabi-$FORGE_GNU_ARM_VERSION/bin:\$PATH\"
export FORGE_FABRO_BIN=\"$FABRO_BIN\"
export FABRO_NO_UPGRADE_CHECK=1
export FORGE_DATA_DIR=\"$FORGE_DATA_DIR\""
if [ -f "$PROFILE" ] && [ "$(cat "$PROFILE")" = "$PROFILE_BODY" ]; then
  log "ok: $PROFILE current"
elif [ "$DRY_RUN" = 1 ]; then
  log "PLAN: write $PROFILE (PATH, FORGE_FABRO_BIN, FABRO_NO_UPGRADE_CHECK=1, FORGE_DATA_DIR)"
else
  log "RUN: write $PROFILE"; printf '%s\n' "$PROFILE_BODY" > "$PROFILE"; chmod 0644 "$PROFILE"
fi

# ------------------------------------------------------------------------------------------ Python and the factory
step "Python $FORGE_PYTHON_VERSION (uv) and the factory checkout at $FORGE_REVISION"
as_forge uv python install "$FORGE_PYTHON_VERSION"
run mkdir -p "$(dirname "$FORGE_REPO_DIR")"
if [ -d "$FORGE_REPO_DIR/.git" ]; then
  head="$(git -C "$FORGE_REPO_DIR" rev-parse HEAD 2>/dev/null || true)"
  if [ "$head" = "$FORGE_REVISION" ]; then log "ok: checkout at $FORGE_REVISION"; else
    as_forge git -C "$FORGE_REPO_DIR" fetch --quiet origin "$FORGE_REVISION"
    as_forge git -C "$FORGE_REPO_DIR" checkout --quiet --detach "$FORGE_REVISION"
  fi
else
  run install -d -o "$FORGE_USER" -m 0750 "$FORGE_REPO_DIR"
  as_forge git clone --quiet --no-checkout "$FORGE_REPO_URL" "$FORGE_REPO_DIR"
  as_forge git -C "$FORGE_REPO_DIR" checkout --quiet --detach "$FORGE_REVISION"
fi
if [ "$DRY_RUN" = 0 ]; then
  got="$(git -C "$FORGE_REPO_DIR" rev-parse HEAD)"
  [ "$got" = "$FORGE_REVISION" ] || refuse "checkout is at $got, expected $FORGE_REVISION"
fi
as_forge sh -c "cd '$FORGE_REPO_DIR' && uv sync --frozen --python '$FORGE_PYTHON_VERSION'"   # uv.lock hashes verify every wheel

# -------------------------------------------------------------------------------------------------------- record
step "record"
if [ "$DRY_RUN" = 1 ]; then
  log "PLAN: write $FORGE_PREFIX/provision-record.json (pins, revision, container=$CONTAINER)"
  log "dry-run complete: nothing was changed"
  exit 0
fi
python3 -I -c 'import json,sys,datetime
names=["uv","llvm","gnu_arm","fabro"]; a=sys.argv[1:]
rec={"schema":"forge-c/017/factory-provision","at":datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
     "site":a[0],"container":a[1]=="1","revision":a[2],"gpu_software":False,
     "pins":{n:{"version":a[3+3*i],"url":a[4+3*i],"sha256":a[5+3*i]} for i,n in enumerate(names)}}
print(json.dumps(rec,indent=2,sort_keys=True))' "$FORGE_SITE" "$CONTAINER" "$FORGE_REVISION" \
  "${PIN_VER[uv]}" "${PIN_URL[uv]}" "${PIN_SHA[uv]}" "${PIN_VER[llvm]}" "${PIN_URL[llvm]}" "${PIN_SHA[llvm]}" \
  "${PIN_VER[gnu_arm]}" "${PIN_URL[gnu_arm]}" "${PIN_SHA[gnu_arm]}" "${PIN_VER[fabro]}" "${PIN_URL[fabro]}" "${PIN_SHA[fabro]}" \
  > "$FORGE_PREFIX/provision-record.json"
log "provision PASS site=$FORGE_SITE container=$CONTAINER revision=$FORGE_REVISION"
