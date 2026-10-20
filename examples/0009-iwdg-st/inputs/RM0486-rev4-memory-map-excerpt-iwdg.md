# RM0486 Rev 4 — Memory map excerpt (IWDG base address)

> Converted from `rm0486.pdf` (sha256 `83cb7e9c7f784a4c5dbbedec428adf58d2cbac8cd802d11e2cdc4d504cceaa86`), pages 179–179.
> Source: https://www.st.com/resource/en/reference_manual/rm0486-stm32n647657xx-armbased-32bit-mcus-stmicroelectronics.pdf — retrieved via web.archive.org capture 20260815172300.
> Authoritative content © STMicroelectronics; converted verbatim for offline engineering use. Cite as `RM0486 p.N`.

<a id="p-179"></a>
<!-- source: RM0486 p.179 -->

```text
RM0486


                   Table 3. Peripheral register boundary addresses (continued)
                                                                                                 Size
Bus Secure boundary address      Nonsecure boundary address              Description
                                                                                               (Kbytes)

       0x5600C000 - 0x5600FFFF    0x4600C000 - 0x4600FFFF     Reserved                           16
       0x5600B000 - 0x5600BFFF    0x4600B000 - 0x4600BFFF     Reserved                            4
       0x5600A000 - 0x5600AFFF    0x4600A000 - 0x4600AFFF     DTS (16FF version)                  4
       0x56009000 - 0x56009FFF    0x46009000 - 0x46009FFF     BSEC                                4
       0x56008000 - 0x56008FFF    0x46008000 - 0x46008FFF     SYSCFG                              4
       0x56004C00 - 0x56007FFF    0x46004C00 - 0x46007FFF     Reserved(WDG_LS_D2)                13
       0x56004800 - 0x56004BFF    0x46004800 - 0x46004BFF     IWDG (WDG_LS_D1)                    1
       0x56004400 - 0x560047FF    0x46004400 - 0x460047FF     TAMP                                1
       0x56004000 - 0x560043FF    0x46004000 - 0x460043FF     RTC and backup registers            1
       0x56003C00 - 0x56003FFF    0x46003C00 - 0x46003FFF     VREFBUF                             1
       0x56003400 - 0x56003BFF    0x46003400 - 0x46003BFF     Reserved                            2
APB4




       0x56003000 - 0x560033FF    0x46003000 - 0x460033FF     LPTIMER5                            1
       0x56002C00 - 0x56002FFF    0x46002C00 - 0x46002FFF     LPTIMER4                            1
       0x56002800 - 0x56002BFF    0x46002800 - 0x46002BFF     LPTIMER3                            1
       0x56002400 - 0x560027FF    0x46002400 - 0x460027FF     LPTIMER2                            1
       0x56002000 - 0x560023FF    0x46002000 - 0x460023FF     Reserved                            1
       0x56001C00 - 0x56001FFF    0x46001C00 - 0x46001FFF     I2C4                                1
       0x56001800 - 0x56001BFF    0x46001800 - 0x46001BFF     Reserved                            1
       0x56001400 - 0x560017FF    0x46001400 - 0x460017FF     SPI6/I2S                            1
       0x56001000 - 0x560013FF    0x46001000 - 0x460013FF     Reserved                            1
       0x56000C00 - 0x56000FFF    0x46000C00 - 0x46000FFF     LPUART1                             1
       0x56000800 - 0x56000BFF    0x46000800 - 0x46000BFF     HDP                                 1
       0x56000000 - 0x460007FF    0x46000000 - 0x460007FF     Reserved                            2
       0x54002400 - 0x5400FFFF    0x44002400 - 0x4400FFFF     Reserved (for APB peripherals)     55
       0x54002000 - 0x540023FF    0x44002000 - 0x440023FF     DFT APB registers                   1
APB3




       0x54001000 - 0x54001FFF    0x44001000 - 0x44001FFF     DBG_MCU                             4
       0x54000000 - 0x54000FFF    0x44000000 - 0x44000FFF     DAP ROM table                       4
       0x52008000 - 0x5200FFFF    0x42008000 - 0x4200FFFF     Reserved (for APB peripherals)     32
APB2




       0x52006000 - 0x52007FFF    0x42006000 - 0x42007FFF     Reserved                            7
       0x52005C00 - 0x52005FFF    0x42005C00 - 0x42005FFF     SAI2                                1




                                                                                                          181
```

