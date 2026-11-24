#!/bin/sh
# run_sim.sh <program.c>: build one target program with the product sources and run it on the simulator platform.
# Prints the text of the diagnostic USART (the HI-TEST lines). Environment: RENODE (path of renode), SIM_SECONDS.
# Run from the project root. Files next to the program that are not test_*.c (the hardware port) are built in.
set -eu
prog=$1; here=$(dirname "$0"); root=$(pwd); dir=$(dirname "$prog"); out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
RENODE=${RENODE:-renode}
port=$(find "$dir" -maxdepth 1 -name '*.c' ! -name 'test_*.c' | sort)
src=$(find src -name '*.c' 2>/dev/null | sort)
arm-none-eabi-gcc -mcpu=cortex-m55 -mthumb -mfloat-abi=soft -std=c11 -O2 -Wall -Wextra -Werror -Iinclude -I"$dir" \
  -nostartfiles -specs=nano.specs -specs=nosys.specs -T "$here/link.ld" "$here/startup.c" "$prog" $port $src -o "$out/t.elf" >&2
cat > "$out/go.resc" <<RESC
\$cs=@$root/$here/HiStm32n6Watchdogs.cs
\$repl=@$root/$here/stm32n6_supervisor.repl
\$elf=@$out/t.elf
\$uart=@$out/uart.txt
\$seconds="${SIM_SECONDS:-5}"
include @$root/$here/run.resc
RESC
"$RENODE" --console --disable-xwt --plain -e "include @$out/go.resc; quit" > "$out/log.txt" 2>&1 < /dev/null || { tail -5 "$out/log.txt" >&2; exit 3; }
[ -f "$out/uart.txt" ] || { grep -i error -A3 "$out/log.txt" | head -5 >&2; exit 3; }
cat "$out/uart.txt"
