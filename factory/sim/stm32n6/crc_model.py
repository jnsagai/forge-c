# ruff: noqa: F821 - Renode injects `request` into Python peripheral scripts
# Behavioural CRC model (RM0486 rev 4 chapter 26, feature 015): a 32-bit write to CRC_DR (0x000) combines the word with
# the current CRC (MSB first, polynomial CRC_POL 0x014 of size CRC_CR.POLYSIZE bits 4:3 = 32/16/8/7 bits), after the
# input reversal CRC_CR.REV_IN (bits 6:5) of type CRC_CR.RTYPE_IN (bit 9): bit level (none, by byte, by half-word, by
# word) or, with RTYPE_IN, half-word (01) or byte (10) reversal by word; a read of CRC_DR returns the CRC after the
# output reversal CRC_CR.REV_OUT (bits 8:7) of type CRC_CR.RTYPE_OUT (bit 10): bit-reversed for 01, or with RTYPE_OUT
# half-word (01) or byte (10) reversal by word (RM0486 26.3.3 examples). CRC_CR.RESET (bit 0) loads
# CRC_INIT (0x010) into the CRC and reads 0; a write to CRC_INIT also loads it. CRC_IDR (0x004) is storage, untouched by
# RESET. Reset values: CRC_DR and CRC_INIT 0xFFFFFFFF, CRC_POL 0x04C11DB7, CRC_CR and CRC_IDR 0. 8/16-bit data writes
# and DMA are out of the work orders' scope and not modelled.
SCENARIO = "default"


def _rev(v, bits):
    r = 0
    for i in range(bits):
        if v & (1 << i):
            r |= 1 << (bits - 1 - i)
    return r


def _swap(v, mode):
    if mode == 1:  # half-word reversal done by word
        return ((v << 16) | (v >> 16)) & 0xFFFFFFFF
    if mode == 2:  # byte reversal done by word
        return int.from_bytes(v.to_bytes(4, "little"), "big")
    return v


def _rev_in(v, mode, rtype):
    if rtype:
        return _swap(v, mode)
    if mode == 1:
        return sum(_rev((v >> s) & 0xFF, 8) << s for s in (0, 8, 16, 24))
    if mode == 2:
        return sum(_rev((v >> s) & 0xFFFF, 16) << s for s in (0, 16))
    if mode == 3:
        return _rev(v, 32)
    return v


def _width(cr):
    return {0: 32, 1: 16, 2: 8, 3: 7}[(cr >> 3) & 0x3]


if request.IsInit:
    regs = {0x004: 0, 0x008: 0, 0x010: 0xFFFFFFFF, 0x014: 0x04C11DB7}
    crc = 0xFFFFFFFF
elif request.IsRead:
    off = request.Offset
    if off == 0x000:
        mode, rtype = (regs[0x008] >> 7) & 0x3, (regs[0x008] >> 10) & 0x1
        request.Value = _swap(crc, mode) if rtype else (_rev(crc, 32) if mode == 1 else crc)
    elif off == 0x008:
        request.Value = regs[0x008] & 0x7FE
    else:
        request.Value = regs.get(off, 0)
elif request.IsWrite:
    off = request.Offset
    v = request.Value & 0xFFFFFFFF
    if off == 0x000:
        n = _width(regs[0x008])
        mask = (1 << n) - 1
        data = _rev_in(v, (regs[0x008] >> 5) & 0x3, (regs[0x008] >> 9) & 0x1)
        c = crc & mask
        for i in range(31, -1, -1):
            bit = ((data >> i) & 1) ^ ((c >> (n - 1)) & 1)
            c = (c << 1) & mask
            if bit:
                c ^= regs[0x014] & mask
        crc = c
    elif off == 0x008:
        regs[0x008] = v & 0x7FE
        if v & 0x1:
            crc = regs[0x010]
    elif off == 0x010:
        regs[0x010] = v
        crc = v
    elif off in (0x004, 0x014):
        regs[off] = v
