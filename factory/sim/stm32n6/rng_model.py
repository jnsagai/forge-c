# ruff: noqa: F821 - Renode injects `request` into Python peripheral scripts
# Behavioural RNG model (RM0486 rev 4 chapter 47, feature 014 operation-24 campaign): RNG_CR (0x000) resets to
# 0x00800D00, RNG_SR (0x004) and RNG_DR (0x008) to 0, RNG_NSCR (0x00C) to 0x0003FFFF, RNG_HTCR (0x010) to 0x000072AC.
# RNG_CR.CED (bit 5) changes only in a write with RNG_CR.CONDRST (bit 30) set in the same access (RM0486 47.7.1); a
# write with CONDRST = 1 clears RNG_SR and the data. CONFIGLOCK (bit 31) is set-only and, once set, configuration bits
# 29:4 keep their value. While RNG_CR.RNGEN (bit 2) is set and CONDRST is 0, RNG_SR.DRDY (bit 0) reads 1 and each read
# of RNG_DR returns the next value of a 32-bit xorshift sequence seeded with 0x2545F491 (0xE124B63A, 0x8B9A74AB, ...,
# never 0); otherwise DRDY and RNG_DR read 0. RNG_SR.CEIS (bit 5) and SEIS (bit 6) are rc_w0; CECS/SECS (bits 1/2) are
# read-only. Clock and seed errors are not produced (scenario "seed_error" sets SECS and SEIS for error-path tests).
# IronPython 2.7: no f-strings, no int.to_bytes.
SCENARIO = "default"
CONDRST = 0x40000000
LOCK = 0x80000000
CED = 0x20
CFG = 0x3FFFFFF0  # configuration bits 29:4, written only with CONDRST (CED, ARDIS, CONFIG1/2/3, NISTC, CLKDIV)


def _next(x):
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFFFFFF
    return x


def _ready():
    return (regs[0x000] & 0x4) and not (regs[0x000] & CONDRST)


if request.IsInit:
    regs = {0x000: 0x00800D00, 0x004: 0, 0x00C: 0x0003FFFF, 0x010: 0x000072AC}
    state = {"x": 0x2545F491}
    if SCENARIO == "seed_error":
        regs[0x004] = 0x44
elif request.IsRead:
    off = request.Offset
    if off == 0x004:
        request.Value = (regs[0x004] & 0x66) | (1 if _ready() else 0)
    elif off == 0x008:
        if _ready():
            state["x"] = _next(state["x"])
            request.Value = state["x"]
        else:
            request.Value = 0
    else:
        request.Value = regs.get(off, 0)
elif request.IsWrite:
    off = request.Offset
    v = request.Value & 0xFFFFFFFF
    if off == 0x000:
        old = regs[0x000]
        keep = CFG if (old & LOCK or not v & CONDRST) else 0
        regs[0x000] = (old & (keep | LOCK)) | (v & ~keep & ~LOCK & 0x7FFFFFFC) | (v & LOCK)
        if v & CONDRST:
            regs[0x004] = 0
    elif off == 0x004:
        regs[0x004] &= (v & 0x60) | 0x06
    elif off in (0x00C, 0x010):
        if not regs[0x000] & LOCK and regs[0x000] & CONDRST:
            regs[off] = v
