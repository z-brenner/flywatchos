#ifndef FLYOS_SIM_HOST_POLICY_H
#define FLYOS_SIM_HOST_POLICY_H

/*
 * HOST-ONLY executable specification. Do not link into firmware.
 * These ordinary C objects are not authorized target storage. Boolean context
 * and queue/display feedback are scenario inputs, not recovered Garmin APIs.
 * No timing, mutex ownership, callback lifetime, storage or delivery proof is
 * implied by passing this model's tests.
 */
#include <stdbool.h>
#include <stdint.h>

#define FLY_SIM_KEY_COUNT 5u
#define FLY_SIM_REDRAW_MAX_ATTEMPTS 8u

typedef enum {
    FLY_SIM_VIEW_INVALID = 0,
    FLY_SIM_VIEW_HOME,
    FLY_SIM_VIEW_NATIVE
} FlySimView;

typedef enum {
    FLY_SIM_KEY_LIGHT = 0,
    FLY_SIM_KEY_START,
    FLY_SIM_KEY_BACK,
    FLY_SIM_KEY_DOWN,
    FLY_SIM_KEY_UP
} FlySimKey;

typedef enum {
    FLY_SIM_PRESS = 0,
    FLY_SIM_REPEAT,
    FLY_SIM_RELEASE
} FlySimKeyPhase;

typedef enum {
    FLY_SIM_ROUTE_REJECTED = 0,
    FLY_SIM_ROUTE_GARMIN,
    FLY_SIM_ROUTE_FLYOS
} FlySimRoute;

typedef struct {
    FlySimView view;
    bool usb_mass_storage;
    bool input_ready;
} FlySimInputContext;

typedef struct {
    bool active[FLY_SIM_KEY_COUNT];
    FlySimRoute owner[FLY_SIM_KEY_COUNT];
    uint8_t flyos_held;
} FlySimKeys;

void fly_sim_keys_init(FlySimKeys *keys);
/*
 * Only a fresh, well-formed PRESS samples context. LIGHT always belongs to
 * Garmin, as does BACK (system escape). START/DOWN/UP belong to FlyOS only
 * for ready, non-USB, HOME presses when BACK is not held. This conservative
 * host policy is not a proposed five-key target implementation.
 * A latched valid sequence keeps its owner through later context changes.
 * Orphans, duplicate presses and invalid key/phase values are REJECTED without
 * delivery or latch mutation: do not reinterpret them as fresh native events.
 */
FlySimRoute fly_sim_key_event(FlySimKeys *keys, unsigned key,
                             FlySimKeyPhase phase,
                             const FlySimInputContext *context);

typedef struct {
    uint64_t epoch;
    unsigned attempt;
} FlySimRedrawToken;

typedef struct {
    FlySimView view;
    bool usb_mass_storage;
    bool safe_callback;
    bool source_mutex_locked;
    bool usb_mutex_locked;
    /* Abstract retry opportunity supplied by a scenario; no target cadence. */
    bool retry_due;
} FlySimRedrawContext;

typedef struct {
    bool attempted;
    bool enqueued;
    bool nonblocking;
    FlySimRedrawToken token;
} FlySimRedrawSubmission;

typedef struct {
    bool attached;
    bool pending;
    bool exhausted;
    bool epoch_exhausted;
    unsigned budget;
    unsigned attempts;
    uint64_t epoch;
    unsigned last_enqueued_attempt;
} FlySimRedraw;

/* Invalid budgets fail closed, yielding no submission; zero budget is valid. */
bool fly_sim_redraw_init(FlySimRedraw *redraw, bool attached, unsigned budget);
/* Each attached -> detached edge starts one epoch; reattach cancels it. */
void fly_sim_redraw_usb(FlySimRedraw *redraw, bool attached);
/*
 * Marks a FlyOS-owned button change dirty while detached. Native/rejected
 * routes do nothing. Each accepted change invalidates older display tokens.
 * Changes coalesce into one pending work interval: they never replenish its
 * attempt budget or bypass retry_due. Only completion or a USB lifecycle edge
 * can start a fresh budget. This is a host proposal, not installed behavior.
 * Caller must supply the actual latched route, not raw physical button bits.
 */
bool fly_sim_redraw_button(FlySimRedraw *redraw, FlySimRoute owner);
/*
 * Emits at most one abstract NONBLOCKING submission on an eligible callback.
 * queue_accepts is a scenario result, not an actual queue operation. Native
 * modals/invalid views and unsafe contexts preserve pending without spending
 * the budget. retry_due gates attempts after the first. Exhaustion preserves
 * pending; enqueue success is never display success.
 */
FlySimRedrawSubmission fly_sim_redraw_step(
    FlySimRedraw *redraw, const FlySimRedrawContext *context, bool queue_accepts);
/*
 * Only a current epoch's latest enqueued token with confirmed HOME display
 * completes work. A native/invalid display, stale token or mere render does
 * not acknowledge it. Completion remains possible after budget exhaustion.
 */
bool fly_sim_redraw_displayed(FlySimRedraw *redraw, FlySimRedrawToken token,
                              FlySimView displayed_view);

#endif
