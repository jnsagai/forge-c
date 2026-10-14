#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
command -v cbmc >/dev/null 2>&1 || { echo 'MISSING OSS tool: cbmc' >&2; exit 2; }
mkdir -p "$root/evidence/oss-demo"
cd "$root"
cbmc tests/formal/cbmc_rcc_harness.c drivers/demo_rcc/src/forge_rcc_demo.c \
  --function main --bounds-check --pointer-check --signed-overflow-check \
  --unsigned-overflow-check --unwind 2 -I drivers/demo_rcc/include \
  > evidence/oss-demo/cbmc.log 2>&1 || {
    tail -60 evidence/oss-demo/cbmc.log >&2; exit 1;
  }
echo 'CBMC demonstrator completed; review full assumptions/proof scope before making safety claims.'
