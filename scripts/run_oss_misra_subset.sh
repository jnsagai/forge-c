#!/usr/bin/env bash
# Open-source Cppcheck MISRA addon; incomplete rule coverage by design.
# Requires installed addon package. Does NOT claim MISRA compliance.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
command -v cppcheck >/dev/null 2>&1 || { echo 'MISSING: cppcheck' >&2; exit 2; }
# Pass explicit addon (e.g. /usr/share/cppcheck/addons/misra.py) or rely on cppcheck search.
addon="${CPPCHECK_MISRA_ADDON:-misra}"
mkdir -p "$root/evidence/oss-demo"
if ! cppcheck --std=c11 --addon="$addon" --enable=style --error-exitcode=1 \
    -I"$root/drivers/demo_rcc/include" "$root/drivers/demo_rcc/src/forge_rcc_demo.c" \
    > "$root/evidence/oss-demo/misra-subset.log" 2>&1; then
  cat "$root/evidence/oss-demo/misra-subset.log" >&2
  exit 1
fi
echo 'MISRA SUBSET CHECK EXECUTED: NOT FULL MISRA C COMPLIANCE'
