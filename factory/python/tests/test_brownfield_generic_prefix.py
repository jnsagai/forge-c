"""Feature 015: the brownfield register-effect extraction and conformance follow the work order's peripheral.

WO-BENCH-CRC-ST-r2 passed SWE.1-SWE.6 but its package carried 10 false CONTRADICTION findings ("field CRC_CR.RESET has
no definition in the delivered code"): the field lookup and the CMSIS access patterns were RCC-only, so ST's CRC code
(`MODIFY_REG(CRCx->CR, ...)`, CMSIS `CRC_CR_POLYSIZE_Msk`) was never read. RCC extraction is unchanged."""
from forge_factory.brownfield import conformance as C
from forge_factory.brownfield import scope as S

CMSIS = """
#define CRC_CR_RESET_Pos (0U)
#define CRC_CR_RESET_Msk (0x1UL << CRC_CR_RESET_Pos)
#define CRC_CR_RESET CRC_CR_RESET_Msk
#define CRC_CR_POLYSIZE_Pos (3U)
#define CRC_CR_POLYSIZE_Msk (0x3UL << CRC_CR_POLYSIZE_Pos)
#define CRC_CR_POLYSIZE CRC_CR_POLYSIZE_Msk
#define SPI_TXDR_TXDR_Pos (0U)
#define SPI_TXDR_TXDR_Msk (0xFFFFFFFFUL << SPI_TXDR_TXDR_Pos)
"""
ST = """
__STATIC_INLINE void LL_CRC_ResetCRCCalculationUnit(CRC_TypeDef *CRCx)
{
  SET_BIT(CRCx->CR, CRC_CR_RESET);
}
__STATIC_INLINE void LL_CRC_SetPolynomialSize(CRC_TypeDef *CRCx, uint32_t PolySize)
{
  MODIFY_REG(CRCx->CR, CRC_CR_POLYSIZE, PolySize);
}
__STATIC_INLINE void LL_SPI_TransmitData8(SPI_TypeDef *SPIx, uint8_t TxData)
{
  *((__IO uint8_t *)&SPIx->TXDR) = TxData;
}
__STATIC_INLINE uint8_t LL_SPI_ReceiveData8(SPI_TypeDef *SPIx)
{
  return (*((__IO uint8_t *)&SPIx->RXDR));
}
__STATIC_INLINE void LL_RCC_HSI_Enable(void)
{
  SET_BIT(RCC->CSR, RCC_CSR_HSIONS);
}
"""


def _defs():
    return {d.name: d for d in S.index(ST, "software/ll/x.h")}, S.constant_macros([CMSIS])


def test_crc_fields_resolve_from_the_cmsis_macros_of_the_work_order_peripheral():
    _defs_, macros = _defs()
    assert C._field_mask("CRC_CR", "RESET", macros, "CRC") == 0x1
    assert C._field_mask("CRC_CR", "POLYSIZE", macros, "CRC") == 0x18
    assert C._field_mask("CRC_CR", "RESET", macros) is None  # the old RCC-only lookup could not find it


def test_instance_pointer_accesses_are_extracted_with_bound_or_unbound_arguments():
    defs, macros = _defs()
    got = S.register_effects(defs["LL_CRC_ResetCRCCalculationUnit"], macros, "cmsis", ["CRC"], defs, prefix="CRC")
    assert [(e.register, e.op, e.mask) for e in got] == [("CRC_CR", "set", 0x1)]
    got = S.register_effects(defs["LL_CRC_SetPolynomialSize"], macros, "cmsis", ["(CRC)", "0x00000008U"], defs,
                             prefix="CRC")
    assert [(e.register, e.op, e.mask) for e in got] == [("CRC_CR", "modify", 0x8)]  # MODIFY_REG: the value written
    tx = S.register_effects(defs["LL_SPI_TransmitData8"], macros, "cmsis", ["SPI1", "0xA5U"], defs, prefix="SPI")
    rx = S.register_effects(defs["LL_SPI_ReceiveData8"], macros, "cmsis", ["SPI1"], defs, prefix="SPI")
    assert [(e.register, e.op, e.mask) for e in tx] == [("SPI_TXDR", "write", 0xA5)]
    assert [(e.register, e.op) for e in rx] == [("SPI_RXDR", "read")]


def test_rcc_extraction_is_unchanged():
    defs, macros = _defs()
    got = S.register_effects(defs["LL_RCC_HSI_Enable"], macros, "cmsis", None, defs)
    assert [(e.register, e.op, e.via) for e in got] == [("RCC_CR", "set", "RCC_CSR")]
    assert S.register_effects(defs["LL_CRC_ResetCRCCalculationUnit"], macros, "cmsis", None, defs) == []  # RCC prefix


def test_a_qualifier_after_the_type_cast_and_cmsis_bit_macros_are_not_expanded_twice():
    src = """
__STATIC_INLINE void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData)
{
  *((uint32_t __IO *)(&CRCx->IDR)) = (uint32_t) InData;
}
#define MODIFY_REG(REG, CLEARMASK, SETMASK)  WRITE_REG((REG), (((READ_REG(REG)) & (~(CLEARMASK))) | (SETMASK)))
__STATIC_INLINE void LL_SPI_SetClockPolarity(SPI_TypeDef *SPIx, uint32_t ClockPolarity)
{
  MODIFY_REG(SPIx->CFG2, SPI_CFG2_CPOL, ClockPolarity);
}
"""
    defs = {d.name: d for d in S.index(src, "software/ll/x.h")}
    got = S.register_effects(defs["LL_CRC_Write_IDR"], {}, "cmsis", ["CRC", "0xA5A55A5AU"], defs, prefix="CRC")
    assert [(e.register, e.op, e.mask) for e in got] == [("CRC_IDR", "write", 0xA5A55A5A)]
    got = S.register_effects(defs["LL_SPI_SetClockPolarity"], {}, "cmsis", ["SPI1", "0x02000000U"], defs, prefix="SPI")
    assert [(e.register, e.op, e.mask) for e in got] == [("SPI_CFG2", "modify", 0x02000000)]  # no mask-less write


def test_the_real_crc_r2_package_is_conformant_and_the_ready_rcc_pilots_are_unchanged():
    """WO-BENCH-CRC-ST-r2 (10 false findings at packaging) is CONFORMANT with the generic checker; the READY ST RCC
    pilot keeps its result. Local run state: skipped where it does not exist."""
    import os
    from pathlib import Path

    st = Path(os.environ.get("FORGE_STATE_DIR", "/nonexistent")) / "workorders"
    for wo in ("WO-BENCH-CRC-ST-r2", "WO-0008C-ST-RCC-LL-b009"):
        ws = st / wo / "workspace"
        if not (ws / "workproducts/SWE.2/api_calls.json").is_file():
            continue
        r = C.check(ws, "SWE.3", write=False)
        assert r["status"] == "CONFORMANT", (wo, r["findings"][:3])
