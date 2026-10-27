# ruff: noqa: F821 - Renode injects `request` into Python peripheral scripts
# Behavioural USART1 model (RM0486 rev 4 chapter 65, feature 015), FIFO disabled, internal loopback (TX -> RX).
# USART_ISR (0x01C, read-only) resets to 0x000000C0 (TXE bit 7, TC bit 6). While USART_CR1.UE (bit 0) is set, writes to
# USART_CR2 (0x004), USART_BRR (0x00C), USART_PRESC (0x02C) and to the USART_CR1 fields RM0486 65.8.2 lets change only
# while disabled (FIFOEN 29, M1 28, DEAT 25:21, DEDT 20:16, OVER8 15, M0 12, WAKE 11, PCE 10, PS 9) are ignored. With
# UE set, ISR.TEACK (bit 21) follows CR1.TE (bit 3) and ISR.REACK (bit 22) follows CR1.RE (bit 2). A value written to
# USART_TDR (0x028) with UE and TE set is transmitted at once (TC set again, TXE stays set) and, with RE set, received
# into USART_RDR (0x024) setting ISR.RXNE (bit 5); a value arriving while RXNE is set is lost and sets ISR.ORE (bit 3).
# A read of USART_RDR clears RXNE. ISR flags clear only through USART_ICR (0x020, write-only, write 1): PECF 0, FECF 1,
# NECF 2, ORECF 3, IDLECF 4, TCCF 6; USART_RQR.RXFRQ (0x018 bit 3) discards the received value (RXNE clears). Other
# registers are storage. FIFO mode, interrupts, DMA, synchronous/smartcard/IrDA/LIN/RS-485 modes, auto baud rate and
# line errors are out of the work orders' scope and not modelled.
SCENARIO = "default"
CR1_LOCKED = 0x30000000 | (0x1F << 21) | (0x1F << 16) | (1 << 15) | 0x1E00  # FIFOEN M1 DEAT DEDT OVER8 M0 WAKE PCE PS
ICR_FLAGS = {0: 0x1, 1: 0x2, 2: 0x4, 3: 0x8, 4: 0x10, 6: 0x40}


def _acks():
    global isr
    cr1 = regs[0x000]
    isr = (isr | 0x200000) if (cr1 & 0x1 and cr1 & 0x8) else (isr & ~0x200000)
    isr = (isr | 0x400000) if (cr1 & 0x1 and cr1 & 0x4) else (isr & ~0x400000)


if request.IsInit:
    regs = {0x000: 0, 0x004: 0, 0x008: 0, 0x00C: 0, 0x010: 0, 0x014: 0, 0x02C: 0}
    isr = 0x000000C0
    rdr = 0
elif request.IsRead:
    off = request.Offset
    if off == 0x01C:
        request.Value = isr
    elif off == 0x024:
        request.Value = rdr
        isr &= ~0x20
    elif off in (0x018, 0x020, 0x028):
        request.Value = 0
    else:
        request.Value = regs.get(off, 0)
elif request.IsWrite:
    off = request.Offset
    v = request.Value & 0xFFFFFFFF
    enabled = regs[0x000] & 0x1
    if off == 0x000:
        regs[0x000] = ((regs[0x000] & CR1_LOCKED) | (v & ~CR1_LOCKED)) if enabled else v
        _acks()
    elif off in (0x004, 0x00C, 0x02C):
        if not enabled:
            regs[off] = v
    elif off == 0x018:
        if v & 0x8:
            isr &= ~0x20
    elif off == 0x020:
        for bit, flag in ICR_FLAGS.items():
            if v & (1 << bit):
                isr &= ~flag
    elif off == 0x028:
        cr1 = regs[0x000]
        if cr1 & 0x1 and cr1 & 0x8:
            isr |= 0x40
            if cr1 & 0x4:
                if isr & 0x20:
                    isr |= 0x8
                else:
                    rdr = v & 0x1FF
                    isr |= 0x20
    elif off not in (0x01C, 0x024):
        regs[off] = v
