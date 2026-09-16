#include <stdint.h>
#include "fly/brain64.h"
#include "renderer.h"

typedef uint32_t (*dispatch_fn)(uint8_t *, int);
typedef void (*dirty_fn)(int, int, int, int);
typedef uint32_t (*queue_send_fn)(uint32_t, const void *, uint32_t, uint32_t);

void flyos_key_pass(uint32_t, uint32_t);

enum {
    VIEW_ROOT = 0x20003e84u,
    VIEW_CALLBACK = 0x0005adf5u,
    NODE_LOW = 0x1ffc0000u,
    NODE_HIGH = 0x2003ffacu,
    KEY_WORKSPACE = 0x1ffdbbc8u,
    KEY_RECORD_BYTES = 0x38u,
    KEY_PAD_STATUS = 0x36u,
    KEY_IDLE = 0xff00u,
    KEY_OWNED = 0x5ea1u,
    KEY_PULSE = 0x5da2u
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

static uint32_t stable_home_node(void) {
    uint32_t root = *(volatile const uint32_t *)VIEW_ROOT;
    uint32_t first = scan_home();
    if (first == 0u || *(volatile const uint32_t *)VIEW_ROOT != root) return 0u;
    return first == scan_home() ? first : 0u;
}

static volatile uint16_t *key_pad(uint32_t key) {
    return (volatile uint16_t *)(KEY_WORKSPACE + key * KEY_RECORD_BYTES + KEY_PAD_STATUS);
}

static void clear_key_pulse(volatile uint16_t *status) {
    uint16_t expected = KEY_PULSE;
    (void)__atomic_compare_exchange_n(status, &expected, KEY_IDLE, 0,
                                      __ATOMIC_RELAXED, __ATOMIC_RELAXED);
}

__attribute__((noinline)) static uint8_t owned_button_bits(void) {
    uint8_t buttons = 0u;
    uint16_t status = *key_pad(1u);
    if (status == KEY_OWNED || status == KEY_PULSE) buttons |= 1u << 1;
    status = *key_pad(3u);
    if (status == KEY_OWNED || status == KEY_PULSE) buttons |= 1u << 3;
    status = *key_pad(4u);
    if (status == KEY_OWNED || status == KEY_PULSE) buttons |= 1u << 4;
    return buttons;
}

__attribute__((noinline)) static void clear_key_pulses(void) {
    clear_key_pulse(key_pad(1u));
    clear_key_pulse(key_pad(3u));
    clear_key_pulse(key_pad(4u));
}

__attribute__((noinline)) static void request_redraw(uint32_t home) {
    struct {
        uint32_t node;
        uint16_t event;
    } message = {home, 0x50u};
    uint32_t queue = *(volatile const uint32_t *)0x1ffc7e14u;
    if (queue != 0u) (void)((queue_send_fn)0x000067d9u)(queue, &message, 1u, 0u);
}

__attribute__((noinline)) void flyos_key_event(uint32_t key, uint32_t state) {
    if (key == 1u || key == 3u || key == 4u) {
        volatile uint16_t *status;
        status = key_pad(key);
        if (state == 0u) {
            /* A new physical press always begins a new ownership decision. */
            *status = KEY_IDLE;
            uint8_t usb = *(volatile const uint8_t *)0x1ffc6f25u;
            uint32_t d = *(volatile const uint32_t *)0x400ff0d0u;
            uint32_t home = (usb == 3u || usb == 4u || (d & 2u) == 0u) ?
                            0u : stable_home_node();
            if (home != 0u) {
                *status = KEY_OWNED;
                request_redraw(home);
                return;
            }
        }
        else if (*status == KEY_OWNED) {
            if (state == 1u) {
                uint32_t home = stable_home_node();
                *status = home == 0u ? KEY_IDLE : KEY_PULSE;
                if (home != 0u) request_redraw(home);
            }
            return;
        }
    }
    flyos_key_pass(key, state);
}

static uint8_t read_buttons(uint32_t d) {
    uint32_t a = *(volatile const uint32_t *)0x400ff010u;
    uint32_t c = *(volatile const uint32_t *)0x400ff090u;
    /*
     * Gather the five active-low key lines into one word and invert once
     * rather than inverting each line: LIGHT is C11, START D10, BACK D1,
     * DOWN A20 and UP A22.  `d` stays the caller's single sample, and the
     * two port reads keep their order, so this is purely a smaller encoding
     * of the same value.
     */
    uint32_t held = ((c >> 11) & 1u) | (((d >> 10) & 1u) << 1) |
                    (((d >> 1) & 1u) << 2) | (((a >> 20) & 1u) << 3) |
                    (((a >> 22) & 1u) << 4);

    return (uint8_t)(~held & 0x1fu);
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

static uint8_t battery_percent(uint32_t bits) {
    uint32_t exponent;
    uint32_t mantissa;
    if (bits == 0x80000000u) return 0u;
    if ((bits & 0x80000000u) != 0u || bits > 0x42c80000u) return 0xffu;
    exponent = (bits >> 23) & 0xffu;
    if (exponent == 0xffu) return 0xffu;
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
    if ((d & 2u) == 0u || stable_home_node() == 0u) goto dispatch;
    {
        FlyBrain64 brain;
        FlyBrainInputs inputs = {0};
        uint8_t battery;
        uint8_t usb_state = *(volatile const uint8_t *)0x1ffc6f25u;
        uint32_t tick = read_rtc_tick();
        inputs.buttons = (uint8_t)(read_buttons(d) | owned_button_bits());
        battery = battery_percent(*(volatile const uint32_t *)0x1ffcccd8u);
        if (battery <= 100u) {
            inputs.battery_percent = battery;
            inputs.valid_mask = FLY_BRAIN64_VALID_BATTERY;
        }
        fly_brain64_reconstruct(&brain, 0x46594f53u, tick, &inputs);
        /* FLY_UI_CHORD_ARMED and FLY_UI_SYSTEM stay clear: nothing on this
         * image decides a chord hold or a system session yet, and the
         * five-key ownership state machine that will set them is a later
         * task.  Fabricating either here would be inventing telemetry. */
        n64_render(framebuffer, &brain, &inputs, tick,
                   (uint8_t)((usb_state == 3u || usb_state == 4u) ? FLY_UI_USB : 0u));
        clear_key_pulses();
        ((dirty_fn)0x0000f2e9u)(0, 0, 240, 240);
    }
dispatch:
    return ((dispatch_fn)0x0000e1a5u)(framebuffer, 0);
}
