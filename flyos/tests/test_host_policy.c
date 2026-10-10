#include "sim/host_policy.h"

#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <string.h>

#define CHECK(condition)                                                       \
    do {                                                                       \
        if (!(condition)) {                                                    \
            fprintf(stderr, "check failed: %s (%s:%d)\n", #condition,        \
                    __FILE__, __LINE__);                                       \
            exit(EXIT_FAILURE);                                                \
        }                                                                      \
    } while (0)

static const FlySimInputContext ready_home = {
    FLY_SIM_VIEW_HOME, false, true
};

static void test_home_press_selects_flyos(void) {
    FlySimKeys keys;
    fly_sim_keys_init(&keys);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_FLYOS);
    CHECK(keys.flyos_held == (1u << FLY_SIM_KEY_START));
}

static FlySimRoute expected_press(unsigned key,
                                  const FlySimInputContext *context) {
    return key != FLY_SIM_KEY_LIGHT && key != FLY_SIM_KEY_BACK &&
                   context != NULL && context->view == FLY_SIM_VIEW_HOME &&
                   !context->usb_mass_storage && context->input_ready
               ? FLY_SIM_ROUTE_FLYOS : FLY_SIM_ROUTE_GARMIN;
}

static void test_all_owners_survive_context_transitions(void) {
    static const FlySimView views[] = {
        FLY_SIM_VIEW_INVALID, FLY_SIM_VIEW_HOME, FLY_SIM_VIEW_NATIVE,
        (FlySimView)99
    };
    for (unsigned key = 0u; key < FLY_SIM_KEY_COUNT; ++key) {
        for (unsigned from = 0u; from < 16u; ++from) {
            const FlySimInputContext before = {
                views[from % 4u], (from & 4u) != 0u, (from & 8u) != 0u
            };
            for (unsigned to = 0u; to < 16u; ++to) {
                FlySimKeys keys;
                const FlySimInputContext after = {
                    views[to % 4u], (to & 4u) != 0u, (to & 8u) != 0u
                };
                const FlySimRoute owner = expected_press(key, &before);
                fly_sim_keys_init(&keys);
                CHECK(fly_sim_key_event(&keys, key, FLY_SIM_PRESS, &before)
                      == owner);
                CHECK(fly_sim_key_event(&keys, key, FLY_SIM_REPEAT, &after)
                      == owner);
                CHECK(keys.active[key]);
                CHECK(keys.flyos_held == (owner == FLY_SIM_ROUTE_FLYOS
                      ? (uint8_t)(1u << key) : 0u));
                CHECK(fly_sim_key_event(&keys, key, FLY_SIM_RELEASE, &after)
                      == owner);
                CHECK(!keys.active[key]);
                CHECK(keys.flyos_held == 0u);
                CHECK(fly_sim_key_event(&keys, key, FLY_SIM_PRESS, &after)
                      == expected_press(key, &after));
            }
        }
    }
}

static void test_malformed_events_do_not_mutate_ownership(void) {
    FlySimKeys keys;
    FlySimKeys before;
    fly_sim_keys_init(&keys);
    before = keys;
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_REPEAT,
                           &ready_home) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_RELEASE,
                           &ready_home) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_COUNT, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_sim_key_event(&keys, UINT_MAX, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, (FlySimKeyPhase)-1,
                           &ready_home) == FLY_SIM_ROUTE_REJECTED);
    CHECK(memcmp(&before, &keys, sizeof(keys)) == 0);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_FLYOS);
    before = keys;
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, (FlySimKeyPhase)3,
                           &ready_home) == FLY_SIM_ROUTE_REJECTED);
    CHECK(memcmp(&before, &keys, sizeof(keys)) == 0);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_RELEASE,
                           NULL) == FLY_SIM_ROUTE_FLYOS);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_RELEASE,
                           NULL) == FLY_SIM_ROUTE_REJECTED);
}

static void test_null_snapshot_is_native_and_keys_are_independent(void) {
    FlySimKeys keys;
    fly_sim_keys_init(&keys);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_PRESS,
                           NULL) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_DOWN, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_FLYOS);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_UP, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_FLYOS);
    CHECK(keys.flyos_held == ((1u << FLY_SIM_KEY_DOWN) |
                             (1u << FLY_SIM_KEY_UP)));
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_DOWN, FLY_SIM_RELEASE,
                           &ready_home) == FLY_SIM_ROUTE_FLYOS);
    CHECK(keys.flyos_held == (1u << FLY_SIM_KEY_UP));
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_RELEASE,
                           &ready_home) == FLY_SIM_ROUTE_GARMIN);
}

static void test_back_chord_affects_only_fresh_presses(void) {
    FlySimKeys keys;
    fly_sim_keys_init(&keys);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_UP, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_FLYOS);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_BACK, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_UP, FLY_SIM_REPEAT,
                           &ready_home) == FLY_SIM_ROUTE_FLYOS);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_BACK, FLY_SIM_RELEASE,
                           &ready_home) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_RELEASE,
                           &ready_home) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_sim_key_event(&keys, FLY_SIM_KEY_START, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_FLYOS);
}

static void test_null_key_state_fails_closed(void) {
    fly_sim_keys_init(NULL);
    CHECK(fly_sim_key_event(NULL, FLY_SIM_KEY_START, FLY_SIM_PRESS,
                           &ready_home) == FLY_SIM_ROUTE_REJECTED);
}

static const FlySimRedrawContext safe_home = {
    FLY_SIM_VIEW_HOME, false, true, false, false, true
};

static void test_detach_needs_actual_display_acknowledgment(void) {
    FlySimRedraw redraw;
    FlySimRedrawSubmission request;
    CHECK(fly_sim_redraw_init(&redraw, true, 3u));
    CHECK(!fly_sim_redraw_step(&redraw, &safe_home, true).attempted);
    CHECK(!redraw.pending);
    fly_sim_redraw_usb(&redraw, false);
    CHECK(redraw.pending);
    CHECK(redraw.epoch == 1u);
    request = fly_sim_redraw_step(&redraw, &safe_home, true);
    CHECK(request.attempted && request.enqueued && request.nonblocking);
    CHECK(redraw.pending);
    CHECK(redraw.attempts == 1u);
    CHECK(!fly_sim_redraw_displayed(&redraw, request.token,
                                    FLY_SIM_VIEW_NATIVE));
    CHECK(!fly_sim_redraw_displayed(&redraw, request.token,
                                    FLY_SIM_VIEW_INVALID));
    CHECK(redraw.pending);
    CHECK(fly_sim_redraw_displayed(&redraw, request.token, FLY_SIM_VIEW_HOME));
    CHECK(!redraw.pending);
    CHECK(!fly_sim_redraw_displayed(&redraw, request.token, FLY_SIM_VIEW_HOME));
    CHECK(!fly_sim_redraw_step(&redraw, &safe_home, true).attempted);
}

static void test_redraw_safety_guards_and_modals_preserve_pending(void) {
    for (unsigned mask = 0u; mask < 128u; ++mask) {
        FlySimRedraw redraw;
        FlySimRedrawContext context = {
            (mask & 1u) != 0u ? FLY_SIM_VIEW_NATIVE : FLY_SIM_VIEW_HOME,
            (mask & 2u) != 0u, (mask & 4u) == 0u,
            (mask & 8u) != 0u, (mask & 16u) != 0u, (mask & 32u) != 0u
        };
        const bool eligible = (mask & 31u) == 0u;
        const bool accepts = (mask & 64u) != 0u;
        FlySimRedrawSubmission result;
        CHECK(fly_sim_redraw_init(&redraw, true, 3u));
        fly_sim_redraw_usb(&redraw, false);
        result = fly_sim_redraw_step(&redraw, &context, accepts);
        CHECK(result.attempted == eligible);
        CHECK(result.enqueued == (eligible && accepts));
        CHECK(result.nonblocking == eligible);
        CHECK(redraw.pending);
        CHECK(redraw.attempts == (eligible ? 1u : 0u));
    }
    {
        FlySimRedraw redraw;
        FlySimRedrawContext context = safe_home;
        CHECK(fly_sim_redraw_init(&redraw, true, 3u));
        fly_sim_redraw_usb(&redraw, false);
        context.view = FLY_SIM_VIEW_INVALID;
        CHECK(!fly_sim_redraw_step(&redraw, &context, true).attempted);
        context.view = (FlySimView)99;
        CHECK(!fly_sim_redraw_step(&redraw, &context, true).attempted);
        CHECK(!fly_sim_redraw_step(&redraw, NULL, true).attempted);
        for (unsigned step = 0u; step < 100u; ++step) {
            context.view = FLY_SIM_VIEW_NATIVE;
            CHECK(!fly_sim_redraw_step(&redraw, &context, true).attempted);
        }
        CHECK(redraw.pending && redraw.attempts == 0u);
        CHECK(fly_sim_redraw_step(&redraw, &safe_home, true).attempted);
    }
}

static void test_queue_failure_and_missing_ack_have_bounded_retries(void) {
    for (unsigned budget = 0u; budget <= FLY_SIM_REDRAW_MAX_ATTEMPTS; ++budget) {
        for (unsigned accepts = 0u; accepts < 2u; ++accepts) {
            FlySimRedraw redraw;
            FlySimRedrawSubmission last = {0};
            CHECK(fly_sim_redraw_init(&redraw, true, budget));
            fly_sim_redraw_usb(&redraw, false);
            for (unsigned attempt = 0u; attempt < budget; ++attempt) {
                last = fly_sim_redraw_step(&redraw, &safe_home, accepts != 0u);
                CHECK(last.attempted && last.nonblocking);
                CHECK(last.enqueued == (accepts != 0u));
                CHECK(last.token.epoch == redraw.epoch);
                CHECK(last.token.attempt == attempt + 1u);
                CHECK(redraw.pending);
            }
            for (unsigned extra = 0u; extra < 100u; ++extra) {
                CHECK(!fly_sim_redraw_step(&redraw, &safe_home, true).attempted);
            }
            CHECK(redraw.pending && redraw.exhausted);
            CHECK(redraw.attempts == budget);
            CHECK(fly_sim_redraw_displayed(&redraw, last.token,
                                           FLY_SIM_VIEW_HOME) ==
                  (accepts != 0u && budget != 0u));
            CHECK(redraw.pending == (accepts == 0u || budget == 0u));
        }
    }
}

static void test_retry_opportunity_is_required_after_first_attempt(void) {
    FlySimRedraw redraw;
    FlySimRedrawContext context = safe_home;
    context.retry_due = false;
    CHECK(fly_sim_redraw_init(&redraw, true, 3u));
    fly_sim_redraw_usb(&redraw, false);
    CHECK(fly_sim_redraw_step(&redraw, &context, false).attempted);
    for (unsigned step = 0u; step < 100u; ++step) {
        CHECK(!fly_sim_redraw_step(&redraw, &context, false).attempted);
    }
    CHECK(redraw.attempts == 1u && redraw.pending && !redraw.exhausted);
    context.retry_due = true;
    CHECK(fly_sim_redraw_step(&redraw, &context, false).attempted);
    CHECK(redraw.attempts == 2u);
}

static void test_reattach_cancels_and_old_epochs_cannot_acknowledge(void) {
    FlySimRedraw redraw;
    FlySimRedrawSubmission old;
    FlySimRedrawSubmission current;
    CHECK(fly_sim_redraw_init(&redraw, true, 3u));
    fly_sim_redraw_usb(&redraw, false);
    old = fly_sim_redraw_step(&redraw, &safe_home, true);
    fly_sim_redraw_usb(&redraw, false);
    CHECK(redraw.epoch == old.token.epoch && redraw.attempts == 1u);
    fly_sim_redraw_usb(&redraw, true);
    CHECK(!redraw.pending && !redraw.exhausted);
    CHECK(!fly_sim_redraw_step(&redraw, &safe_home, true).attempted);
    CHECK(!fly_sim_redraw_displayed(&redraw, old.token, FLY_SIM_VIEW_HOME));
    fly_sim_redraw_usb(&redraw, false);
    CHECK(redraw.pending && redraw.attempts == 0u);
    CHECK(redraw.epoch == old.token.epoch + 1u);
    current = fly_sim_redraw_step(&redraw, &safe_home, true);
    CHECK(!fly_sim_redraw_displayed(&redraw, old.token, FLY_SIM_VIEW_HOME));
    CHECK(fly_sim_redraw_displayed(&redraw, current.token, FLY_SIM_VIEW_HOME));
}

static void test_only_latest_accepted_request_can_acknowledge(void) {
    FlySimRedraw redraw;
    FlySimRedrawSubmission first;
    FlySimRedrawSubmission rejected;
    FlySimRedrawSubmission latest;
    CHECK(fly_sim_redraw_init(&redraw, true, 3u));
    fly_sim_redraw_usb(&redraw, false);
    first = fly_sim_redraw_step(&redraw, &safe_home, true);
    rejected = fly_sim_redraw_step(&redraw, &safe_home, false);
    CHECK(!fly_sim_redraw_displayed(&redraw, rejected.token, FLY_SIM_VIEW_HOME));
    latest = fly_sim_redraw_step(&redraw, &safe_home, true);
    CHECK(!fly_sim_redraw_displayed(&redraw, first.token, FLY_SIM_VIEW_HOME));
    ++latest.token.attempt;
    CHECK(!fly_sim_redraw_displayed(&redraw, latest.token, FLY_SIM_VIEW_HOME));
    --latest.token.attempt;
    CHECK(fly_sim_redraw_displayed(&redraw, latest.token, FLY_SIM_VIEW_HOME));
}

static void test_failed_retry_keeps_last_enqueued_acknowledgment_valid(void) {
    FlySimRedraw redraw;
    FlySimRedrawSubmission first;
    CHECK(fly_sim_redraw_init(&redraw, true, 2u));
    fly_sim_redraw_usb(&redraw, false);
    first = fly_sim_redraw_step(&redraw, &safe_home, true);
    CHECK(!fly_sim_redraw_step(&redraw, &safe_home, false).enqueued);
    CHECK(redraw.pending && redraw.exhausted);
    CHECK(fly_sim_redraw_displayed(&redraw, first.token, FLY_SIM_VIEW_HOME));
}

static void test_initial_detached_state_does_not_invent_an_epoch(void) {
    FlySimRedraw redraw;
    CHECK(fly_sim_redraw_init(&redraw, false, 3u));
    fly_sim_redraw_usb(&redraw, false);
    CHECK(!redraw.pending && redraw.epoch == 0u);
    CHECK(!fly_sim_redraw_step(&redraw, &safe_home, true).attempted);
    fly_sim_redraw_usb(&redraw, true);
    fly_sim_redraw_usb(&redraw, false);
    CHECK(redraw.pending && redraw.epoch == 1u);
}

static void test_redraw_invalid_initialization_and_epoch_overflow_fail_closed(void) {
    FlySimRedraw redraw;
    const FlySimRedrawToken token = {0u, 0u};
    CHECK(!fly_sim_redraw_init(NULL, true, 3u));
    fly_sim_redraw_usb(NULL, false);
    CHECK(!fly_sim_redraw_step(NULL, &safe_home, true).attempted);
    CHECK(!fly_sim_redraw_displayed(NULL, token, FLY_SIM_VIEW_HOME));
    CHECK(!fly_sim_redraw_init(&redraw, true,
                               FLY_SIM_REDRAW_MAX_ATTEMPTS + 1u));
    fly_sim_redraw_usb(&redraw, false);
    CHECK(!fly_sim_redraw_step(&redraw, &safe_home, true).attempted);
    CHECK(fly_sim_redraw_init(&redraw, true, 3u));
    redraw.epoch = UINT64_MAX;
    fly_sim_redraw_usb(&redraw, false);
    CHECK(redraw.epoch == UINT64_MAX && redraw.epoch_exhausted);
    CHECK(!redraw.pending);
    CHECK(!fly_sim_redraw_step(&redraw, &safe_home, true).attempted);
    fly_sim_redraw_usb(&redraw, true);
    fly_sim_redraw_usb(&redraw, false);
    CHECK(!redraw.pending && redraw.epoch == UINT64_MAX);
}

int main(void) {
    test_home_press_selects_flyos();
    test_all_owners_survive_context_transitions();
    test_malformed_events_do_not_mutate_ownership();
    test_null_snapshot_is_native_and_keys_are_independent();
    test_back_chord_affects_only_fresh_presses();
    test_null_key_state_fails_closed();
    test_detach_needs_actual_display_acknowledgment();
    test_redraw_safety_guards_and_modals_preserve_pending();
    test_queue_failure_and_missing_ack_have_bounded_retries();
    test_retry_opportunity_is_required_after_first_attempt();
    test_reattach_cancels_and_old_epochs_cannot_acknowledge();
    test_only_latest_accepted_request_can_acknowledge();
    test_failed_retry_keeps_last_enqueued_acknowledgment_valid();
    test_initial_detached_state_does_not_invent_an_epoch();
    test_redraw_invalid_initialization_and_epoch_overflow_fail_closed();
    puts("host-only input/redraw policy tests passed");
    return EXIT_SUCCESS;
}
