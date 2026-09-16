.syntax unified
.cpu cortex-m4
.thumb

.section .hook, "ax", %progbits
.balign 2
.global flyos_hook_patch
.type flyos_hook_patch, %function
.thumb_func
flyos_hook_patch:
    bl n64_overlay_then_flush
.size flyos_hook_patch, . - flyos_hook_patch

.section .keyhook, "ax", %progbits
.balign 2
.global flyos_key_hook_patch
.type flyos_key_hook_patch, %function
.thumb_func
flyos_key_hook_patch:
    b.w flyos_key_event
    nop
.size flyos_key_hook_patch, . - flyos_key_hook_patch

.section .text.flyos_key_pass, "ax", %progbits
.balign 2
.global flyos_key_pass
.type flyos_key_pass, %function
.thumb_func
flyos_key_pass:
    push {r4, r5, lr}
    rsb.w r2, r0, r0, lsl #3
    movw r3, #0xfa4f
    bx r3
.size flyos_key_pass, . - flyos_key_pass
