# RM0486 Rev 4 — Chapter 59 Independent watchdog (IWDG)

> Converted from `rm0486.pdf` (sha256 `83cb7e9c7f784a4c5dbbedec428adf58d2cbac8cd802d11e2cdc4d504cceaa86`), pages 2979–2994.
> Source: https://www.st.com/resource/en/reference_manual/rm0486-stm32n647657xx-armbased-32bit-mcus-stmicroelectronics.pdf — retrieved via web.archive.org capture 20260815172300.
> Authoritative content © STMicroelectronics; converted verbatim for offline engineering use. Cite as `RM0486 p.N`.

<a id="p-2979"></a>
<!-- source: RM0486 p.2979 -->

```text
RM0486                                                                    Independent watchdog (IWDG)


```

## 59 Independent watchdog (IWDG)

### 59.1 IWDG introduction

```text
         The independent watchdog (IWDG) peripheral offers a high safety level, thanks to its
         capability to detect malfunctions due to software or hardware failures.
         The IWDG is clocked by an independent clock, and stays active even if the main clock fails.
         In addition, the watchdog function is performed in the VDD voltage domain, allowing the
         IWDG to remain functional even in low power modes. Refer to Section 59.3 to check the
         capability of the IWDG in this product.
         The IWDG is best suited for applications that require the watchdog to run as a totally
         independent process outside the main application, making it very reliable to detect any
         unexpected behavior.


```

### 59.2 IWDG main features

```text
         •     12-bit down-counter
         •     Dual voltage domain, thus enabling operation in low power modes
         •     Independent clock
         •     Early wake-up interrupt generation
         •     Reset generation
               –     In case of timeout
               –     In case of refresh outside the expected window


```

### 59.3 IWDG implementation

```text
                                                Table 572. IWDG features (1)
                                         IWDG modes/features                              IWDG
         LSI used as IWDG kernel clock (iwdg_ker_ck)                                        X
         Window function                                                                    X
         Early wake-up interrupt generation                                                 X
         System reset generation(2)                                                         X
         Capability to work in system Stop                                                  X
         Capability to work in system Standby                                               X
         Capability to generate an interrupt in system Stop                                 X
         Capability to generate an interrupt in system Standby                              -
         Capability to be frozen when the microcontroller enters in Debug mode(3)           X
         Option bytes to control the activity in Stop mode(4)                               X
         Option bytes to control the activity in Standby mode(5)                            X
         Option bytes to control the Hardware mode(6)                                       X
         1. ‘X’ = supported, ‘-’ = not supported.
         2. Refer to the RCC section for additional information.
         3. Controlled via DBG_IWDG_STOP in DBG section.



                                                                                                         2994
```

<a id="p-2980"></a>
<!-- source: RM0486 p.2980 -->

```text
Independent watchdog (IWDG)                                                                                                RM0486


                 4. Controlled via the option byte IWDG_STOP in FLASH section.
                 5. Controlled via the option byte IWDG_STDBY in FLASH section.
                 6. Controlled via the option byte IWDG_SW in FLASH section.



```

### 59.4 IWDG functional description

#### 59.4.1 IWDG block diagram

```text
                 Figure 772 shows the functional blocks of the independent watchdog module.

                               Figure 772. Independent watchdog block diagram

                    IWDG
                         VCORE voltage domain
          APB




                                                                                                  IRQ
                                                Register interface                                               iwdg_it
                                                                                               interface
     iwdg_pclk

                                                                 sync

                                                     Shadow registers and Control                                iwdg_ker_req



                                                        12-bit reload value
                             Prescaler
  iwdg_ker_ck
                                          presc_ck            IWDCNT                                             iwdg_wkup
                                                                                     Comparator logic
   iwdg_in_rst                                                 (12 bits)                                         iwdg_out_rst
                          VDD voltage domain

                                                                                                                       MS49973V4

                 The register and IRQ interfaces are located into the VCORE voltage domain. The watchdog
                 function itself is located into the VDD voltage domain to remain functional in low power
                 modes. See Section 59.3 for IWDG capabilities.
                 The register and IRQ interfaces are mainly clocked by the APB clock (iwdg_pclk), while the
                 watchdog function is clocked by a dedicated kernel clock (iwdg_ker_ck). A synchronization
                 mechanism makes the data exchange between the two domains possible. Note that most of
                 the registers located in the register interface are shadowed into the VDD voltage domain.
                 The IWDG down-counter (IWDCNT) is clocked by the prescaled clock (presc_ck). The
                 prescaled clock is generated from the kernel clock iwdg_ker_ck divided by the prescaler,
                 according to PR[3:0] bitfield.
                 The table below gives the timing delays according to the actions performed on the IWDG:
                 changing the prescaler, the timeout, the window or the early wake-up comparator values or
                 doing a refresh.

                                     Table 573. IWDG delays versus actions (1)
    TDRVU, TDPVU                    TDWVU                     TDEWU                   TDRefresh                 TDRefAuto

   Min            Max         Min         Max           Min                Max      Min        Max         Min             Max

   5 Tk           6 Tk          -           6 Tk          -                6 Tk     2 Tk    2 Tk + Tp       -               Tp



```

<a id="p-2981"></a>
<!-- source: RM0486 p.2981 -->

```text
RM0486                                                                                     Independent watchdog (IWDG)


1. Tk represents a period of the kernel clock input, Tp represents a period of presc_ck.


```

#### 59.4.2 IWDG internal signals

```text
              The list of IWDG internal signals is detailed in Table 574.

                                         Table 574. IWDG internal input/output signals
                         Signal name                    Signal type                            Description

                         iwdg_ker_ck                        Input          IWDG kernel clock
                         iwdg_ker_req                       Input          IWDG kernel clock request
                           iwdg_pclk                        Input          IWDG APB clock
                         iwdg_out_rst                      Output          IWDG reset output
                          iwdg_in_rst                       Input          IWDG reset input
                          iwdg_wkup                        Output          IWDG wake-up event
                            iwdg_it                        Output          IWDG early wake-up interrupt


```

#### 59.4.3 Software and hardware watchdog modes

```text
              The watchdog modes allow the application to select the way the IWDG is enabled, either by
              software commands (Software watchdog mode), or automatically (Hardware watchdog
              mode). All other functions work similarly for both Software and Hardware modes.
              The software watchdog mode is the default working mode. The independent watchdog is
              started by writing the value 0x0000 CCCC into the IWDG key register (IWDG_KR), and the
              IWDCNT starts counting down from the reset value (0xFFF).
              In the hardware watchdog mode the independent watchdog is generally started
              automatically at power-on, or every time it is reset (via iwdg_in_rst). The IWDCNT down-
              counter starts counting down from the reset value 0xFFF. The hardware watchdog mode
              feature is enabled through the device option bits, see Section 59.3 for details.
              When the IWDG is enabled the ONF flag is set to 1.
              When the IWDCNT reaches 0x000, a reset signal is generated (iwdg_out_rst asserted).
              Whenever the key value 0x0000 AAAA is written in the IWDG key register (IWDG_KR), the
              IWDG_RLR value is reloaded into the IWDCNT, and the watchdog reset is prevented.
              Due to re-synchronization delays, the IWDG must be refreshed before the IWDCNT
              down-counter reaches 1.
              Once started, the IWDG can be stopped only when it is reset (iwdg_in_rst asserted).
              As shown in Figure 773, when the refresh command is executed, one period of presc_ck
              later, the IWDCNT is reloaded with the content of RL[11:0].




                                                                                                                          2994
```

<a id="p-2982"></a>
<!-- source: RM0486 p.2982 -->

```text
Independent watchdog (IWDG)                                                                          RM0486


                                             Figure 773. Reset timing due to timeout
                    IWDCNT value
                                          Refresh not allowed(1)       Refresh allowed

                     0xFFF

                   RL[11:0]
                                                                   WIN[11:0]+1
                                                                                         Tpresc_ck
                 WIN[11:0]




                                                                                                       Time
                                                                                 Tpresc_ck
                                                                            2
                              Tpresc_ck
                                                                            1
                                                                            0

             Writing 0xAAAA
              into IWDG_KR

                iwdg_out_rst
                  iwdg_in_rst

                                                                                                     MS49974V2

            1. If window option activated.
            If the IWDG is not refreshed before the IWDCNT reaches 1, the IWDG generates a reset
            (iwdg_out_rst is asserted). In return, the RCC resets the IWDG (assertion of iwdg_in_rst) to
            clear the reset source.
Note:       The iwdg_out_rst signal typically triggers a system reset, however, this behavior may vary
            across products. For more details, refer to Chapter 59.3.

```

#### 59.4.4 Window option

```text
            The IWDG can also work as a window watchdog, by setting the appropriate window in the
            IWDG window register (IWDG_WINR).
            If the reload operation is performed while the counter is greater than WIN[11:0] + 1, a reset
            is generated. WIN[11:0] is located in the IWDG window register (IWDG_WINR). As shown in
            Figure 774, the reset is generated one period of presc_ck after the unexpected refresh
            command.
            The default value of the IWDG window register (IWDG_WINR) is 0x0000 0FFF, so, if not
            updated, the window option is disabled.
            As soon as the window value changes, the down-counter (IWDCNT) is reloaded with the
            RL[11:0] value, to ease the estimation for where the next refresh must take place.




```

<a id="p-2983"></a>
<!-- source: RM0486 p.2983 -->

```text
RM0486                                                               Independent watchdog (IWDG)


                     Figure 774. Reset timing due to refresh in the not allowed area

                    IWDCNT value
                                                    Refresh not allowed
                      0xFFF

                    RL[11:0]


               WIN[11:0] + 1


                                                                                      Time
                         Tpresc_ck                       Tpresc_ck
              Writing 0xAAAA
               into IWDG_KR

                iwdg_out_rst
                  iwdg_in_rst

                                                                                             MS49975V3



         Configuring the IWDG when the window option is enabled
         1.   Enable the IWDG by writing 0x0000 CCCC in the IWDG key register (IWDG_KR).
         2.   Enable register access by writing 0x0000 5555 in the IWDG key register (IWDG_KR).
         3.   Write the IWDG prescaler by programming IWDG prescaler register (IWDG_PR).
         4.   Write the IWDG reload register (IWDG_RLR).
         5.   If needed, enable the early wake-up interrupt, and program the early wake-up
              comparator, by writing the proper values into the IWDG early wake-up interrupt register
              (IWDG_EWCR).
         6.   Write to the IWDG window register (IWDG_WINR). This automatically reloads the
              IWDCNT down-counter with the RL[11:0] value.
         7.   Wait for the registers to be updated (IWDG_SR = 0x0000 0000).
         8.   Write 0x0000 0000 into IWDG key register (IWDG_KR) to write-protect registers.
Note:    Step 7 can be skipped if the application does not intend to disable the APB clock after the
         completion of this sequence.




                                                                                                         2994
```

<a id="p-2984"></a>
<!-- source: RM0486 p.2984 -->

```text
Independent watchdog (IWDG)                                                                                                       RM0486


               Configuring the IWDG when the window option is disabled
               When the window option it is not used, the IWDG can be configured as follows:
               1.   Enable the IWDG by writing 0x0000 CCCC in the IWDG key register (IWDG_KR).
               2.   Enable register access by writing 0x0000 5555 in the IWDG key register (IWDG_KR).
               3.   Write the prescaler by programming the IWDG prescaler register (IWDG_PR).
               4.   Write the IWDG reload register (IWDG_RLR).
               5.   If needed, enable the early wake-up interrupt, and program the early wake-up
                    comparator, by writing the proper values into the IWDG early wake-up interrupt register
                    (IWDG_EWCR).
               6.   Wait for the registers to be updated (IWDG_SR = 0x0000 0000).
               7.   Refresh the counter with RL[11:0] value, and write-protect registers by writing
                    0x0000 AAAA into IWDG key register (IWDG_KR).
               The figure below shows a sequence example changing the prescaler, the reload value, and
               then performing a refresh.

                           Figure 775. Changing PR, RL, and performing a refresh(1)

    iwdg_ker_ck
                               TDPVU                                 TDRVU                               TDRefresh

        WDGCNT
                       N         ...       N-k     N-k-1    ...            N-k-t         N-k-t-1   ...             ...        M       ...
         counter
                       ÷4       ÷4         ÷4      ÷8       ...
                                                                                                     Refresh ignored region


            PVU

            RVU

        Prescaler           ÷4                                                             ÷8

         RL[11:0]                                  P                                                        M

    CPU activity

                            Write 1 into IWDG_PR                  Write into M into RL[11:0]       Write 0xAAAA into IWDG_KR
                                                                                                   Refresh + Registers lock
                        Write 0x5555 into IWDG_KR
                        Registers unlock


                                                                                                                                  MSv75426V1

               1. Refer to Table 573: IWDG delays versus actions for details on timing values.
Note:          When the new prescaler value is accepted by the IWDG (falling edge of PVU), the new
               division ratio is effective when the current division sequence is completed (N-k in the
               drawing).
Note:          The timeout delay between the refresh (write 0xAAAA into IWDG_KR) and the watchdog
               reset is increased by TDRefresh.
               If a refresh command is sent while the previous refresh command is not yet completed, this
               last refresh command is ignored.




```

<a id="p-2985"></a>
<!-- source: RM0486 p.2985 -->

```text
RM0486                                                                                          Independent watchdog (IWDG)


         Updating the window comparator
         It is possible to update the window comparator when the IWDG is already running. The
         IWDCNT is reloaded as well. The following sequence can be performed to update the
         window comparator:
         1.     Enable register access by writing 0x0000 5555 in the IWDG key register (IWDG_KR).
         2.     Write to the IWDG window register (IWDG_WINR). This automatically reloads the
                IWDCNT down-counter with RL[11:0] value.
         3.     Wait for WVU = 0
         4.     Lock registers by writing IWDG_KR to 0x0000 0000
         Step 3 can be skipped if the application does not intend to disable the APB clock after the
         completion of this sequence.
         Figure 776 shows this sequence. As soon as the IWDG_WINR register is written, the WVU
         flag goes high for TDwvu. After a window comparator update, a refresh is automatically
         performed. The refresh is effective in the worst case, on the next prescaler clock active
         edge after the falling edge of WVU (TDRefAuto)

                             Figure 776. Window comparator update(1)

          iwdg_ker_ck

                                                 TDWVU               TDRefAuto
           WDGCNT
                                N                 ...       N-k             M             M-1         M-2    ...
            counter
                                                                             Refresh ignored region


                 WVU
           WIN[11:0]                    500                                               800

              RL[11:0]                                                      M

         CPU activity
                                 Write 800 into IWDG_WINR         Write 0x0000 into IWDG_KR
                                                                  Registers lock
                              Write 0x5555 into IWDG_KR
                              Registers unlock

                                                                                                                   MSv75427V1

         1. Refer to Table 573: IWDG delays versus actions for details on timing values.


```

#### 59.4.5 Debug

```text
         When the processor enters into Debug mode (core halted), the IWDCNT down-counter
         either continues to work normally or stops, depending on debug capability of the product.
         Refer to Section 59.3 for details on the capabilities of this product.

```

#### 59.4.6 Register access protection

```text
         Write accesses to IWDG prescaler register (IWDG_PR), IWDG reload register
         (IWDG_RLR), IWDG early wake-up interrupt register (IWDG_EWCR) and IWDG window
         register (IWDG_WINR) are protected. To modify them, first write 0x0000 5555 in the IWDG
         key register (IWDG_KR). A write access to this register with a different value breaks the



                                                                                                                                2994
```

<a id="p-2986"></a>
<!-- source: RM0486 p.2986 -->

```text
Independent watchdog (IWDG)                                                                            RM0486


            sequence and register access is protected again. This is the case of the reload operation
            (writing 0x0000 AAAA).
            A status register is available to indicate that an update of the prescaler or the down-counter
            reload value or the window value is ongoing.


```

### 59.5 IWDG low power modes

```text
            Depending on option bytes configuration, the IWDG can continue counting or not during the
            low power modes. Refer to Section 59.3 for details.

                                Table 575. Effect of low power modes on IWDG
                    Mode                                         Description

            Sleep                 No effect. IWDG interrupts cause the device to exit from the mode.
                                  The IWDG remains active or not, depending on option bytes configuration.
            Stop                  Refer to Section 59.3 for details.
                                  IWDG interrupts cause the device to exit the Stop mode.
                                  The IWDG remains active or not, depending on option bytes configuration.
            Standby               Refer to Section 59.3 for details.
                                  IWDG interrupts do not make the device to exit from Standby mode.
            Shutdown              The IWDG is not working.



```

### 59.6 IWDG interrupts

```text
            The IWDG offers the possibility to generate an early interrupt depending on the value of the
            down-counter. The early interrupt is enabled by setting the EWIE bit of the IWDG early
            wake-up interrupt register (IWDG_EWCR) to 1.
            A comparator value (EWIT[11:0]) allows the application to define the position where the
            early interrupt must be generated.
            When the IWDCNT down-counter reaches the value of EWIT[11:0] - 1, the iwdg_wkup is
            activated, making it possible for the system to exit from low power modes, if needed.
            When the APB clock is available, the iwdg_it is activated as well.
            In addition, the flag EWIF of the IWDG status register (IWDG_SR) is set to 1.
            The EWI interrupt is acknowledged by writing 1 to the EWIC bit in the IWDG interrupt clear
            register (IWDG_ICR).
            Writing into the IWDG_EWCR register also triggers a refresh of the down-counter
            (IWDCNT) with the reload value RL[11:0].




```

<a id="p-2987"></a>
<!-- source: RM0486 p.2987 -->

```text
RM0486                                                                 Independent watchdog (IWDG)


                    Figure 777. Independent watchdog interrupt timing diagram

                IWDCNT value

                                                              IWDCNT = EWIT - 1

          EWIT[11:0]




                                                                              Writing           Time
                                                                             EWIC to ‘1’
 APB write accesses

      iwdg_wkup_it

                  pclk                                                         pclk active


               iwdg_it
                                                                                                MS49976V1


          The early wake-up interrupt (EWI) can be used if specific safety operations or data logging
          must be performed before the watchdog reset is generated.

          Changing the early wake-up comparator value
          It is possible to change the early wake-up comparator value or to enable/disable the
          interrupt generation at any time, by performing the following sequence:
          1.     Enable register access by writing 0x0000 5555 in the IWDG key register (IWDG_KR).
          2.     Enable or disable the early wake-up interrupt, and/or program the early wake-up
                 comparator, by writing the proper values into the IWDG early wake-up interrupt register
                 (IWDG_EWCR).
          3.     Wait for EWU = 0, EWU is located into the IWDG status register (IWDG_SR).
          4.     Write-protect registers by writing 0x0000 0000 to IWDG key register (IWDG_KR).
          Step 3 can be skipped if the application does not intend to disable the APB clock after the
          completion of this sequence.
          Figure 778 shows this sequence. During the early wake-up comparator update operation
          the flag EWU remains to 1 for TDewu. A refresh is automatically performed. The refresh is
          effective on the worst case, on the next prescaler clock active edge after the falling edge of
          EWU (TDRefAuto).




                                                                                                            2994
```

<a id="p-2988"></a>
<!-- source: RM0486 p.2988 -->

```text
Independent watchdog (IWDG)                                                                                                    RM0486


                                      Figure 778. Early wake-up comparator update(1)

                       iwdg_ker_ck

                                                              TDEWU                TDRefAuto

               WDGCNT counter                 N                ...         N-k         M                M-1         M-2        ...

                                                                                        Refresh ignored region


                              EWU

                        EWIT[11:0]                      500                                              300

                          RL[11:0]                                                     M

                       CPU activity

                                               Write 300 into EWIT[11:0]               Write 0x0000 into IWDG_KR
                                                                                       Registers lock
                                           Write 0x5555 into IWDG_KR
                                           Registers unlock


                                                                                                                               MSv75425V1

            1. Refer to Table 573: IWDG delays versus actions for details on timing values.
            Table 576 summarizes the IWDG interrupt request.

                                              Table 576. IWDG interrupt request
                                                                                                                 Activated interrupt
                                                          Interrupt              Interrupt enable
              Interrupt event        Event flag
                                                        clear method                control bit
                                                                                                              iwdg_it     iwdg_wkup_it

             IWDCNT reaches
                                       EWIF          Writing EWIC to 1                 EWIE                      Y(1)         Y(2)
               EWIT value
            1. Generated when a clock is present on iwdg_pclk input.
            2. Generated when a clock is present on iwdg_ker_ck input.



```

### 59.7 IWDG registers

```text
            Refer to Section 1.2 on page 156 for a list of abbreviations used in register descriptions.
            The peripheral registers can be accessed by half-words (16-bit) or words (32-bit).
            Most of the registers located into the register interface are shadowed into the VDD voltage
            domain. When the iwdg_in_rst is asserted, the watchdog logic and the shadow registers
            located into the VDD voltage domain are reset.
            When the application reads back a watchdog register, the hardware transfers the value of
            the corresponding shadow register to the register interface.
            When the application writes a watchdog register, the hardware updates the corresponding
            shadow register.




```

<a id="p-2989"></a>
<!-- source: RM0486 p.2989 -->

```text
RM0486                                                                            Independent watchdog (IWDG)


```

#### 59.7.1 IWDG key register (IWDG_KR)

```text
                Address offset: 0x00
                Reset value: 0x0000 0000

 31      30       29    28     27      26     25       24     23    22     21       20    19     18         17       16
 Res.    Res.    Res.   Res.   Res.    Res.   Res.    Res.   Res.   Res.   Res.    Res.   Res.   Res.      Res.     Res.


 15      14       13    12     11      10      9       8       7     6      5       4      3      2             1    0
                                                       KEY[15:0]
  w       w       w      w      w       w      w       w      w      w      w       w      w      w             w    w



          Bits 31:16 Reserved, must be kept at reset value.
           Bits 15:0 KEY[15:0]: Key value (write only, read 0x0000)
                      These bits can be used for several functions, depending upon the value written by the
                      application:
                      - 0xAAAA: reloads the RL[11:0] value into the IWDCNT down-counter (watchdog refresh),
                      and write-protects registers. This value must be written by software at regular intervals,
                      otherwise the watchdog generates a reset when the counter reaches 0.
                      - 0x5555: enables write-accesses to the registers.
                      - 0xCCCC: enables the watchdog (except if the hardware watchdog option is selected) and
                      write-protects registers.
                      - values different from 0x5555: write-protects registers.
                      Note that only IWDG_PR, IWDG_RLR, IWDG_EWCR and IWDG_WINR registers have a
                      write-protection mechanism.


```

#### 59.7.2 IWDG prescaler register (IWDG_PR)

```text
                Address offset: 0x04
                Reset value: 0x0000 0000

 31      30       29    28     27      26     25       24     23    22     21       20    19     18         17       16
 Res.    Res.    Res.   Res.   Res.    Res.   Res.    Res.   Res.   Res.   Res.    Res.   Res.   Res.      Res.     Res.


 15      14       13    12     11      10      9       8       7     6      5       4      3      2             1    0
 Res.    Res.    Res.   Res.   Res.    Res.   Res.    Res.   Res.   Res.   Res.    Res.               PR[3:0]
                                                                                          rw     rw         rw       rw



           Bits 31:4 Reserved, must be kept at reset value.




                                                                                                                            2994
```

<a id="p-2990"></a>
<!-- source: RM0486 p.2990 -->

```text
Independent watchdog (IWDG)                                                                                         RM0486


                Bits 3:0 PR[3:0]: Prescaler divider
                          These bits are write access protected, see Section 59.4.6. They are written by software to
                          select the prescaler divider feeding the counter clock. PVU bit of the IWDG status register
                          (IWDG_SR) must be reset to be able to change the prescaler divider.
                          0000: divider / 4
                          0001: divider / 8
                          0010: divider / 16
                          0011: divider / 32
                          0100: divider / 64
                          0101: divider / 128
                          0110: divider / 256
                          0111: divider / 512
                          Others: divider / 1024
                         Note: Reading this register returns the prescaler value from the VDD voltage domain. This
                               value may not be up to date/valid if a write operation to this register is ongoing. For this
                               reason the value read from this register is valid only when the PVU bit in the IWDG
                               status register (IWDG_SR) is reset.


```

#### 59.7.3 IWDG reload register (IWDG_RLR)

```text
                 Address offset: 0x08
                 Reset value: 0x0000 0FFF

  31     30         29      28     27      26     25      24     23      22      21     20      19     18      17      16
 Res.    Res.      Res.    Res.   Res.    Res.   Res.    Res.    Res.   Res.    Res.   Res.    Res.   Res.    Res.    Res.


  15     14         13      12     11      10      9      8       7       6      5       4      3       2      1       0
 Res.    Res.      Res.    Res.                                           RL[11:0]
                                   rw      rw     rw      rw      rw     rw      rw     rw      rw     rw      rw      rw



          Bits 31:12 Reserved, must be kept at reset value.
            Bits 11:0 RL[11:0]: Watchdog counter reload value
                       These bits are write access protected, see Section 59.4.6. They are written by software to
                       define the value to be loaded in the watchdog counter each time the value 0xAAAA is written
                       in the IWDG key register (IWDG_KR). The watchdog counter counts down from this value.
                       The timeout period is a function of this value and the prescaler.clock. It is not recommended
                       to set RL[11:0] to a value lower than 2.
                       The RVU bit in the IWDG status register (IWDG_SR) must be reset to be able to change the
                       reload value.
                      Note: Reading this register returns the reload value from the VDD voltage domain. This value
                             may not be up to date/valid if a write operation to this register is ongoing, hence the
                             value read from this register is valid only when the RVU bit in the IWDG status register
                             (IWDG_SR) is reset.

```

#### 59.7.4 IWDG status register (IWDG_SR)

```text
                 Address offset: 0x0C
                 Reset value: 0x0000 0000 (0xFFFF FEFF)
                 This register contains various status flags. Note that the mask value between parenthesis
                 means that the reset value of ONF bit is not defined. When the IWDG is configured in



```

<a id="p-2991"></a>
<!-- source: RM0486 p.2991 -->

```text
RM0486                                                                                 Independent watchdog (IWDG)


                software mode, the reset value of ONF bit is 0, when the IWDG is configured in hardware
                mode, the reset value of ONF bit is 1.

  31     30        29     28      27      26     25       24     23      22     21       20     19      18     17      16
 Res.   Res.      Res.   Res.    Res.    Res.    Res.    Res.   Res.    Res.    Res.    Res.   Res.    Res.    Res.   Res.


  15     14        13     12      11      10      9       8      7       6       5       4      3       2       1       0
 EWIF   Res.      Res.   Res.    Res.    Res.    Res.    ONF    Res.    Res.    Res.    Res.   EWU     WVU     RVU    PVU
  r                                                       r                                      r      r       r       r



         Bits 31:16 Reserved, must be kept at reset value.
                Bit 15 EWIF: Watchdog early interrupt flag
                        This bit is set to ‘1’ by hardware in order to indicate that an early interrupt is pending. This bit
                        must be cleared by the software by writing the bit EWIC of IWDG_ICR register to ‘1’.
          Bits 14:9 Reserved, must be kept at reset value.
                 Bit 8 ONF: Watchdog enable status bit
                       Set to ‘1’ by hardware as soon as the IWDG is started. In software mode, it remains to '1' until
                       the IWDG is reset. In hardware mode, this bit is always set to '1'.
                         0: The IWDG is not activated
                         1: The IWDG is activated and needs to be refreshed regularly by the application
               Bits 7:4 Reserved, must be kept at reset value.
                 Bit 3 EWU: Watchdog interrupt comparator value update
                        This bit is set by hardware to indicate that an update of the interrupt comparator value
                        (EWIT[11:0]) or an update of the EWIE is ongoing. It is reset by hardware when the update
                        operation is completed in the VDD voltage domain. Refer to Table 573: IWDG delays versus
                        actions for delay values.
                        The EWIT[11:0] and EWIE fields can be updated only when EWU bit is reset.
                 Bit 2 WVU: Watchdog counter window value update
                        This bit is set by hardware to indicate that an update of the window value is ongoing. It is
                        reset by hardware when the reload value update operation is completed in the VDD voltage
                        domain. Refer to Table 573: IWDG delays versus actions for delay values.
                        The window value can be updated only when WVU bit is reset.
                        This bit is generated only if generic “window” = 1.
                 Bit 1 RVU: Watchdog counter reload value update
                        This bit is set by hardware to indicate that an update of the reload value is ongoing. It is reset
                        by hardware when the reload value update operation is completed in the VDD voltage
                        domain. Refer to Table 573: IWDG delays versus actions for delay values.
                        The reload value can be updated only when RVU bit is reset.
                 Bit 0 PVU: Watchdog prescaler value update
                        This bit is set by hardware to indicate that an update of the prescaler value is ongoing. It is
                        reset by hardware when the prescaler update operation is completed in the VDD voltage
                        domain. Refer to Table 573: IWDG delays versus actions for delay values.
                        The prescaler value can be updated only when PVU bit is reset.

Note:           If several reload, prescaler, early interrupt position or window values are used by the
                application, it is mandatory to wait until RVU bit is reset before changing the reload value, to
                wait until PVU bit is reset before changing the prescaler value, to wait until WVU bit is reset
                before changing the window value, and to wait until EWU bit is reset before changing the



                                                                                                                               2994
```

<a id="p-2992"></a>
<!-- source: RM0486 p.2992 -->

```text
Independent watchdog (IWDG)                                                                                       RM0486


                early interrupt position value. After updating the prescaler and/or the reload/window/early
                interrupt value, it is not necessary to wait until RVU or PVU or WVU or EWU is reset before
                continuing code execution, except in case of low power mode entry.

```

#### 59.7.5 IWDG window register (IWDG_WINR)

```text
                Address offset: 0x10
                Reset value: 0x0000 0FFF

  31     30       29     28     27      26      25      24     23      22      21     20     19      18      17      16
 Res.    Res.    Res.   Res.    Res.   Res.    Res.    Res.   Res.    Res.    Res.   Res.    Res.   Res.    Res.    Res.


  15     14       13     12     11      10      9       8      7       6       5      4       3       2      1       0
 Res.    Res.    Res.   Res.                                           WIN[11:0]
                                rw      rw      rw      rw     rw      rw      rw     rw     rw      rw      rw      rw



          Bits 31:12 Reserved, must be kept at reset value.
            Bits 11:0 WIN[11:0]: Watchdog counter window value
                      These bits are write access protected, see Section 59.4.6.They contain the high limit of the
                      window value to be compared with the downcounter.
                      To prevent a reset, the IWDCNT downcounter must be reloaded when its value is lower than
                      WIN[11:0] + 1 and greater than 1.
                      The WVU bit in the IWDG status register (IWDG_SR) must be reset to be able to change the
                      reload value.
                      Note: Reading this register returns the reload value from the VDD voltage domain. This value
                             may not be valid if a write operation to this register is ongoing. For this reason the value
                             read from this register is valid only when the WVU bit in the IWDG status register
                             (IWDG_SR) is reset.

```

#### 59.7.6 IWDG early wake-up interrupt register (IWDG_EWCR)

```text
                Address offset: 0x14
                Reset value: 0x0000 0000

  31     30       29     28     27      26      25      24     23      22      21     20     19      18      17      16
 Res.    Res.    Res.   Res.    Res.   Res.    Res.    Res.   Res.    Res.    Res.   Res.    Res.   Res.    Res.    Res.


  15     14       13     12     11      10      9       8      7       6       5      4       3       2      1       0
 EWIE    Res.    Res.   Res.                                           EWIT[11:0]
  rw                            rw      rw      rw      rw     rw      rw      rw     rw     rw      rw      rw      rw



          Bits 31:16 Reserved, must be kept at reset value.
                Bit 15 EWIE: Watchdog early interrupt enable
                       Set and reset by software.
                       0: The early interrupt interface is disabled.
                       1: The early interrupt interface is enabled.
                       The EWU bit in the IWDG status register (IWDG_SR) must be reset to be able to change the
                       value of this bit.




```

<a id="p-2993"></a>
<!-- source: RM0486 p.2993 -->

```text
RM0486                                                                             Independent watchdog (IWDG)


          Bits 14:12 Reserved, must be kept at reset value.
           Bits 11:0 EWIT[11:0]: Watchdog counter early wake-up interrupt value
                     These bits are write access protected (see Section 59.4.6). They are written by software to
                     define at which position of the IWDCNT down-counter the early wake-up interrupt must be
                     generated. The early interrupt is generated when the IWDCNT is lower or equal to
                     EWIT[11:0] - 1.
                     EWIT[11:0] must be bigger than 1.
                     An interrupt is generated only if EWIE = 1.
                     The EWU bit in the IWDG status register (IWDG_SR) must be reset to be able to change the
                     reload value.
                     Note: Reading this register returns the Early wake-up comparator value and the Interrupt
                            enable bit from the VDD voltage domain. This value may not be up to date/valid if a write
                            operation to this register is ongoing, hence the value read from this register is valid only
                            when the EWU bit in the IWDG status register (IWDG_SR) is reset.

```

#### 59.7.7 IWDG interrupt clear register (IWDG_ICR)

```text
                Address offset: 0x18
                Reset value: 0x0000 0000

 31      30       29     28      27     26     25       24    23      22     21      20     19      18      17     16
 Res.    Res.    Res.    Res.   Res.   Res.    Res.    Res.   Res.   Res.   Res.    Res.   Res.    Res.    Res.   Res.


 15      14       13     12      11     10      9       8      7      6       5      4       3       2      1       0
EWIC     Res.    Res.    Res.   Res.   Res.    Res.    Res.   Res.   Res.   Res.    Res.    Res.   Res.    Res.   Res.
 rw



          Bits 31:16 Reserved, must be kept at reset value.
                Bit 15 EWIC: Watchdog early interrupt acknowledge
                       The software must write a 1 into this bit in order to acknowledge the early wake-up interrupt
                       and to clear the EWIF flag. Writing 0 has not effect, reading this flag returns a 0.
           Bits 14:0 Reserved, must be kept at reset value.




                                                                                                                           2994
```

<a id="p-2994"></a>
<!-- source: RM0486 p.2994 -->

```text
                                                                                                              0x18
                                                                                                                                          0x14
                                                                                                                                                                        0x10
                                                                                                                                                                                                                                0x08
                                                                                                                                                                                                                                                            0x04
                                                                                                                                                                                                                                                                                       0x00




                                                                                                                                                                                                     0x0C
                                                                                                                                                                                                                                                                                                      Offset
                                                                                                                                                                                                                                                                                                                                                                      59.7.8




2994/4669
                                                                                                                                                                                                        IWDG_SR
                                                                                                                                                                                                                                                               IWDG_PR
                                                                                                                                                                                                                                                                                          IWDG_KR




                                                                                                                 IWDG_ICR
                                                                                                                                                                                                                                   IWDG_RLR




                                                                                                Reset value
                                                                                                                            Reset value
                                                                                                                                                          Reset value
                                                                                                                                                                                       Reset value
                                                                                                                                                                                                                  Reset value
                                                                                                                                                                                                                                              Reset value
                                                                                                                                                                                                                                                                         Reset value




                                                                                                                                                                           IWDG_WINR



                                                                                                                                             IWDG_EWCR
                                                                                                                                                                                                                                                                                                      Register name

                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           31
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           30
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           29
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           28
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           27
                                                                                                                                                                                                                                                                                                                                                                                          Independent watchdog (IWDG)




                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           26
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.
                                                                                                                                                                                                                                                                                                                                                                      IWDG register map




                                                                                                                                                                                                                                                                                                      25
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           24
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           23
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           22
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           21
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           20
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           19
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           18
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.




                                                                                                                                                                                                                                                                                                      17
                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                       Res.           16


                                                                                                0
                                                                                                                            0
                                                                                                                                                                                       0
                                                                                                                                                                                                                                                                         0




                                                                                                              EWIC                        EWIE                          Res.                         EWIF                       Res.                        Res.                                      15
                                                                                                                                                                                                                                                                         0




                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                                      14
                                                                                                                                                                                                                                                                         0




                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                                      13
                                                                                                                                                                                                                                                                         0




                                                                                                              Res.                        Res.                          Res.                         Res.                       Res.                        Res.                                      12
                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0




                                                                                                              Res.                                                                                   Res.                                                   Res.                                      11
                                                                                                                                                                                                                                                                                                                      Table 577. IWDG register map and reset values




                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0




                                                                                                              Res.                                                                                   Res.                                                   Res.                                      10
                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0




                                                                                                              Res.                                                                                   Res.                                                   Res.                                      9
                                                                                                                                                                                       x




                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0




                                                                                                              Res.                                                                                   ONF                                                    Res.                                      8
                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0




                                                                                                              Res.                                                                                   Res.                                                   Res.                                      7
                                                                                                                                                                                                                                                                                          KEY[15:0]




                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0




                                                                                                              Res.                                                                                   Res.                                                   Res.                                      6
                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0




                                                                                                              Res.                                                                                   Res.                                                   Res.                                      5
                                                                                                                                                                                                                                   RL[11:0]




                                                                                                                                                                           WIN[11:0]




               Refer to Section 2.3: Memory organization for the register boundary addresses.
                                                                                                                                             EWIT[11:0]

                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0




                                                                                                              Res.                                                                                   Res.                                                   Res.                                      4
                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                       0
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0



                                                                                                                                                                                                                                              0




                                                                                                              Res.                                                                                   EWU                                                                                              3
                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0




                                                                                                                                                                                       0
                                                                                                                                                                                                                                              0




                                                                                                              Res.                                                                                   WVU                                                                                              2
                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0




                                                                                                                                                                                       0
                                                                                                                                                                                                                                              0




                                                                                                              Res.                                                                                   RVU                                                                                              1
                                                                                                                                                                                                                                                               PR[3:0]




                                                                                                                            0
                                                                                                                                                          1
                                                                                                                                                                                                                  1
                                                                                                                                                                                                                                                                         0




                                                                                                                                                                                       0
                                                                                                                                                                                                                                              0




                                                                                                              Res.                                                                                   PVU                                                                                              0
                                                                                                                                                                                                                                                                                                                                                                                          RM0486
```

