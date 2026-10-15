/* RAM-resident image for the Forge-C STM32N6 Renode platform. */
ENTRY(forge_reset_handler)
MEMORY { RAM (rwx) : ORIGIN = 0x34000000, LENGTH = 0x1F0000
         MAILBOX (rw) : ORIGIN = 0x341F0000, LENGTH = 0x1000 }
ll_rcc_regs = 0x56028000;  /* RCC register block (RM0486 p.176); the driver declares it extern */
SECTIONS {
  .isr_vector : { KEEP(*(.isr_vector)) } > RAM
  .text : { *(.text*) *(.rodata*) } > RAM
  .data : { *(.data*) } > RAM
  .bss (NOLOAD) : { _sbss = .; *(.bss*) *(COMMON) _ebss = .; } > RAM
  .forge_mailbox (NOLOAD) : { KEEP(*(.forge_mailbox)) } > MAILBOX
  _estack = ORIGIN(RAM) + LENGTH(RAM);
}
