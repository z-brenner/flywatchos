.syntax unified
.cpu cortex-m4
.thumb
.section .hook.display, "ax", %progbits
.balign 2
.global probe_display_patch
.type probe_display_patch, %function
.thumb_func
probe_display_patch:
    bl probe_display
.size probe_display_patch, . - probe_display_patch
