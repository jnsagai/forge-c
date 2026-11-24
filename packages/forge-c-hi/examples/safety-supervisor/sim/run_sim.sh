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
# store the CRC-32/MPEG-2 reference values of the program code and the configuration block (CON-SUP-124, CON-SUP-142)
for s in text:app_crc cfg:cfg_crc; do
  : > "$out/sec.bin"; arm-none-eabi-objcopy -O binary -j ".${s%%:*}" "$out/t.elf" "$out/sec.bin"
  python3 -c '
import sys
c = 0xFFFFFFFF
for b in open(sys.argv[1], "rb").read():
    c ^= b << 24
    for _ in range(8):
        c = ((c << 1) ^ 0x04C11DB7 if c & 0x80000000 else c << 1) & 0xFFFFFFFF
open(sys.argv[2], "wb").write(c.to_bytes(4, "little"))' "$out/sec.bin" "$out/crc.bin"
  arm-none-eabi-objcopy --update-section ".${s##*:}=$out/crc.bin" "$out/t.elf"
done
cat > "$out/go.resc" <<RESC
\$cs=@$root/$here/HiStm32n6Watchdogs.cs
\$repl=@$root/$here/stm32n6_supervisor.repl
\$elf=@$out/t.elf
\$uart=@$out/uart.txt
\$seconds="${SIM_SECONDS:-5}"
include @$root/$here/run.resc
RESC
# optional stimulus: <program>.uart, one "<microseconds> <text>" per line. After that much more simulated time the text
# and a line feed are received by USART1, one character every 87 us.
if [ -f "${prog%.c}.uart" ]; then python3 - "${prog%.c}.uart" >> "$out/go.resc" <<'PY'
import sys
for line in open(sys.argv[1], encoding="ascii"):
    if line.strip() and not line.startswith("#"):
        us, _, text = line.rstrip("\n").partition(" ")
        print(f'emulation RunFor "{int(us) / 1e6:.6f}"')
        for c in text + "\n":
            print(f'usart1 WriteChar {ord(c)}')
            print('emulation RunFor "0.000087"')
PY
fi
printf 'emulation RunFor $seconds\nquit\n' >> "$out/go.resc"
"$RENODE" --console --disable-xwt --plain -e "include @$out/go.resc; quit" > "$out/log.txt" 2>&1 < /dev/null || { tail -5 "$out/log.txt" >&2; exit 3; }
[ -f "$out/uart.txt" ] || { grep -i error -A3 "$out/log.txt" | head -5 >&2; exit 3; }
cat "$out/uart.txt"
