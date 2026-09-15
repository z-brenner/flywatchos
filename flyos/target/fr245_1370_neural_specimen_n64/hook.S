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
