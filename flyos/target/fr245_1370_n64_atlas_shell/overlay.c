#include <stdint.h>
#include "fly/brain64.h"
#include "state.h"

typedef uint32_t (*dispatch_fn)(uint8_t *, int);
typedef void (*dirty_fn)(int, int, int, int);
typedef uint32_t (*queue_send_fn)(uint32_t, const void *, uint32_t, uint32_t);
typedef uint32_t (*tick_fn)(void);

void n64_render(uint8_t *, const FlyBrain64 *, const FlyBrainInputs *, uint32_t, uint8_t);
void flyos_key_pass(uint32_t, uint32_t);

enum {
    VIEW_ROOT = 0x20003e84u,
    VIEW_CALLBACK = 0x0005adf5u,
    NODE_LOW = 0x1ffc0000u,
    NODE_HIGH = 0x2003ffacu,
    KEY_WORKSPACE = 0x1ffdbbc8u,
    KEY_RECORD_BYTES = 0x38u,
    KEY_STATE_OFFSET = 0x36u,
    KEY_LIGHT = 0u,
    KEY_START = 1u,
    KEY_BACK = 2u,
    CHORD_HOLD_MS = 2000u,
    TICK_GETTER = 0x00007fa5u
};

static uint8_t valid_node(uint32_t node) {
    return (uint8_t)((node & 3u) == 0u && node >= NODE_LOW && node <= NODE_HIGH);
}

/*
 * Bounded snapshot classifier equivalent to the pinned Garmin finder/first-visible
 * pair for a stable list.  Every captured next pointer is validated before it is
 * followed.  A structurally unusable list (malformed root, unaligned or out-of-range
 * node, cycle, more than eight nodes, or no nodes at all) is INVALID -- "unknown",
 * not "not home".  A usable list whose watch-face node is the first visible node is
 * HOME; any other usable list is NON_HOME.
 */
__attribute__((noinline)) static uint8_t scan_view(uint32_t *home) {
    uint32_t seen[8];
    uint32_t node = *(volatile const uint32_t *)VIEW_ROOT;
    uint32_t matching = 0u;
    uint32_t visible = 0u;
    unsigned count = 0u;

    *home = 0u;
    while (node != 0u) {
        if (count == 8u || valid_node(node) == 0u) return FLY_VIEW_INVALID;
        for (unsigned i = 0u; i < count; ++i) if (seen[i] == node) return FLY_VIEW_INVALID;
        seen[count] = node;
        uint32_t next = *(volatile const uint32_t *)(node + 4u);
        uint32_t callback = *(volatile const uint32_t *)(node + 8u);
        uint32_t flags = *(volatile const uint32_t *)(node + 0x50u);
        ++count;
        if (matching == 0u && callback == VIEW_CALLBACK) matching = node;
        if (visible == 0u && (flags & 2u) == 0u) visible = node;
        if (next != 0u && valid_node(next) == 0u) return FLY_VIEW_INVALID;
        node = next;
    }
    if (count == 0u) return FLY_VIEW_INVALID;
    if (matching == 0u || matching != visible) return FLY_VIEW_NON_HOME;
    *home = matching;
    return FLY_VIEW_HOME;
}

/*
 * Two bounded observations bracketed by root reads must agree on both the class
 * and the node.  An ABA change restored before re-read is indistinguishable from a
 * stable snapshot but cannot redirect an unvalidated read or control flow.
 */
__attribute__((noinline)) static struct FlyViewResult stable_view(void) {
    struct FlyViewResult result;
    uint32_t first_home = 0u;
    uint32_t second_home = 0u;
    uint32_t root = *(volatile const uint32_t *)VIEW_ROOT;
    uint8_t first = scan_view(&first_home);

    result.home = 0u;
    result.kind = FLY_VIEW_INVALID;
    if (*(volatile const uint32_t *)VIEW_ROOT != root) return result;
    if (scan_view(&second_home) != first || second_home != first_home) return result;
    result.home = first_home;
    result.kind = first;
    return result;
}

static volatile uint16_t *key_word(uint32_t key) {
    return (volatile uint16_t *)(KEY_WORKSPACE + key * KEY_RECORD_BYTES + KEY_STATE_OFFSET);
}

/* Garmin's own press timestamp, written to record offset zero at phase zero. */
static uint32_t key_down_ms(uint32_t key) {
    return *(volatile const uint32_t *)(KEY_WORKSPACE + key * KEY_RECORD_BYTES);
}

/*
 * Aligned 16-bit compare/exchange of the local nibble only.  Both the expected
 * and the desired word carry required_mode, so a concurrent mode change by the
 * other subsystem makes the exchange fail instead of overwriting it.
 */
static uint8_t cas_local(volatile uint16_t *word, uint8_t expected,
                         uint8_t desired, uint8_t required_mode) {
    uint16_t observed = fly_state_word(expected, required_mode);
    return (uint8_t)__atomic_compare_exchange_n(word, &observed,
                                                fly_state_word(desired, required_mode), 0,
                                                __ATOMIC_RELAXED, __ATOMIC_RELAXED);
}

/*
 * Aligned 16-bit compare/exchange of the mode nibble only.  The observed local
 * nibble is carried through unchanged, so a mode transition never rewrites the
 * owner of an in-progress sequence, and a concurrent local change makes the
 * exchange fail.
 */
static uint8_t cas_mode(volatile uint16_t *word, uint8_t expected_mode, uint8_t desired_mode) {
    uint16_t observed = *word;
    uint8_t local = fly_state_read_local(observed);
    if (local == FLY_STATE_INVALID || fly_state_read_mode(observed) != expected_mode) return 0u;
    return (uint8_t)__atomic_compare_exchange_n(word, &observed,
                                                fly_state_word(local, desired_mode), 0,
                                                __ATOMIC_RELAXED, __ATOMIC_RELAXED);
}

/* FlySystemMode latch, or FLY_STATE_INVALID for a reset/garbage LIGHT word. */
static uint8_t system_mode(void) {
    return fly_state_read_mode(*key_word(KEY_LIGHT));
}

static uint8_t session_is_flyos(uint8_t mode) {
    return (uint8_t)(mode == NORMAL || mode == CHORD_HOLD || mode == SYSTEM_PENDING);
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

static uint8_t pressed_gpio_mask(void) {
    return read_buttons(*(volatile const uint32_t *)0x400ff0d0u);
}

__attribute__((noinline)) static uint8_t owned_button_bits(void) {
    uint8_t buttons = 0u;
    for (uint32_t key = 0u; key < 5u; ++key) {
        uint8_t local = fly_state_read_local(*key_word(key));
        if (local == FLY_HELD || local == FLY_PULSE) buttons |= (uint8_t)(1u << key);
    }
    return buttons;
}

/* Release acknowledgement lasts exactly one rendered frame; only the local nibble moves. */
__attribute__((noinline)) static void clear_key_pulses(void) {
    for (uint32_t key = 0u; key < 5u; ++key) {
        volatile uint16_t *word = key_word(key);
        uint8_t mode = fly_state_read_mode(*word);
        if (mode != FLY_STATE_INVALID) (void)cas_local(word, FLY_PULSE, FLY_IDLE, mode);
    }
}

__attribute__((noinline)) static void request_redraw(uint32_t home) {
    struct {
        uint32_t node;
        uint16_t event;
    } message = {home, 0x50u};
    uint32_t queue = *(volatile const uint32_t *)0x1ffc7e14u;
    if (queue != 0u) (void)((queue_send_fn)0x000067d9u)(queue, &message, 1u, 0u);
}

static uint8_t chord_elapsed(uint32_t now, uint32_t light_down, uint32_t back_down) {
    /* The shorter of the two hold times -- that is, the key pressed second --
     * is the binding constraint: both must have been held the full threshold. */
    uint32_t oldest_elapsed = (now - light_down) < (now - back_down) ?
                              (now - light_down) : (now - back_down);
    return oldest_elapsed >= CHORD_HOLD_MS;
}

/* NORMAL -> CHORD_HOLD -> SYSTEM_PENDING while both chord keys are FlyOS-held. */
__attribute__((noinline)) static void chord_advance(void) {
    volatile uint16_t *light = key_word(KEY_LIGHT);
    uint8_t mode;
    if (fly_state_read_local(*light) != FLY_HELD) return;
    if (fly_state_read_local(*key_word(KEY_BACK)) != FLY_HELD) return;
    mode = fly_state_read_mode(*light);
    if (mode == NORMAL) {
        (void)cas_mode(light, NORMAL, CHORD_HOLD);
    } else if (mode == CHORD_HOLD &&
               chord_elapsed(((tick_fn)TICK_GETTER)(),
                             key_down_ms(KEY_LIGHT), key_down_ms(KEY_BACK))) {
        (void)cas_mode(light, CHORD_HOLD, SYSTEM_PENDING);
    }
}

/*
 * A single release breaks an armed-but-unconfirmed chord.  A confirmed chord
 * commits only once both chord sequences have left FLY_HELD, so Garmin can never
 * receive an orphan repeat or release phase from either of them.
 */
__attribute__((noinline)) static void chord_release(void) {
    volatile uint16_t *light = key_word(KEY_LIGHT);
    (void)cas_mode(light, CHORD_HOLD, NORMAL);
    if (fly_state_read_local(*light) != FLY_HELD &&
        fly_state_read_local(*key_word(KEY_BACK)) != FLY_HELD)
        (void)cas_mode(light, SYSTEM_PENDING, SYSTEM_HOME);
}

__attribute__((noinline)) void flyos_key_event(uint32_t key, uint32_t phase) {
    volatile uint16_t *word;
    uint16_t observed;
    uint8_t local;
    uint8_t mode;
    struct FlyViewResult view;

    if (key > 4u) {
        flyos_key_pass(key, phase);
        return;
    }
    word = key_word(key);
    observed = *word;
    local = fly_state_read_local(observed);
    mode = fly_state_read_mode(observed);

    if (phase != 0u) {
        /* Every later phase of a sequence consults only the latched local state. */
        if (local != FLY_HELD && local != FLY_PULSE) {
            flyos_key_pass(key, phase);
            return;
        }
        if (phase != 1u) {
            if (local == FLY_HELD && (key == KEY_LIGHT || key == KEY_BACK)) chord_advance();
            return;
        }
        view = stable_view();
        (void)cas_local(word, local,
                        view.kind == FLY_VIEW_HOME ? FLY_PULSE : FLY_IDLE, mode);
        if (key == KEY_LIGHT || key == KEY_BACK) chord_release();
        if (view.kind == FLY_VIEW_HOME) request_redraw(view.home);
        return;
    }

    /* Phase zero: a new physical press always begins a new ownership decision. */
    view = stable_view();
    if (local == FLY_STATE_INVALID || mode == FLY_STATE_INVALID ||
        (key > KEY_START && mode != NORMAL)) {
        /*
         * Reset, legacy 13.76, or otherwise unrecognized encoding.  Normalize it
         * only from a quiet stable home with every other GPIO released, so that
         * cleanup can never erase a valid latch or a sequence still in progress.
         */
        if (view.kind == FLY_VIEW_HOME &&
            (pressed_gpio_mask() & (uint8_t)~(uint8_t)(1u << key)) == 0u) {
            *word = fly_state_word(FLY_IDLE, NORMAL);
            local = FLY_IDLE;
            mode = NORMAL;
        } else {
            /*
             * Not normalizable here.  A complement-broken word already makes
             * every later phase fail open, but a valid local under a corrupt
             * mode would not, so latch GARMIN_HELD to keep the whole sequence
             * on one owner and leave Garmin no orphan phases.
             */
            if (local != FLY_STATE_INVALID && mode != FLY_STATE_INVALID)
                (void)cas_local(word, local, GARMIN_HELD, mode);
            flyos_key_pass(key, phase);
            return;
        }
    }
    if (view.kind == FLY_VIEW_HOME && session_is_flyos(system_mode()) &&
        cas_local(word, local, FLY_HELD, mode)) {
        if (key == KEY_LIGHT || key == KEY_BACK) chord_advance();
        request_redraw(view.home);
        return;
    }
    (void)cas_local(word, local, GARMIN_HELD, mode);
    flyos_key_pass(key, phase);
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
    struct FlyViewResult view;
    uint8_t mode;
    (void)original_wait;
    if (framebuffer == (uint8_t *)0) goto dispatch;
    view = stable_view();
    /* Only a stable classification may move a valid latch; INVALID changes nothing. */
    if (view.kind == FLY_VIEW_NON_HOME) {
        (void)cas_mode(key_word(KEY_LIGHT), SYSTEM_HOME, SYSTEM_EXCURSION);
        goto dispatch;
    }
    if (view.kind != FLY_VIEW_HOME) goto dispatch;
    mode = system_mode();
    if (mode == SYSTEM_EXCURSION && pressed_gpio_mask() == 0u &&
        cas_mode(key_word(KEY_LIGHT), SYSTEM_EXCURSION, NORMAL)) mode = NORMAL;
    if (mode == FLY_STATE_INVALID) goto dispatch;
    {
        FlyBrain64 brain;
        FlyBrainInputs inputs = {0};
        uint8_t battery;
        uint8_t usb_state = *(volatile const uint8_t *)0x1ffc6f25u;
        uint32_t tick = read_rtc_tick();
        uint8_t ui = (uint8_t)((usb_state == 3u || usb_state == 4u) ? FLY_UI_USB : 0u);
        if (mode == CHORD_HOLD || mode == SYSTEM_PENDING) ui |= FLY_UI_CHORD_ARMED;
        else if (mode == SYSTEM_HOME || mode == SYSTEM_EXCURSION) ui |= FLY_UI_SYSTEM;
        inputs.buttons = (uint8_t)(pressed_gpio_mask() | owned_button_bits());
        battery = battery_percent(*(volatile const uint32_t *)0x1ffcccd8u);
        if (battery <= 100u) {
            inputs.battery_percent = battery;
            inputs.valid_mask = FLY_BRAIN64_VALID_BATTERY;
        }
        fly_brain64_reconstruct(&brain, 0x46594f53u, tick, &inputs);
        n64_render(framebuffer, &brain, &inputs, tick, ui);
        clear_key_pulses();
        ((dirty_fn)0x0000f2e9u)(0, 0, 240, 240);
    }
dispatch:
    return ((dispatch_fn)0x0000e1a5u)(framebuffer, 0);
}
