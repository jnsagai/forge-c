# ruff: noqa: F821 - Renode injects `request` into Python peripheral scripts
# Behavioural RCC model (RM0486 rev 4): RCC_CR (0x000) oscillator/PLL enable bits are mirrored into RCC_SR (0x004)
# ready flags at the same bit positions (HSI 3, HSE 4, MSI 2, LSE 1, LSI 0, PLL1..4 8..11) unless SCENARIO is
# "never_ready" (timeout path). All other registers (e.g. AHB1ENR 0x250, AHB1RSTR 0x210) are plain storage.
# Feature 008 (ST pilot, CMSIS code): the full 8 KB RCC window (RM0486 memory map 0x56028000-0x56029FFF) and the RM's
# set/clear registers: writing 1s to a set register (e.g. RCC_CSR 0x800, RCC_AHB1ENSR 0xA50) sets those bits in its
# target register (RCC_CR, RCC_AHB1ENR), a clear register (RCC_CCR 0x1000, RCC_AHB1ENCR 0x1250) clears them. CAPA-065
# (rc1 0008a): the RM0486 fields of the set/clear registers are write-only ('w', e.g. RCC_CSR p.647), so a read of a
# set/clear register returns 0 (it used to return the target register, which made full-register snapshots change).
# The table is generated from the RM0486 section files (test_brownfield_st_host checks it).
SCENARIO = "default"
READY_MASK = 0x00000F1F
SET_ALIAS = {  # write-1-to-set register offset -> target register offset (RM0486 rev 4, generated)
    0x800: 0x000,  # RCC_CSR -> RCC_CR
    0xA0C: 0x20C,  # RCC_MEMRSTSR -> RCC_MEMRSTR
    0xA10: 0x210,  # RCC_AHB1RSTSR -> RCC_AHB1RSTR
    0xA14: 0x214,  # RCC_AHB2RSTSR -> RCC_AHB2RSTR
    0xA18: 0x218,  # RCC_AHB3RSTSR -> RCC_AHB3RSTR
    0xA1C: 0x21C,  # RCC_AHB4RSTSR -> RCC_AHB4RSTR
    0xA20: 0x220,  # RCC_AHB5RSTSR -> RCC_AHB5RSTR
    0xA24: 0x224,  # RCC_APB1LRSTSR -> RCC_APB1LRSTR
    0xA28: 0x228,  # RCC_APB1HRSTSR -> RCC_APB1HRSTR
    0xA2C: 0x22C,  # RCC_APB2RSTSR -> RCC_APB2RSTR
    0xA34: 0x234,  # RCC_APB4LRSTSR -> RCC_APB4LRSTR
    0xA38: 0x238,  # RCC_APB4HRSTSR -> RCC_APB4HRSTR
    0xA3C: 0x23C,  # RCC_APB5RSTSR -> RCC_APB5RSTR
    0xA40: 0x240,  # RCC_DIVENSR -> RCC_DIVENR
    0xA44: 0x244,  # RCC_BUSENSR -> RCC_BUSENR
    0xA4C: 0x24C,  # RCC_MEMENSR -> RCC_MEMENR
    0xA50: 0x250,  # RCC_AHB1ENSR -> RCC_AHB1ENR
    0xA54: 0x254,  # RCC_AHB2ENSR -> RCC_AHB2ENR
    0xA58: 0x258,  # RCC_AHB3ENSR -> RCC_AHB3ENR
    0xA5C: 0x25C,  # RCC_AHB4ENSR -> RCC_AHB4ENR
    0xA60: 0x260,  # RCC_AHB5ENSR -> RCC_AHB5ENR
    0xA64: 0x264,  # RCC_APB1LENSR -> RCC_APB1LENR
    0xA68: 0x268,  # RCC_APB1HENSR -> RCC_APB1HENR
    0xA6C: 0x26C,  # RCC_APB2ENSR -> RCC_APB2ENR
    0xA70: 0x270,  # RCC_APB3ENSR -> RCC_APB3ENR
    0xA74: 0x274,  # RCC_APB4LENSR -> RCC_APB4LENR
    0xA78: 0x278,  # RCC_APB4HENSR -> RCC_APB4HENR
    0xA7C: 0x27C,  # RCC_APB5ENSR -> RCC_APB5ENR
    0xA84: 0x284,  # RCC_BUSLPENSR -> RCC_BUSLPENR
    0xA90: 0x290,  # RCC_AHB1LPENSR -> RCC_AHB1LPENR
    0xA94: 0x294,  # RCC_AHB2LPENSR -> RCC_AHB2LPENR
    0xA98: 0x298,  # RCC_AHB3LPENSR -> RCC_AHB3LPENR
    0xA9C: 0x29C,  # RCC_AHB4LPENSR -> RCC_AHB4LPENR
    0xAA0: 0x2A0,  # RCC_AHB5LPENSR -> RCC_AHB5LPENR
    0xAA4: 0x2A4,  # RCC_APB1LLPENSR -> RCC_APB1LLPENR
    0xAA8: 0x2A8,  # RCC_APB1HLPENSR -> RCC_APB1HLPENR
    0xAAC: 0x2AC,  # RCC_APB2LPENSR -> RCC_APB2LPENR
    0xAB0: 0x2B0,  # RCC_APB3LPENSR -> RCC_APB3LPENR
    0xAB4: 0x2B4,  # RCC_APB4LLPENSR -> RCC_APB4LLPENR
    0xAB8: 0x2B8,  # RCC_APB4HLPENSR -> RCC_APB4HLPENR
    0xABC: 0x2BC,  # RCC_APB5LPENSR -> RCC_APB5LPENR
}
CLEAR_ALIAS = {  # write-1-to-clear register offset -> target register offset
    0x1000: 0x000,  # RCC_CCR -> RCC_CR
    0x120C: 0x20C,  # RCC_MEMRSTCR -> RCC_MEMRSTR
    0x1210: 0x210,  # RCC_AHB1RSTCR -> RCC_AHB1RSTR
    0x1214: 0x214,  # RCC_AHB2RSTCR -> RCC_AHB2RSTR
    0x1218: 0x218,  # RCC_AHB3RSTCR -> RCC_AHB3RSTR
    0x121C: 0x21C,  # RCC_AHB4RSTCR -> RCC_AHB4RSTR
    0x1220: 0x220,  # RCC_AHB5RSTCR -> RCC_AHB5RSTR
    0x1224: 0x224,  # RCC_APB1LRSTCR -> RCC_APB1LRSTR
    0x1228: 0x228,  # RCC_APB1HRSTCR -> RCC_APB1HRSTR
    0x122C: 0x22C,  # RCC_APB2RSTCR -> RCC_APB2RSTR
    0x1234: 0x234,  # RCC_APB4LRSTCR -> RCC_APB4LRSTR
    0x1238: 0x238,  # RCC_APB4HRSTCR -> RCC_APB4HRSTR
    0x123C: 0x23C,  # RCC_APB5RSTCR -> RCC_APB5RSTR
    0x1240: 0x240,  # RCC_DIVENCR -> RCC_DIVENR
    0x1244: 0x244,  # RCC_BUSENCR -> RCC_BUSENR
    0x124C: 0x24C,  # RCC_MEMENCR -> RCC_MEMENR
    0x1250: 0x250,  # RCC_AHB1ENCR -> RCC_AHB1ENR
    0x1254: 0x254,  # RCC_AHB2ENCR -> RCC_AHB2ENR
    0x1258: 0x258,  # RCC_AHB3ENCR -> RCC_AHB3ENR
    0x125C: 0x25C,  # RCC_AHB4ENCR -> RCC_AHB4ENR
    0x1260: 0x260,  # RCC_AHB5ENCR -> RCC_AHB5ENR
    0x1264: 0x264,  # RCC_APB1LENCR -> RCC_APB1LENR
    0x1268: 0x268,  # RCC_APB1HENCR -> RCC_APB1HENR
    0x126C: 0x26C,  # RCC_APB2ENCR -> RCC_APB2ENR
    0x1270: 0x270,  # RCC_APB3ENCR -> RCC_APB3ENR
    0x1274: 0x274,  # RCC_APB4LENCR -> RCC_APB4LENR
    0x1278: 0x278,  # RCC_APB4HENCR -> RCC_APB4HENR
    0x127C: 0x27C,  # RCC_APB5ENCR -> RCC_APB5ENR
    0x1284: 0x284,  # RCC_BUSLPENCR -> RCC_BUSLPENR
    0x1290: 0x290,  # RCC_AHB1LPENCR -> RCC_AHB1LPENR
    0x1294: 0x294,  # RCC_AHB2LPENCR -> RCC_AHB2LPENR
    0x1298: 0x298,  # RCC_AHB3LPENCR -> RCC_AHB3LPENR
    0x129C: 0x29C,  # RCC_AHB4LPENCR -> RCC_AHB4LPENR
    0x12A0: 0x2A0,  # RCC_AHB5LPENCR -> RCC_AHB5LPENR
    0x12A4: 0x2A4,  # RCC_APB1LLPENCR -> RCC_APB1LLPENR
    0x12A8: 0x2A8,  # RCC_APB1HLPENCR -> RCC_APB1HLPENR
    0x12AC: 0x2AC,  # RCC_APB2LPENCR -> RCC_APB2LPENR
    0x12B0: 0x2B0,  # RCC_APB3LPENCR -> RCC_APB3LPENR
    0x12B4: 0x2B4,  # RCC_APB4LLPENCR -> RCC_APB4LLPENR
    0x12B8: 0x2B8,  # RCC_APB4HLPENCR -> RCC_APB4HLPENR
    0x12BC: 0x2BC,  # RCC_APB5LPENCR -> RCC_APB5LPENR
}

if request.IsInit:
    regs = {}
elif request.IsRead:
    off = request.Offset
    if off in SET_ALIAS or off in CLEAR_ALIAS:  # CAPA-065: write-only set/clear registers read as 0
        request.Value = 0
    elif off == 0x004:
        cr = regs.get(0x000, 0)
        request.Value = 0 if SCENARIO == "never_ready" else (cr & READY_MASK)
    else:
        request.Value = regs.get(off, 0)
elif request.IsWrite:
    off, val = request.Offset, request.Value & 0xFFFFFFFF
    if off in SET_ALIAS:
        regs[SET_ALIAS[off]] = regs.get(SET_ALIAS[off], 0) | val
    elif off in CLEAR_ALIAS:
        regs[CLEAR_ALIAS[off]] = regs.get(CLEAR_ALIAS[off], 0) & ~val & 0xFFFFFFFF
    else:
        regs[off] = val
