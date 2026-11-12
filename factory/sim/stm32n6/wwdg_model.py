# ruff: noqa: F821 - Renode injects `request` into Python peripheral scripts
# Behavioural WWDG model (RM0486 rev 4 chapter 60, feature 014 operation-24 campaign): WWDG_CR (0x000) and WWDG_CFR
# (0x004) reset to 0x7F, WWDG_SR (0x008) to 0. WWDG_CR.WDGA (bit 7) and WWDG_CFR.EWI (bit 9) are set by writing 1 and
# keep their value on a write of 0 (cleared only by a reset, RM0486 60.6.1/60.6.2); WWDG_SR.EWIF (bit 0) is cleared by
# writing 0 and unchanged by writing 1 (60.6.3). While WDGA is set, every read of WWDG_CR advances time by one counter
# step (deterministic polling): T[6:0] decrements by one down to 0x40, where it stops and sets EWIF. The watchdog reset
# (T decremented from 0x40 to 0x3F, or a refresh outside the window) is not modelled. IronPython 2.7: no f-strings.
SCENARIO = "default"
WDGA = 0x80
EWI = 0x200

if request.IsInit:
    regs = {0x000: 0x7F, 0x004: 0x7F, 0x008: 0}
elif request.IsRead:
    off = request.Offset
    if off == 0x000 and regs[0x000] & WDGA:
        t = regs[0x000] & 0x7F
        if t > 0x40:
            t -= 1
            regs[0x000] = (regs[0x000] & WDGA) | t
        if t == 0x40:
            regs[0x008] |= 1
    request.Value = regs.get(off, 0)
elif request.IsWrite:
    off = request.Offset
    v = request.Value & 0xFFFFFFFF
    if off == 0x000:
        regs[0x000] = (regs[0x000] & WDGA) | (v & WDGA) | (v & 0x7F)
    elif off == 0x004:
        regs[0x004] = (regs[0x004] & EWI) | (v & EWI) | (v & 0x387F)
    elif off == 0x008:
        regs[0x008] &= v & 1
