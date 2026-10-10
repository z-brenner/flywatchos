#include "sim/host_policy.h"

#include <string.h>

void fly_sim_keys_init(FlySimKeys *keys) {
    if (keys != NULL) {
        memset(keys, 0, sizeof(*keys));
    }
}

FlySimRoute fly_sim_key_event(FlySimKeys *keys, unsigned key,
                             FlySimKeyPhase phase,
                             const FlySimInputContext *context) {
    FlySimRoute owner;
    uint8_t bit;
    if (keys == NULL || key >= FLY_SIM_KEY_COUNT ||
        (phase != FLY_SIM_PRESS && phase != FLY_SIM_REPEAT &&
         phase != FLY_SIM_RELEASE)) {
        return FLY_SIM_ROUTE_REJECTED;
    }
    if ((phase == FLY_SIM_PRESS) == keys->active[key]) {
        return FLY_SIM_ROUTE_REJECTED;
    }
    bit = (uint8_t)(1u << key);
    if (phase == FLY_SIM_PRESS) {
        owner = FLY_SIM_ROUTE_GARMIN;
        if (key != FLY_SIM_KEY_LIGHT && key != FLY_SIM_KEY_BACK &&
            !keys->active[FLY_SIM_KEY_BACK] && context != NULL &&
            context->view == FLY_SIM_VIEW_HOME && context->input_ready &&
            !context->usb_mass_storage) {
            owner = FLY_SIM_ROUTE_FLYOS;
        }
        keys->active[key] = true;
        keys->owner[key] = owner;
        if (owner == FLY_SIM_ROUTE_FLYOS) {
            keys->flyos_held |= bit;
        }
        return owner;
    }
    owner = keys->owner[key];
    if (phase == FLY_SIM_RELEASE) {
        keys->active[key] = false;
        keys->owner[key] = FLY_SIM_ROUTE_REJECTED;
        keys->flyos_held &= (uint8_t)~bit;
    }
    return owner;
}

bool fly_sim_redraw_init(FlySimRedraw *redraw, bool attached, unsigned budget) {
    if (redraw == NULL) {
        return false;
    }
    memset(redraw, 0, sizeof(*redraw));
    redraw->attached = attached;
    if (budget > FLY_SIM_REDRAW_MAX_ATTEMPTS) {
        return false;
    }
    redraw->budget = budget;
    return true;
}

void fly_sim_redraw_usb(FlySimRedraw *redraw, bool attached) {
    if (redraw == NULL || attached == redraw->attached) {
        return;
    }
    redraw->attached = attached;
    redraw->pending = false;
    redraw->attempts = 0u;
    redraw->last_enqueued_attempt = 0u;
    redraw->exhausted = false;
    if (attached) {
        return;
    }
    if (redraw->epoch == UINT64_MAX) {
        redraw->epoch_exhausted = true;
        return;
    }
    ++redraw->epoch;
    redraw->pending = true;
    redraw->exhausted = redraw->budget == 0u;
}

FlySimRedrawSubmission fly_sim_redraw_step(
    FlySimRedraw *redraw, const FlySimRedrawContext *context, bool queue_accepts) {
    FlySimRedrawSubmission result = {0};
    if (redraw == NULL || context == NULL || !redraw->pending ||
        redraw->attached || redraw->epoch_exhausted ||
        redraw->budget > FLY_SIM_REDRAW_MAX_ATTEMPTS ||
        redraw->attempts >= redraw->budget ||
        context->view != FLY_SIM_VIEW_HOME || context->usb_mass_storage ||
        !context->safe_callback || context->source_mutex_locked ||
        context->usb_mutex_locked ||
        (redraw->attempts != 0u && !context->retry_due)) {
        return result;
    }
    ++redraw->attempts;
    result.attempted = true;
    result.nonblocking = true;
    result.enqueued = queue_accepts;
    result.token.epoch = redraw->epoch;
    result.token.attempt = redraw->attempts;
    if (queue_accepts) {
        redraw->last_enqueued_attempt = redraw->attempts;
    }
    redraw->exhausted = redraw->attempts == redraw->budget;
    return result;
}

bool fly_sim_redraw_displayed(FlySimRedraw *redraw, FlySimRedrawToken token,
                              FlySimView displayed_view) {
    if (redraw == NULL || !redraw->pending || redraw->attached ||
        redraw->epoch_exhausted || displayed_view != FLY_SIM_VIEW_HOME ||
        token.epoch != redraw->epoch || token.attempt == 0u ||
        token.attempt != redraw->last_enqueued_attempt) {
        return false;
    }
    redraw->pending = false;
    redraw->exhausted = false;
    return true;
}
