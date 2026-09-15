ENTRY(flyos_hook_patch)

SECTIONS
{
    .hook 0x00009a20 :
    {
        KEEP(*(.hook))
    }

    .overlay 0x001f6000 :
    {
        KEEP(*(.overlay.entry))
        *(.text*)
        *(.rodata*)
    }

    /DISCARD/ :
    {
        *(.comment*)
        *(.ARM.attributes*)
        *(.ARM.exidx*)
        *(.ARM.extab*)
        *(.eh_frame*)
    }
}

ASSERT(SIZEOF(.hook) == 4, "hook must be one Thumb BL instruction")
ASSERT(ADDR(.overlay) == 0x001f6000, "overlay address changed")
ASSERT(SIZEOF(.overlay) <= 0x400, "overlay exceeds reserved cave allocation")
