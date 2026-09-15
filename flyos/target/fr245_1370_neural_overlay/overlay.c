#include <stdint.h>
#include "fly/brain32.h"
#include "display/brain_ascii.h"

typedef uint32_t (*dispatch_flush_fn)(uint8_t *, int);
typedef void (*dirty_add_fn)(int, int, int, int);

static uint8_t read_buttons(void) {
    uint32_t a = *(volatile const uint32_t *)0x400ff010u;
    uint32_t c = *(volatile const uint32_t *)0x400ff090u;
    uint32_t d = *(volatile const uint32_t *)0x400ff0d0u;
    return (uint8_t)((((c & 0x00000800u) == 0u) << 0) |
                     (((d & 0x00000400u) == 0u) << 1) |
                     (((d & 0x00000002u) == 0u) << 2) |
                     (((a & 0x00100000u) == 0u) << 3) |
                     (((a & 0x00400000u) == 0u) << 4));
}

/* Exactly three volatile reads per attempt, at most two attempts. The
 * invalid sentinel avoids presenting a mixed seconds/prescaler sample. */
static uint32_t read_rtc_tick(void) {
    volatile const uint32_t *rtc = (volatile const uint32_t *)0x4003d000u;
    for (unsigned attempt = 0; attempt < 2u; ++attempt) {
        uint32_t before = rtc[0];
        uint32_t prescaler = rtc[1];
        uint32_t after = rtc[0];
        if (before == after) return (after << 15) | (prescaler & 0x7fffu);
    }
    return UINT32_MAX;
}

__attribute__((section(".overlay.entry"), used))
uint32_t overlay_then_flush(uint8_t *framebuffer, int original_wait) {
    (void)original_wait;
    if (framebuffer != (uint8_t *)0 &&
        *(volatile const uint32_t *)0x1ffdb754u == 0x0000ebfcu &&
        *(volatile const uint8_t *)0x1fff223cu == 1u) {
        FlyBrain32 brain;
        uint8_t buttons = read_buttons();
        uint32_t tick = read_rtc_tick();
        fly_brain32_reconstruct(&brain, 0x46594f53u, tick, buttons);
        fly_brain_ascii_render(framebuffer, &brain, tick, buttons);
        ((dirty_add_fn)0x0000f2e9u)(0, 0, 240, 240);
    }
    return ((dispatch_flush_fn)0x0000e1a5u)(framebuffer, 0);
}
