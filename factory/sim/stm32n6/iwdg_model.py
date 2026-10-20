# ruff: noqa: F821 - Renode injects `request` into Python peripheral scripts
# Behavioural IWDG model (RM0486 rev 4 chapter 59, feature 009): IWDG_KR (0x000) is write-only (reads 0) and takes
# keys: 0x5555 enables write access to IWDG_PR (0x004), IWDG_RLR (0x008) and IWDG_WINR (0x010), any other key locks
# them again, 0xCCCC starts the watchdog (IWDG_SR.ONF, bit 8), 0xAAAA refreshes the counter. An accepted PR/RLR/WINR
# write sets IWDG_SR.PVU/RVU/WVU (bits 0/1/2) until the next read of IWDG_SR ("default"), or for ever in scenario
# "never_ready" (the caller's bounded poll must give up). IWDG_RLR resets to 0x00000FFF; other registers are storage.
SCENARIO = "default"
if request.IsInit:
    regs = {0x008: 0x00000FFF}
    unlocked = False
    pending = 0
elif request.IsRead:
    off = request.Offset
    if off == 0x000:
        request.Value = 0
    elif off == 0x00C:
        request.Value = regs.get(0x00C, 0) | pending
        if SCENARIO != "never_ready":
            pending = 0
    else:
        request.Value = regs.get(off, 0)
elif request.IsWrite:
    off = request.Offset
    v = request.Value & 0xFFFFFFFF
    if off == 0x000:
        key = v & 0xFFFF
        if key == 0x5555:
            unlocked = True
        else:
            unlocked = False
            if key == 0xCCCC:
                regs[0x00C] = regs.get(0x00C, 0) | 0x100
    elif off in (0x004, 0x008, 0x010):
        if unlocked:
            regs[off] = v
            pending = pending | {0x004: 0x1, 0x008: 0x2, 0x010: 0x4}[off]
    elif off != 0x00C:
        regs[off] = v
