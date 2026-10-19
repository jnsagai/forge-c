"""Synthetic RM sections (layout of the baselined RM0486 markdown, content minimal) for EASA tests."""
from forge_factory.assurance import hardware as H

COLS = (" 15      14       13     12      11     10      9       8       7      6       5      4       3       2      1        0")
CR = f"""<!-- source: RM0486 section 14.10.1 starting p.479 -->
#### 14.10.1 RCC control register (RCC_CR)
```text
                Address offset: 0x0
                Reset value: 0x0000 0008
 31      30       29     28      27     26      25      24      23     22     21      20      19     18      17       16
 Res.   Res.     Res.    Res.   Res.   Res.    Res.    Res.   Res.    Res.   Res.    Res.    Res.   Res.    Res.     Res.
{COLS}
                                                                                     HSE     HSI
                                                                                     ON      ON
                                                                                     rw      rw
<!-- source: RM0486 p.480 -->
             Bit 4 HSEON: HSE oscillator enable
             Bit 3 HSION: HSI oscillator enable
```
"""
SR = f"""<!-- source: RM0486 section 14.10.2 starting p.481 -->
#### 14.10.2 RCC status register (RCC_SR)
```text
               Address offset: 0x4
               Reset value: 0x0000 0000
{COLS}
                                                                                     HSE     HSI
                                                                                     RDY     RDY
                                                                                      r       r
<!-- source: RM0486 p.482 -->
               Bit 4 HSERDY: HSE clock ready flag
               Bit 3 HSIRDY: HSI clock ready flag
```
"""
CSR = f"""#### 14.10.128 RCC control set register (RCC_CSR)
```text
               Address offset: 0x800
               Reset value: 0x0000 0000
{COLS}
                                                                                     HSEO    HSION
                                                                                      w       w
               Bit 4 HSEONS: HSE enable
               Bit 3 HSIONS: HSI enable
```
"""
CCR = CSR.replace("set register (RCC_CSR)", "clear register (RCC_CCR)").replace("0x800", "0x1000").replace("ONS:", "ONC:")
HDR = """#define LL_RCC_CR_OFFSET 0x000U
#define LL_RCC_SR_OFFSET 0x004U
#define LL_RCC_CR_HSION_MSK 0x00000008U
#define LL_RCC_CR_HSEON_MSK 0x00000010U
#define LL_RCC_SR_HSIRDY_MSK 0x00000008U
#define LL_RCC_CR_FOO_MSK 0x00000080U
static inline void LL_RCC_HSI_Enable(void)
{
  ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSION_MSK;
}

static inline void LL_RCC_HSE_Enable(void)
{
  ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSEON_MSK;
}
"""




def idx_from(tmp_path):
    d = tmp_path / "sections"
    d.mkdir(parents=True, exist_ok=True)
    for name, t in (("cr.md", CR), ("sr.md", SR), ("csr.md", CSR), ("ccr.md", CCR)):
        (d / name).write_text(t)
    return H.index(d)
