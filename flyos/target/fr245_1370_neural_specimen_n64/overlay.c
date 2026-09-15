#include <stdint.h>
#include "fly/brain64.h"

typedef uint32_t (*dispatch_fn)(uint8_t *, int);
typedef void (*dirty_fn)(int, int, int, int);

void n64_render(uint8_t *, const FlyBrain64 *, const FlyBrainInputs *, uint32_t, uint8_t);

enum {
    VIEW_ROOT = 0x20003e84u,
    VIEW_CALLBACK = 0x0005adf5u,
    NODE_LOW = 0x1ffc0000u,
    NODE_HIGH = 0x2003ffacu
};

static uint8_t valid_node(uint32_t node) {
    return (uint8_t)((node & 3u) == 0u && node >= NODE_LOW && node <= NODE_HIGH);
}

/*
 * Bounded snapshot predicate equivalent to the pinned Garmin finder/first-visible
 * pair for a stable list.  Every captured next pointer is validated before it is
 * followed.  home_active requires two bounded observations to agree and brackets
 * them with root reads.  An ABA change restored before re-read is indistinguishable
 * from a stable snapshot but cannot redirect an unvalidated read or control flow.
 */
__attribute__((noinline)) static uint32_t scan_home(void) {
    uint32_t seen[8];
    uint32_t node = *(volatile const uint32_t *)VIEW_ROOT;
    uint32_t matching = 0u;
    uint32_t visible = 0u;
    unsigned count = 0u;

    while (node != 0u) {
        if (count == 8u || valid_node(node) == 0u) return 0u;
        for (unsigned i = 0u; i < count; ++i) if (seen[i] == node) return 0u;
        seen[count] = node;
        uint32_t next = *(volatile const uint32_t *)(node + 4u);
        uint32_t callback = *(volatile const uint32_t *)(node + 8u);
        uint32_t flags = *(volatile const uint32_t *)(node + 0x50u);
        ++count;
        if (matching == 0u && callback == VIEW_CALLBACK) matching = node;
        if (visible == 0u && (flags & 2u) == 0u) visible = node;
        if (next != 0u && valid_node(next) == 0u) return 0u;
        node = next;
    }
    return matching != 0u && matching == visible ? matching : 0u;
}

static uint8_t home_active(void) {
    uint32_t root = *(volatile const uint32_t *)VIEW_ROOT;
    uint32_t first = scan_home();
    if (first == 0u || *(volatile const uint32_t *)VIEW_ROOT != root) return 0u;
    return (uint8_t)(first == scan_home());
}

static uint8_t read_buttons(uint32_t d) {
    uint32_t a = *(volatile const uint32_t *)0x400ff010u;
    uint32_t c = *(volatile const uint32_t *)0x400ff090u;
    return (uint8_t)((((c & 0x00000800u) == 0u) << 0) |
                     (((d & 0x00000400u) == 0u) << 1) |
                     (((d & 0x00000002u) == 0u) << 2) |
                     (((a & 0x00100000u) == 0u) << 3) |
                     (((a & 0x00400000u) == 0u) << 4));
}

static uint32_t read_rtc_tick(void) {
    volatile const uint32_t *rtc = (volatile const uint32_t *)0x4003d000u;
    for (unsigned attempt = 0u; attempt < 2u; ++attempt) {
        uint32_t before = rtc[0];
        uint32_t prescaler = rtc[1];
        uint32_t after = rtc[0];
        if (before == after) return (after << 15) | (prescaler & 0x7fffu);
    }
    return UINT32_MAX;
}

static uint8_t battery_percent(uint32_t bits, uint8_t *valid) {
    uint32_t exponent;
    uint32_t mantissa;
    *valid = 0u;
    if (bits == 0x80000000u) { *valid = 1u; return 0u; }
    if ((bits & 0x80000000u) != 0u || bits > 0x42c80000u) return 0u;
    exponent = (bits >> 23) & 0xffu;
    if (exponent == 0xffu) return 0u;
    *valid = 1u;
    if (exponent < 127u) return 0u;
    mantissa = (bits & 0x007fffffu) | 0x00800000u;
    return (uint8_t)(mantissa >> (150u - exponent));
}

__attribute__((section(".overlay.entry"), used))
uint32_t n64_overlay_then_flush(uint8_t *framebuffer, int original_wait) {
    uint32_t d;
    (void)original_wait;
    if (framebuffer == (uint8_t *)0) goto dispatch;
    d = *(volatile const uint32_t *)0x400ff0d0u;
    if ((d & 2u) == 0u || home_active() == 0u) goto dispatch;
    {
        FlyBrain64 brain;
        FlyBrainInputs inputs = {0};
        uint8_t battery_valid;
        uint8_t usb_state = *(volatile const uint8_t *)0x1ffc6f25u;
        uint32_t tick = read_rtc_tick();
        inputs.buttons = read_buttons(d);
        inputs.battery_percent = battery_percent(
            *(volatile const uint32_t *)0x1ffcccd8u, &battery_valid);
        if (battery_valid != 0u) inputs.valid_mask = FLY_BRAIN64_VALID_BATTERY;
        fly_brain64_reconstruct(&brain, 0x46594f53u, tick, &inputs);
        n64_render(framebuffer, &brain, &inputs, tick,
                   (uint8_t)(usb_state == 3u || usb_state == 4u));
        ((dirty_fn)0x0000f2e9u)(0, 0, 240, 240);
    }
dispatch:
    return ((dispatch_fn)0x0000e1a5u)(framebuffer, 0);
}
