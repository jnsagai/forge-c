ENTRY(sim_reset_handler)
MEMORY { ROM (rx) : ORIGIN = 0x34000000, LENGTH = 0x100000
         RAM (rw) : ORIGIN = 0x34100000, LENGTH = 0xF0000
         RET (rw) : ORIGIN = 0x341F0000, LENGTH = 0x1000 }
SECTIONS {
  .isr_vector : { KEEP(*(.isr_vector)) } > ROM
  .text : { *(.text*) *(.rodata*) . = ALIGN(4); } > ROM
  _sidata = LOADADDR(.data);
  .data : { . = ALIGN(4); _sdata = .; *(.data*) . = ALIGN(4); _edata = .; } > RAM AT > ROM
  .bss (NOLOAD) : { . = ALIGN(4); _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .; } > RAM
  .noinit (NOLOAD) : { *(.noinit*) } > RET
  _estack = ORIGIN(RAM) + LENGTH(RAM);
}
