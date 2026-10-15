# Behavioural RCC model (RM0486 rev 4): RCC_CR (0x000) oscillator/PLL enable bits are mirrored into RCC_SR (0x004)
# ready flags at the same bit positions (HSI 3, HSE 4, MSI 2, LSE 1, LSI 0, PLL1..4 8..11) unless SCENARIO is
# "never_ready" (timeout path). All other registers (e.g. AHB1ENR 0x250, AHB1RSTR 0x210) are plain storage.
SCENARIO = "default"
READY_MASK = 0x00000F1F
if request.IsInit:
    regs = {}
elif request.IsRead:
    off = request.Offset
    if off == 0x004:
        cr = regs.get(0x000, 0)
        request.Value = 0 if SCENARIO == "never_ready" else (cr & READY_MASK)
    else:
        request.Value = regs.get(off, 0)
elif request.IsWrite:
    regs[request.Offset] = request.Value & 0xFFFFFFFF
