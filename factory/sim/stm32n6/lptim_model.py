# ruff: noqa: F821 - Renode injects `request` into Python peripheral scripts
# Behavioural LPTIM1 model (RM0486 rev 4 chapter 58, feature 014 operation-24 campaign) with polled time: while the
# counter runs, every read of LPTIM_CNT (0x01C) or LPTIM_ISR (0x000) advances one kernel clock; the counter steps every
# 2^PRESC clocks (LPTIM_CFGR.PRESC bits 11:9) from 0 up to LPTIM_ARR (0x018), sets ISR.ARRM (bit 1) when it reaches ARR
# and at the next step wraps to 0 with an update event (ISR.UE bit 7; a preloaded ARR is loaded); in Single mode it
# stops at that wrap. LPTIM_CR (0x010): ENABLE (bit 0) is storage; CNTSTRT (bit 2), SNGSTRT (bit 1) and COUNTRST (bit 3)
# act only while ENABLE is set and read back 0 (COUNTRST clears the counter at once; the 3-clock synchronisation is not
# modelled); RSTARE (bit 4) is storage. A write to LPTIM_ARR or LPTIM_DIER (0x008) while ENABLE is set is accepted and
# sets ISR.ARROK (bit 4) or ISR.DIEROK (bit 24) at once (APB-to-kernel latency not modelled; ARR loads at once unless
# LPTIM_CFGR.PRELOAD (bit 22) is set and the counter runs); while disabled it is ignored. A write to LPTIM_CFGR (0x00C)
# while ENABLE is set is ignored (RM0486 58.7.10). LPTIM_ICR (0x004) is write-only (reads 0): each bit written 1 clears
# the ISR bit of the same position. Disabling stops the counter, which keeps its value. LPTIM_ARR resets to 1, the
# others to 0. Capture/compare, external clock, triggers, encoder and the repetition counter are storage, not modelled.
# IronPython 2.7: no f-strings, no digit separators, no int.to_bytes.
SCENARIO = "default"
ISR, ICR, DIER, CFGR, CR, ARR, CNT = 0x000, 0x004, 0x008, 0x00C, 0x010, 0x018, 0x01C
ENABLE, SNGSTRT, CNTSTRT, COUNTRST = 0x1, 0x2, 0x4, 0x8
ARRM, ARROK, UE, DIEROK = 0x2, 0x10, 0x80, 0x1000000
PRELOAD = 0x400000


def _step():
    st["clk"] += 1
    if st["clk"] < (1 << ((regs[CFGR] >> 9) & 0x7)):
        return
    st["clk"] = 0
    if regs[CNT] >= regs[ARR]:
        regs[CNT] = 0
        regs[ISR] |= UE
        if st["pending_arr"] is not None:
            regs[ARR] = st["pending_arr"]
            st["pending_arr"] = None
        if st["mode"] == "single":
            st["mode"] = None
        return
    regs[CNT] += 1
    if regs[CNT] == regs[ARR]:
        regs[ISR] |= ARRM


if request.IsInit:
    regs = {ISR: 0, DIER: 0, CFGR: 0, CR: 0, 0x014: 0, ARR: 1, CNT: 0, 0x024: 0, 0x028: 0, 0x02C: 0, 0x034: 0}
    st = {"mode": None, "clk": 0, "pending_arr": None}
elif request.IsRead:
    off = request.Offset
    if off in (CNT, ISR) and st["mode"] is not None and regs[CR] & ENABLE:
        _step()
    if off == ICR:
        request.Value = 0
    else:
        request.Value = regs.get(off, 0)
    if off == CNT and regs[CR] & 0x10:  # RSTARE: a read resets the counter
        regs[CNT] = 0
elif request.IsWrite:
    off = request.Offset
    v = request.Value & 0xFFFFFFFF
    enabled = regs[CR] & ENABLE
    if off == CR:
        regs[CR] = v & (ENABLE | 0x10)
        if v & ENABLE:
            if v & COUNTRST:
                regs[CNT] = 0
            if v & CNTSTRT:
                st["mode"] = "continuous"
            elif v & SNGSTRT:
                st["mode"] = "single"
        else:
            st["mode"] = None
    elif off == ICR:
        regs[ISR] &= ~v & 0xFFFFFFFF
    elif off == ARR:
        if enabled:
            if regs[CFGR] & PRELOAD and st["mode"] is not None:
                st["pending_arr"] = v & 0xFFFF
            else:
                regs[ARR] = v & 0xFFFF
            regs[ISR] = (regs[ISR] & ~UE) | ARROK
    elif off == DIER:
        if enabled:
            regs[DIER] = v
            regs[ISR] |= DIEROK
    elif off == CFGR:
        if not enabled:
            regs[CFGR] = v
    elif off not in (ISR, CNT):
        regs[off] = v
