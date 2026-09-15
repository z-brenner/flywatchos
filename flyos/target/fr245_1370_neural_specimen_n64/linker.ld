ENTRY(flyos_hook_patch)
SECTIONS
{
    .hook 0x00009a20 : { KEEP(*(.hook)) }
    .primary 0x001f6000 :
    {
        KEEP(*(.overlay.entry))
        *overlay.o(.text*)
        *brain64.o(.text.fly_brain64_reconstruct)
        *brain64.o(.text.fly_brain64_seed)
        *brain64.o(.text.fly_brain64_update_state)
        *renderer.o(.text.pixel)
        *renderer.o(.text.line)
        *renderer.o(.text.text)
        *renderer.o(.rodata.letters*)
    }
    .secondary 0x001fa400 :
    {
        *brain64.o(.text*)
        *renderer.o(.text*)
        *(.rodata*)
    }
    .forbidden : { *(.data*) *(.bss*) *(COMMON) }
    /DISCARD/ : { *(.comment*) *(.ARM.attributes*) *(.ARM.exidx*) *(.ARM.extab*) *(.eh_frame*) }
}
ASSERT(ADDR(.hook) == 0x00009a20, "hook address changed")
ASSERT(SIZEOF(.hook) == 4, "hook must be one Thumb BL")
ASSERT(ADDR(.primary) == 0x001f6000, "primary address changed")
ASSERT(n64_overlay_then_flush == 0x001f6000, "entry must be first")
ASSERT(SIZEOF(.primary) <= 0x3ff, "primary overflow or repair byte used")
ASSERT(ADDR(.secondary) == 0x001fa400, "secondary address changed")
ASSERT(SIZEOF(.secondary) <= 0x800, "secondary overflow")
ASSERT(ADDR(.primary)+SIZEOF(.primary) <= ADDR(.secondary), "segments overlap")
ASSERT(SIZEOF(.forbidden) == 0, "writable static storage forbidden")
