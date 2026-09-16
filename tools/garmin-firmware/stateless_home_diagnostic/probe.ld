ENTRY(probe_display_patch)
SECTIONS
{
  .hook_display 0x00009a20 : { KEEP(*(.hook.display)) }
  .payload 0x001fa400 :
  {
    KEEP(*(.probe.entry))
    *(.text*)
    *(.rodata*)
  }
  .forbidden : { *(.data*) *(.bss*) *(COMMON) }
  /DISCARD/ : { *(.comment*) *(.ARM.attributes*) *(.ARM.exidx*) *(.ARM.extab*) *(.eh_frame*) }
}
ASSERT(SIZEOF(.hook_display) == 4, "display hook must be one BL")
ASSERT(SIZEOF(.payload) <= 0x800, "probe payload exceeds secondary cave")
ASSERT(SIZEOF(.forbidden) == 0, "writable static storage forbidden")
