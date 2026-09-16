/* fr245_1370_n64_atlas_shell: immutable fork of fr245_1370_neural_specimen_n64_controls.
 * Same pinned hook/payload envelopes; see docs/superpowers/specs/2026-09-15-flyos-n64-atlas-shell-design.md. */
ENTRY(flyos_hook_patch)
SECTIONS
{
    .hook 0x00009a20 : { KEEP(*(.hook)) }
    .keyhook 0x0000fa48 : { KEEP(*(.keyhook)) }
    .primary 0x001f6000 :
    {
        KEEP(*(.overlay.entry))
        *overlay.o(.text.scan_view)
        *overlay.o(.text.stable_view)
        *overlay.o(.text.flyos_key_event)
        *brain64_packed.o(.text.fly_brain64_reconstruct)
        *renderer.o(.text.pixel)
        *renderer.o(.text.text)
        *renderer.o(.rodata.fly_n64_atlas_letters*)
        *renderer.o(.rodata.fly_n64_atlas_stroke*)
    }
    .secondary 0x001fa400 :
    {
        *hook.o(.text*)
        *overlay.o(.text*)
        *brain64_packed.o(.text*)
        *renderer.o(.text*)
        *(.rodata*)
    }
    .forbidden : { *(.data*) *(.bss*) *(COMMON) }
    /DISCARD/ : { *(.comment*) *(.ARM.attributes*) *(.ARM.exidx*) *(.ARM.extab*) *(.eh_frame*) }
}
ASSERT(ADDR(.hook) == 0x00009a20, "hook address changed")
ASSERT(SIZEOF(.hook) == 4, "hook must be one Thumb BL")
ASSERT(ADDR(.keyhook) == 0x0000fa48, "key hook address changed")
ASSERT(SIZEOF(.keyhook) == 6, "key hook must be one Thumb B.W plus NOP")
ASSERT(ADDR(.primary) == 0x001f6000, "primary address changed")
ASSERT(n64_overlay_then_flush == 0x001f6000, "entry must be first")
ASSERT(SIZEOF(.primary) <= 0x3ff, "primary overflow or repair byte used")
ASSERT(ADDR(.secondary) == 0x001fa400, "secondary address changed")
ASSERT(SIZEOF(.secondary) <= 0x800, "secondary overflow")
ASSERT(ADDR(.primary)+SIZEOF(.primary) <= ADDR(.secondary), "segments overlap")
ASSERT(SIZEOF(.forbidden) == 0, "writable static storage forbidden")
