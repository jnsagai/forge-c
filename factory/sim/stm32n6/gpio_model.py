# ruff: noqa: F821 - Renode injects `request` into Python peripheral scripts
# Behavioural GPIOA model (RM0486 rev 4 chapter 15, feature 015) with the port A reset values: GPIO_MODER (0x00)
# 0xABFFEFFF, GPIO_OSPEEDR (0x08) 0x0C000000, GPIO_PUPDR (0x0C) 0x64000000, the others 0. GPIO_BSRR (0x18,
# write-only) sets the GPIO_ODR (0x14) bits of BSy (bits 15:0) and clears those of BRy (bits 31:16), BSy winning when
# both are set; GPIO_BRR (0x28, write-only) clears GPIO_ODR bits. GPIO_IDR (0x10, read-only) reads GPIO_ODR back for
# pins in output (MODEy = 01) or alternate function (10) mode, 1 for input pins (00) with pull-up (PUPDy = 01) and 0
# otherwise (pull-down, floating, analog). GPIO_OTYPER (0x04), GPIO_AFRL (0x20) and GPIO_AFRH (0x24) are storage. The
# lock sequence (GPIO_LCKR 0x1C), TrustZone, delay and advanced configuration registers are out of the work orders'
# scope: storage, not modelled.
SCENARIO = "default"


def _idr():
    v = 0
    for y in range(16):
        mode = (regs[0x00] >> (2 * y)) & 0x3
        pull = (regs[0x0C] >> (2 * y)) & 0x3
        if mode in (1, 2):
            v |= regs[0x14] & (1 << y)
        elif mode == 0 and pull == 1:
            v |= 1 << y
    return v


if request.IsInit:
    regs = {0x00: 0xABFFEFFF, 0x04: 0, 0x08: 0x0C000000, 0x0C: 0x64000000, 0x14: 0, 0x1C: 0, 0x20: 0, 0x24: 0,
            0x30: 0, 0x34: 0, 0x38: 0, 0x40: 0, 0x44: 0, 0x48: 0, 0x4C: 0}
elif request.IsRead:
    off = request.Offset
    if off == 0x10:
        request.Value = _idr()
    elif off in (0x18, 0x28):
        request.Value = 0
    else:
        request.Value = regs.get(off, 0)
elif request.IsWrite:
    off = request.Offset
    v = request.Value & 0xFFFFFFFF
    if off == 0x18:
        regs[0x14] = ((regs[0x14] & ~((v >> 16) & 0xFFFF)) | (v & 0xFFFF)) & 0xFFFF
    elif off == 0x28:
        regs[0x14] &= ~(v & 0xFFFF)
    elif off == 0x14:
        regs[0x14] = v & 0xFFFF
    elif off != 0x10:
        regs[off] = v
