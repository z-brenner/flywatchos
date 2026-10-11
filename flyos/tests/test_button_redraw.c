#include "sim/host_policy.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(c) do { if (!(c)) { \
    fprintf(stderr, "check failed: %s (%s:%d)\n", #c, __FILE__, __LINE__); \
    exit(EXIT_FAILURE); } } while (0)

static const FlySimInputContext ready = { FLY_SIM_VIEW_HOME, false, true };
static const FlySimRedrawContext safe = {
    FLY_SIM_VIEW_HOME, false, true, false, false, true
};

static void test_owned_button_rejection_remains_pending_until_display(void) {
    FlySimKeys keys;
    FlySimRedraw redraw;
    FlySimRedrawSubmission rejected, accepted;
    fly_sim_keys_init(&keys);
    CHECK(fly_sim_redraw_init(&redraw, false, 3u));
    CHECK(fly_sim_redraw_button(&redraw,
        fly_sim_key_event(&keys, FLY_SIM_KEY_DOWN, FLY_SIM_PRESS, &ready)));
    CHECK(redraw.pending && redraw.epoch == 1u);
    rejected = fly_sim_redraw_step(&redraw, &safe, false);
    CHECK(rejected.attempted && !rejected.enqueued && rejected.nonblocking);
    CHECK(redraw.pending && redraw.attempts == 1u);
    CHECK(!fly_sim_redraw_displayed(&redraw, rejected.token, FLY_SIM_VIEW_HOME));
    accepted = fly_sim_redraw_step(&redraw, &safe, true);
    CHECK(accepted.enqueued && redraw.pending);
    CHECK(fly_sim_redraw_displayed(&redraw, accepted.token, FLY_SIM_VIEW_HOME));
    CHECK(!redraw.pending);
}

static void test_new_input_invalidates_old_display_without_refilling_budget(void) {
    FlySimRedraw redraw;
    FlySimRedrawSubmission old, fresh;
    CHECK(fly_sim_redraw_init(&redraw, false, 3u));
    CHECK(fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
    old = fly_sim_redraw_step(&redraw, &safe, true);
    CHECK(fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
    CHECK(redraw.attempts == 1u && redraw.epoch == old.token.epoch + 1u);
    CHECK(!fly_sim_redraw_displayed(&redraw, old.token, FLY_SIM_VIEW_HOME));
    CHECK(!fly_sim_redraw_step(&redraw, &safe, false).enqueued);
    CHECK(!fly_sim_redraw_displayed(&redraw, old.token, FLY_SIM_VIEW_HOME));
    fresh = fly_sim_redraw_step(&redraw, &safe, true);
    CHECK(redraw.exhausted && redraw.pending);
    CHECK(fly_sim_redraw_displayed(&redraw, fresh.token, FLY_SIM_VIEW_HOME));
    CHECK(fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
    CHECK(redraw.attempts == 0u && !redraw.exhausted && redraw.pending);
    CHECK(!fly_sim_redraw_displayed(&redraw, fresh.token, FLY_SIM_VIEW_HOME));
}

static void test_bursts_never_refill_an_unfinished_work_budget(void) {
    for (unsigned budget = 0u; budget <= FLY_SIM_REDRAW_MAX_ATTEMPTS; ++budget) {
        for (unsigned accept = 0u; accept < 2u; ++accept) {
            FlySimRedraw redraw;
            CHECK(fly_sim_redraw_init(&redraw, false, budget));
            for (unsigned event = 0u; event < 1000u; ++event) {
                FlySimRedrawSubmission submission;
                CHECK(fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
                submission = fly_sim_redraw_step(&redraw, &safe, accept != 0u);
                CHECK(submission.attempted == (event < budget));
                CHECK(submission.enqueued == (event < budget && accept != 0u));
                CHECK(redraw.pending);
                CHECK(redraw.attempts == (event < budget ? event + 1u : budget));
            }
            CHECK(redraw.exhausted && redraw.pending);
        }
    }
}

static void test_only_flyos_owned_events_create_dirty_work(void) {
    for (unsigned key = 0u; key < FLY_SIM_KEY_COUNT; ++key) {
        for (unsigned context = 0u; context < 8u; ++context) {
            FlySimInputContext input = { (context & 1u) ? FLY_SIM_VIEW_NATIVE :
                FLY_SIM_VIEW_HOME, (context & 2u) != 0u, (context & 4u) == 0u };
            FlySimKeys keys;
            FlySimRedraw redraw, before;
            FlySimRoute route;
            fly_sim_keys_init(&keys);
            CHECK(fly_sim_redraw_init(&redraw, false, 3u));
            before = redraw;
            route = fly_sim_key_event(&keys, key, FLY_SIM_PRESS, &input);
            CHECK(fly_sim_redraw_button(&redraw, route) ==
                  (route == FLY_SIM_ROUTE_FLYOS));
            if (route != FLY_SIM_ROUTE_FLYOS)
                CHECK(memcmp(&before, &redraw, sizeof(redraw)) == 0);
        }
    }
    {
        FlySimRedraw redraw, before;
        CHECK(fly_sim_redraw_init(&redraw, false, 3u));
        before = redraw;
        CHECK(!fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_REJECTED));
        CHECK(!fly_sim_redraw_button(&redraw, (FlySimRoute)99));
        CHECK(memcmp(&before, &redraw, sizeof(redraw)) == 0);
        CHECK(!fly_sim_redraw_button(NULL, FLY_SIM_ROUTE_FLYOS));
    }
}

static void test_usb_and_modal_guards_survive_button_requests(void) {
    FlySimRedraw redraw, before;
    FlySimRedrawContext context = safe;
    FlySimRedrawSubmission old, fresh;
    CHECK(fly_sim_redraw_init(&redraw, false, 3u));
    CHECK(fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
    old = fly_sim_redraw_step(&redraw, &safe, true);
    fly_sim_redraw_usb(&redraw, true);
    before = redraw;
    CHECK(!fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
    CHECK(memcmp(&before, &redraw, sizeof(redraw)) == 0);
    CHECK(!fly_sim_redraw_displayed(&redraw, old.token, FLY_SIM_VIEW_HOME));
    fly_sim_redraw_usb(&redraw, false);
    CHECK(fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
    context.view = FLY_SIM_VIEW_NATIVE;
    for (unsigned i = 0u; i < 100u; ++i)
        CHECK(!fly_sim_redraw_step(&redraw, &context, true).attempted);
    context = safe;
    context.usb_mass_storage = true;
    CHECK(!fly_sim_redraw_step(&redraw, &context, true).attempted);
    CHECK(redraw.pending && redraw.attempts == 0u);
    fresh = fly_sim_redraw_step(&redraw, &safe, true);
    CHECK(fresh.enqueued);
    CHECK(!fly_sim_redraw_displayed(&redraw, old.token, FLY_SIM_VIEW_HOME));
    CHECK(fly_sim_redraw_displayed(&redraw, fresh.token, FLY_SIM_VIEW_HOME));
}

static void test_new_input_cannot_bypass_retry_opportunity_or_safety_guards(void) {
    FlySimRedraw redraw;
    FlySimRedrawContext context = safe;
    CHECK(fly_sim_redraw_init(&redraw, false, 3u));
    CHECK(fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
    CHECK(fly_sim_redraw_step(&redraw, &safe, false).attempted);
    context.retry_due = false;
    for (unsigned i = 0u; i < 100u; ++i) {
        CHECK(fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
        CHECK(!fly_sim_redraw_step(&redraw, &context, true).attempted);
    }
    CHECK(redraw.attempts == 1u);
    for (unsigned mask = 1u; mask < 16u; ++mask) {
        context = safe;
        context.safe_callback = (mask & 1u) == 0u;
        context.source_mutex_locked = (mask & 2u) != 0u;
        context.usb_mutex_locked = (mask & 4u) != 0u;
        context.view = (mask & 8u) != 0u ? FLY_SIM_VIEW_INVALID : FLY_SIM_VIEW_HOME;
        CHECK(fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
        CHECK(!fly_sim_redraw_step(&redraw, &context, true).attempted);
    }
    CHECK(redraw.attempts == 1u && redraw.pending);
}

static void test_generation_overflow_fails_closed(void) {
    FlySimRedraw redraw;
    FlySimRedrawSubmission old;
    CHECK(fly_sim_redraw_init(&redraw, false, 3u));
    redraw.epoch = UINT64_MAX - 1u;
    CHECK(fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
    old = fly_sim_redraw_step(&redraw, &safe, true);
    CHECK(old.token.epoch == UINT64_MAX);
    CHECK(!fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
    CHECK(redraw.epoch == UINT64_MAX && redraw.epoch_exhausted);
    CHECK(!fly_sim_redraw_step(&redraw, &safe, true).attempted);
    CHECK(!fly_sim_redraw_displayed(&redraw, old.token, FLY_SIM_VIEW_HOME));
    CHECK(!fly_sim_redraw_button(&redraw, FLY_SIM_ROUTE_FLYOS));
}

int main(void) {
    test_owned_button_rejection_remains_pending_until_display();
    test_new_input_invalidates_old_display_without_refilling_budget();
    test_bursts_never_refill_an_unfinished_work_budget();
    test_only_flyos_owned_events_create_dirty_work();
    test_usb_and_modal_guards_survive_button_requests();
    test_new_input_cannot_bypass_retry_opportunity_or_safety_guards();
    test_generation_overflow_fails_closed();
    puts("host-only button/redraw rejection tests passed");
    return EXIT_SUCCESS;
}
