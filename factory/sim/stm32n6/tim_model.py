# ruff: noqa: F821 - Renode injects `request` into Python peripheral scripts
# Behavioural TIM2 model (RM0486 rev 4 chapter 54, feature 015), 32-bit counter, internal clock only. Time advances by
# one kernel clock on every read of TIM_CNT (0x24) or TIM_SR (0x10) while TIM_CR1.CEN (bit 0) is set, so polling
# loops are deterministic. The counter steps every (prescaler + 1) clocks: up to TIM_ARR (0x2C) then 0 (DIR bit 4 = 0),
# down to 0 then TIM_ARR (DIR = 1), or up then down when TIM_CR1.CMS (bits 6:5) is not 0 (DIR then follows the
# counter). Each overflow/underflow is an update event (UEV): unless TIM_CR1.UDIS (bit 1) is set it sets TIM_SR.UIF
# (bit 0), loads the prescaler shadow from TIM_PSC (0x28) and, with TIM_CR1.ARPE (bit 7), the auto-reload shadow from
# TIM_ARR; in one-pulse mode (TIM_CR1.OPM, bit 3) it clears CEN. Without ARPE TIM_ARR takes effect at once.
# TIM_EGR.UG (0x14 bit 0) re-initialises the counter (0, or the auto-reload value down-counting) and the prescaler and,
# unless UDIS is set, loads the shadows and sets UIF unless TIM_CR1.URS (bit 2) is set. TIM_SR is rc_w0 (a written 0
# clears a flag, 1 leaves it); TIM_EGR reads 0. TIM_ARR resets to 0xFFFFFFFF, the other registers to 0. Capture/compare,
# slave mode, encoder, DMA, interrupts and dithering are out of the work orders' scope: storage, not modelled.
SCENARIO = "default"


def _uev(by_ug=False):
    global sr, psc_shadow, arr_shadow
    cr1 = regs[0x00]
    if cr1 & 0x2:  # UDIS: no update event
        return
    psc_shadow = regs[0x28] & 0xFFFF
    arr_shadow = regs[0x2C]
    if not (by_ug and cr1 & 0x4):  # URS: UG does not set UIF
        sr |= 0x1
    if cr1 & 0x8 and not by_ug:  # one-pulse mode
        regs[0x00] &= ~0x1


def _arr():
    return arr_shadow if regs[0x00] & 0x80 else regs[0x2C]


def _tick():
    global pc, cnt, up
    cr1 = regs[0x00]
    if not cr1 & 0x1:
        return
    pc += 1
    if pc <= psc_shadow:
        return
    pc = 0
    arr = _arr()
    center = cr1 & 0x60
    going_up = up if center else not cr1 & 0x10
    if going_up:
        if cnt >= arr:
            if center:
                up = False
                cnt = arr - 1 if arr else 0
            else:
                cnt = 0
            _uev()
        else:
            cnt += 1
    else:
        if cnt == 0:
            if center:
                up = True
                cnt = 1 if arr else 0
            else:
                cnt = arr
            _uev()
        else:
            cnt -= 1
    if center:
        regs[0x00] = (regs[0x00] & ~0x10) | (0 if up else 0x10)


if request.IsInit:
    regs = {0x00: 0, 0x04: 0, 0x08: 0, 0x0C: 0, 0x18: 0, 0x1C: 0, 0x20: 0, 0x28: 0, 0x2C: 0xFFFFFFFF, 0x34: 0,
            0x38: 0, 0x3C: 0, 0x40: 0, 0x48: 0, 0x4C: 0, 0x5C: 0, 0x60: 0, 0x64: 0, 0x68: 0}
    sr, cnt, pc, up = 0, 0, 0, True
    psc_shadow, arr_shadow = 0, 0xFFFFFFFF
elif request.IsRead:
    off = request.Offset
    if off == 0x24:
        _tick()
        request.Value = cnt
    elif off == 0x10:
        _tick()
        request.Value = sr
    elif off == 0x14:
        request.Value = 0
    else:
        request.Value = regs.get(off, 0)
elif request.IsWrite:
    off = request.Offset
    v = request.Value & 0xFFFFFFFF
    if off == 0x10:
        sr &= v
    elif off == 0x14:
        if v & 0x1:
            pc = 0
            cnt = _arr() if (regs[0x00] & 0x10 and not regs[0x00] & 0x60) else 0
            _uev(by_ug=True)
            if not regs[0x00] & 0x2:
                cnt = arr_shadow if (regs[0x00] & 0x10 and not regs[0x00] & 0x60) else 0
    elif off == 0x24:
        cnt = v
    elif off == 0x28:
        regs[0x28] = v & 0xFFFF
    elif off == 0x00:
        regs[0x00] = v
        if v & 0x60:
            up = not v & 0x10
    else:
        regs[off] = v
