ENTRY(flyos_hook_patch)

SECTIONS
{
    .hook 0x00009a20 : { KEEP(*(.hook)) }
    .primary 0x001f6000 :
    {
        KEEP(*(.overlay.entry))
        *brain32.o(.text*)
    }
    .secondary 0x001fa400 :
    {
        *(.text*)
        *(.rodata*)
    }
    .forbidden : { *(.data*) *(.bss*) *(COMMON) }
    /DISCARD/ :
    {
        *(.comment*) *(.ARM.attributes*) *(.ARM.exidx*)
        *(.ARM.extab*) *(.eh_frame*)
    }
}

ASSERT(ADDR(.hook) == 0x00009a20, "hook address changed")
ASSERT(SIZEOF(.hook) == 4, "hook must be one Thumb BL")
ASSERT(ADDR(.primary) == 0x001f6000, "primary address changed")
ASSERT(overlay_then_flush == 0x001f6000, "entry must be first Thumb function")
/* 0x001f63ff is exclusively reserved for additive-checksum repair. */
ASSERT(SIZEOF(.primary) <= 0x3ff, "primary exceeds payload bound or consumes checksum byte")
ASSERT(ADDR(.secondary) == 0x001fa400, "secondary address changed")
ASSERT(SIZEOF(.secondary) <= 0x800, "secondary exceeds offline allocation")
ASSERT(ADDR(.primary) + SIZEOF(.primary) <= ADDR(.secondary), "payload overlap")
ASSERT(SIZEOF(.forbidden) == 0, "target cannot use writable static storage")
