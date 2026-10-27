# ruff: noqa: F821 - Renode injects `request` into Python peripheral scripts
# Behavioural SPI1 model (RM0486 rev 4 chapter 67, feature 015), loopback master: SPI_CFG1 (0x008) and SPI_CFG2 (0x00C)
# are write-protected while SPI_CR1.SPE (bit 0) is set. Frames written to SPI_TXDR (0x020) wait in the TxFIFO
# (SPI_SR.TXC, bit 12, clears) until a master transfer runs: SPI_CR1.CSTART (bit 9), accepted only with SPE and
# SPI_CFG2.MASTER (bit 22), moves each frame to the RxFIFO (loopback: MISO = MOSI), setting SPI_SR.RXP (bit 0); after
# SPI_CR2.TSIZE frames (0 = endless) SPI_SR.EOT (bit 3) and TXTF (bit 4) are set, CSTART clears and TXC sets again. A
# read of SPI_RXDR (0x030) pops a frame (RXP clears when empty); a frame arriving with a full 16-frame RxFIFO is lost
# and sets SPI_SR.OVR (bit 6). SPI_SR (0x014) is read-only (reset 0x00001002: TXP, TXC); flags clear only by writing 1
# to SPI_IFCR (0x018, write-only): EOTC bit 3, TXTFC bit 4, UDRC bit 5, OVRC bit 6, CRCEC bit 7, TIFREC bit 8, MODFC
# bit 9, SUSPC bit 11. SPI_CRCPOLY (0x040) resets to 0x107; other registers are storage. CRC, TI mode, I2S, interrupts,
# DMA and the half-duplex/simplex directions are out of the work orders' scope and not modelled.
SCENARIO = "default"
DEPTH = 16


def _transfer():
    global tx, rx, done, sr
    tsize = regs[0x004] & 0xFFFF
    while tx and (regs[0x000] & 0x200):
        v = tx.pop(0)
        if len(rx) < DEPTH:
            rx.append(v)
        else:
            sr |= 0x40
        done += 1
        if tsize and done >= tsize:
            sr |= 0x18
            regs[0x000] &= ~0x200
            done = 0
    if not tx:
        sr |= 0x1000
    sr = (sr | 0x1) if rx else (sr & ~0x1)


if request.IsInit:
    regs = {0x000: 0, 0x004: 0, 0x008: 0x00070007, 0x00C: 0, 0x010: 0, 0x040: 0x107, 0x044: 0, 0x048: 0, 0x04C: 0,
            0x050: 0}
    sr = 0x00001002
    tx, rx, done = [], [], 0
elif request.IsRead:
    off = request.Offset
    if off == 0x014:
        request.Value = sr
    elif off == 0x030:
        request.Value = rx.pop(0) if rx else 0
        sr = (sr | 0x1) if rx else (sr & ~0x1)
    elif off in (0x018, 0x020):
        request.Value = 0
    else:
        request.Value = regs.get(off, 0)
elif request.IsWrite:
    off = request.Offset
    v = request.Value & 0xFFFFFFFF
    if off == 0x000:
        start = (v & 0x200) and (v & 0x1) and (regs[0x00C] & 0x400000)
        regs[0x000] = (v & ~0x200) | (0x200 if start or (regs[0x000] & 0x200 and v & 0x1) else 0)
        _transfer()
    elif off in (0x008, 0x00C):
        if not regs[0x000] & 0x1:
            regs[off] = v
    elif off == 0x018:
        sr &= ~(v & 0xBF8)
    elif off == 0x020:
        tx.append(v)
        sr &= ~0x1000
        _transfer()
    elif off != 0x014 and off != 0x030:
        regs[off] = v
