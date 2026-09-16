#include <stdint.h>
#include "fly/brain64.h"
#include "renderer.h"
#include "state.h"

typedef uint32_t (*dispatch_fn)(uint8_t *, int);
typedef void (*dirty_fn)(int, int, int, int);
typedef uint32_t (*queue_send_fn)(uint32_t, const void *, uint32_t, uint32_t);
typedef uint32_t (*tick_fn)(void);

void flyos_key_pass(uint32_t, uint32_t);

enum {
    VIEW_ROOT = 0x20003e84u,
    VIEW_CALLBACK = 0x0005adf5u,
    NODE_LOW = 0x1ffc0000u,
    NODE_HIGH = 0x2003ffacu,
    KEY_WORKSPACE = 0x1ffdbbc8u,
    KEY_RECORD_BYTES = 0x38u,
    KEY_LOCAL_OFFSET = 0x36u,
    KEY_MODE_OFFSET = 0x37u,
    KEY_COUNT = 5u,
    KEY_LIGHT = 0u,
    KEY_BACK = 2u,
    CHORD_HOLD_MS = 2000u,
    TICK_GETTER = 0x00007fa5u,
    /* session_flags() sentinel: this frame belongs to Garmin, so do not draw. */
    SESSION_NO_RENDER = 0xffu,
    /* stable_view() returns 0 for INVALID, 1 for NON_HOME, and otherwise the
     * first-visible watch-face node.  Real nodes are four-byte aligned and far
     * above 1, so the sentinel can never collide with one. */
    VIEW_NON_HOME = 1u
};

/*
 * Every ownership value is a compile-time constant, so fly_state_byte folds to
 * an 8-bit immediate and the complement discipline costs no code at all.
 * Comparing a whole byte against one of these is a stricter check than decoding
 * a nibble and testing its complement separately.
 */
#define L_IDLE   fly_state_byte(FLY_IDLE)
#define L_HELD   fly_state_byte(FLY_HELD)
#define L_PULSE  fly_state_byte(FLY_PULSE)
#define L_GARMIN fly_state_byte(GARMIN_HELD)
#define M_NORMAL  fly_state_byte(NORMAL)
#define M_CHORD   fly_state_byte(CHORD_HOLD)
#define M_PENDING fly_state_byte(SYSTEM_PENDING)
#define M_SYSTEM  fly_state_byte(SYSTEM_HOME)

static uint8_t valid_node(uint32_t node) {
    return (uint8_t)((node & 3u) == 0u && node >= NODE_LOW && node <= NODE_HIGH);
}

/*
 * Bounded snapshot classifier equivalent to the pinned Garmin finder/first-visible
 * pair for a stable list.  Every captured next pointer is validated before it is
 * followed.
 *
 * A structurally unusable list -- malformed root, unaligned or out-of-range node,
 * cycle, more than eight nodes, or no nodes at all -- is INVALID, meaning
 * "unknown", not "not home".  A usable list whose watch-face node is the first
 * visible node yields that node; any other usable list is NON_HOME.
 */
__attribute__((noinline)) static uint32_t scan_view(void) {
    uint32_t seen[8];
    uint32_t node = *(volatile const uint32_t *)VIEW_ROOT;
    uint32_t matching = 0u;
    uint32_t visible = 0u;
    unsigned count = 0u;

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
    return (matching != 0u && matching == visible) ? matching : VIEW_NON_HOME;
}

/*
 * Two bounded observations bracketed by root reads must agree.  An ABA change
 * restored before re-read is indistinguishable from a stable snapshot but cannot
 * redirect an unvalidated read or control flow.
 */
__attribute__((noinline)) static uint32_t stable_view(void) {
    uint32_t root = *(volatile const uint32_t *)VIEW_ROOT;
    uint32_t first = scan_view();
    if (first == FLY_VIEW_INVALID || *(volatile const uint32_t *)VIEW_ROOT != root)
        return FLY_VIEW_INVALID;
    return first == scan_view() ? first : FLY_VIEW_INVALID;
}

/* Ownership byte for one key: record +0x36.  The mode byte at +0x37 belongs to
 * the system-session (LIGHT) and detach (START) subsystems and is not addressed
 * anywhere in this file. */
static volatile uint8_t *key_local(uint32_t key) {
    return (volatile uint8_t *)(KEY_WORKSPACE + key * KEY_RECORD_BYTES + KEY_LOCAL_OFFSET);
}

/* FlySystemMode lives in LIGHT's mode byte, and only there.  START's mode byte
 * carries FlyDetachMode for a later task and is never addressed in this file. */
static volatile uint8_t *session_mode(void) {
    return (volatile uint8_t *)(KEY_WORKSPACE + KEY_LIGHT * KEY_RECORD_BYTES + KEY_MODE_OFFSET);
}

/* Garmin's own press timestamp, stamped into record offset zero at phase zero. */
static uint32_t key_down_ms(uint32_t key) {
    return *(volatile const uint32_t *)(KEY_WORKSPACE + key * KEY_RECORD_BYTES);
}

static uint8_t read_buttons(uint32_t d);

/*
 * Physical lines and FlyOS-owned bits are merged in this one callee rather than
 * in n64_overlay_then_flush.  That function's frame has zero slack under the
 * pinned 384-byte stack ceiling (184 + 16 + 184 is exactly 384), and holding a
 * single live result across one call instead of two keeps it there.
 */
__attribute__((noinline)) static uint8_t button_bits(uint32_t d) {
    volatile uint8_t *local = key_local(0u);
    uint8_t buttons = read_buttons(d);
    for (uint8_t bit = 1u; bit != 1u << KEY_COUNT; bit = (uint8_t)(bit << 1)) {
        if (*local == L_HELD || *local == L_PULSE) buttons |= bit;
        local = (volatile uint8_t *)((uint32_t)local + KEY_RECORD_BYTES);
    }
    return buttons;
}

/* One out-of-line exchange shared by all five keys: inlining the LDREXB/STREXB
 * loop into the loop body costs far more than the call. */
__attribute__((noinline)) static void clear_key_pulse(volatile uint8_t *local) {
    uint8_t expected = L_PULSE;
    (void)__atomic_compare_exchange_n(local, &expected, L_IDLE, 0,
                                      __ATOMIC_RELAXED, __ATOMIC_RELAXED);
}

__attribute__((noinline)) static void clear_key_pulses(void) {
    for (uint32_t key = 0u; key < KEY_COUNT; ++key) clear_key_pulse(key_local(key));
}

__attribute__((noinline)) static void request_redraw(uint32_t home) {
    struct {
        uint32_t node;
        uint16_t event;
    } message = {home, 0x50u};
    uint32_t queue = *(volatile const uint32_t *)0x1ffc7e14u;
    if (queue != 0u) (void)((queue_send_fn)0x000067d9u)(queue, &message, 1u, 0u);
}

/*
 * One step of the LIGHT+BACK system chord, shared by the hold and release paths
 * because both need the same two ownership bytes and the same mode byte.
 *
 * Holding both advances NORMAL -> CHORD_HOLD -> SYSTEM_PENDING.  A single
 * release breaks an armed-but-unconfirmed chord.  A confirmed chord commits to
 * SYSTEM_HOME only once neither chord key is still held -- the both-release
 * barrier -- so Garmin can never receive an orphan repeat or release phase from
 * either entry sequence.
 *
 * This is called on every FlyOS-owned phase of every key, not just LIGHT and
 * BACK.  It reads both chord bytes and the mode byte itself, so it is correct
 * for any key, and testing the key at each call site costs more than the call:
 * a third key pressed during a chord hold simply ticks the same state machine.
 */
__attribute__((noinline)) static void chord_step(void) {
    uint8_t light = *key_local(KEY_LIGHT);
    uint8_t back = *key_local(KEY_BACK);
    volatile uint8_t *mode = session_mode();
    uint8_t held = *mode;

    if (light == L_HELD && back == L_HELD) {
        if (held == M_NORMAL) {
            *mode = M_CHORD;
        } else if (held == M_CHORD) {
            /* Both hold times must clear the threshold, so the key pressed
             * second is the binding one. */
            uint32_t now = ((tick_fn)TICK_GETTER)();
            if ((now - key_down_ms(KEY_LIGHT)) >= CHORD_HOLD_MS &&
                (now - key_down_ms(KEY_BACK)) >= CHORD_HOLD_MS)
                *mode = M_PENDING;
        }
    } else if (held == M_CHORD) {
        *mode = M_NORMAL;
    } else if (held == M_PENDING && light != L_HELD && back != L_HELD) {
        *mode = M_SYSTEM;
    }
}

/*
 * One owner per physical sequence, decided once at phase zero and latched in the
 * key's own ownership byte.  Cached USB state no longer changes the decision and
 * no GPIO line can veto it: all five keys belong to FlyOS on a stable home,
 * unless a deliberate Garmin system session is running.
 */
__attribute__((noinline)) void flyos_key_event(uint32_t key, uint32_t phase) {
    uint32_t view = 0u;
    if (key < KEY_COUNT) {
        volatile uint8_t *local = key_local(key);
        if (phase == 0u) {
            /* A new press always begins a new ownership decision, and rewriting
             * this byte first normalizes any reset, legacy 13.76 or garbage
             * encoding found in it.  Only this key's ownership byte is touched,
             * so no global latch and no other sequence can be disturbed. */
            *local = L_IDLE;
            view = stable_view();
            /* NORMAL, CHORD_HOLD and SYSTEM_PENDING are FlyOS-owning modes.
             * SYSTEM_HOME, SYSTEM_EXCURSION and any unreadable latch are not.
             * Comparing whole bytes against the three constants validates the
             * complement at the same time and folds to three immediates. */
            uint8_t held = *session_mode();
            if (view > VIEW_NON_HOME &&
                (held == M_NORMAL || held == M_CHORD || held == M_PENDING)) {
                *local = L_HELD;
                goto owned;
            }
            /* NON_HOME, INVALID, or a live system session: Garmin owns the whole
             * sequence, and the latch makes every later phase pass through
             * without re-deciding. */
            *local = L_GARMIN;
        } else if (*local == L_HELD) {
            if (phase == 1u) {
                view = stable_view();
                if (view > VIEW_NON_HOME) {
                    *local = L_PULSE;
                    goto owned;
                }
                *local = L_IDLE;
            }
            chord_step();
            return;
        } else if (*local == L_PULSE) {
            return; /* still ours: a late phase after release is never leaked */
        }
    }
    flyos_key_pass(key, phase);
    return;
owned:
    /* Every FlyOS-owned press and release converges here: tick the chord state
     * machine, then ask for the one cosmetic redraw that shows the change. */
    chord_step();
    request_redraw(view);
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

/*
 * The excursion half of the session state machine, and the answer to "what does
 * the renderer get, if it runs at all".  Kept out of n64_overlay_then_flush's
 * own frame, which has no slack under the pinned 384-byte stack ceiling.
 *
 * SYSTEM_HOME -> SYSTEM_EXCURSION records that Garmin has actually been visited,
 * which is what stops a freshly committed session clearing itself while the
 * watch face is still up.  SYSTEM_EXCURSION -> NORMAL then needs a stable home
 * with every key released.  An INVALID view moves no valid mode at all.
 *
 * Returns SESSION_NO_RENDER when this frame belongs to Garmin: a non-home or
 * unclassifiable view, or a latch too corrupt to act on.
 */
__attribute__((noinline)) static uint8_t session_flags(uint32_t view, uint32_t d) {
    static const uint8_t presentation[5] = {
        0u, FLY_UI_CHORD_ARMED, FLY_UI_CHORD_ARMED, FLY_UI_SYSTEM, FLY_UI_SYSTEM
    };
    volatile uint8_t *mode = session_mode();
    uint8_t held = fly_state_read_byte(*mode);

    if (view <= VIEW_NON_HOME) {
        /* Only a stable non-home view records that Garmin was really visited;
         * an INVALID view moves nothing. */
        if (view == VIEW_NON_HOME && held == SYSTEM_HOME)
            *mode = fly_state_byte(SYSTEM_EXCURSION);
        return SESSION_NO_RENDER;
    }
    /* Stable home.  A finished excursion and an unreadable latch both recover
     * here, and only here: every key must be released first, so this can never
     * cut across a sequence still in progress. */
    if (held >= SYSTEM_EXCURSION && read_buttons(d) == 0u) {
        *mode = M_NORMAL;
        held = NORMAL;
    }
    /* Anything still unreadable fails open rather than drawing over Garmin. */
    return held < 5u ? presentation[held] : SESSION_NO_RENDER;
}

__attribute__((section(".overlay.entry"), used))
uint32_t n64_overlay_then_flush(uint8_t *framebuffer, int original_wait) {
    uint32_t d;
    uint8_t session;
    (void)original_wait;
    if (framebuffer == (uint8_t *)0) goto dispatch;
    d = *(volatile const uint32_t *)0x400ff0d0u;
    /* BACK no longer vetoes the FlyOS face: it is a FlyOS key now, so holding it
     * shows its own callout instead of blanking the frame. */
    session = session_flags(stable_view(), d);
    if (session == SESSION_NO_RENDER) goto dispatch;
    {
        FlyBrain64 brain;
        FlyBrainInputs inputs = {0};
        uint8_t battery;
        uint8_t usb_state = *(volatile const uint8_t *)0x1ffc6f25u;
        uint32_t tick = read_rtc_tick();
        inputs.buttons = button_bits(d);
        battery = battery_percent(*(volatile const uint32_t *)0x1ffcccd8u);
        if (battery <= 100u) {
            inputs.battery_percent = battery;
            inputs.valid_mask = FLY_BRAIN64_VALID_BATTERY;
        }
        fly_brain64_reconstruct(&brain, 0x46594f53u, tick, &inputs);
        n64_render(framebuffer, &brain, &inputs, tick,
                   (uint8_t)(session |
                             ((usb_state == 3u || usb_state == 4u) ? FLY_UI_USB : 0u)));
        clear_key_pulses();
        ((dirty_fn)0x0000f2e9u)(0, 0, 240, 240);
    }
dispatch:
    return ((dispatch_fn)0x0000e1a5u)(framebuffer, 0);
}
