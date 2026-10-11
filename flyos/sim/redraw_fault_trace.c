/* Public synthetic fault scenarios. No firmware, queue API or hardware I/O. */
#include "sim/host_policy.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

static FlySimRedraw redraw;
static unsigned step_count;
static FlySimRoute route;
static const FlySimRedrawContext safe = {
    FLY_SIM_VIEW_HOME, false, true, false, false, true
};

static const char *boolean(bool value) { return value ? "true" : "false"; }

static void begin_case(const char *name, bool attached, unsigned budget, bool first) {
    if (!fly_sim_redraw_init(&redraw, attached, budget)) exit(EXIT_FAILURE);
    step_count = 0u;
    route = FLY_SIM_ROUTE_REJECTED;
    printf("%s{\"name\":\"%s\",\"steps\":[", first ? "" : ",", name);
}

static void snapshot(const char *operation, FlySimRedrawSubmission submission,
                     bool acknowledged) {
    printf("%s{\"op\":\"%s\",\"route\":%u,\"epoch\":%" PRIu64
           ",\"attempts\":%u,\"pending\":%s,\"exhausted\":%s,"
           "\"attempted\":%s,\"enqueued\":%s,\"acknowledged\":%s}",
           step_count++ == 0u ? "" : ",", operation, (unsigned)route,
           redraw.epoch, redraw.attempts, boolean(redraw.pending),
           boolean(redraw.exhausted), boolean(submission.attempted),
           boolean(submission.enqueued), boolean(acknowledged));
}

static void mark(const char *operation) {
    const FlySimRedrawSubmission none = {0};
    snapshot(operation, none, false);
}

static void button(const char *operation, FlySimInputContext context) {
    FlySimKeys keys;
    fly_sim_keys_init(&keys);
    route = fly_sim_key_event(&keys, FLY_SIM_KEY_DOWN, FLY_SIM_PRESS, &context);
    (void)fly_sim_redraw_button(&redraw, route);
    mark(operation);
}

static FlySimRedrawSubmission attempt(const char *operation,
                                     FlySimRedrawContext context, bool accepts) {
    FlySimRedrawSubmission result = fly_sim_redraw_step(&redraw, &context, accepts);
    snapshot(operation, result, false);
    return result;
}

static void display(const char *operation, FlySimRedrawToken token) {
    const FlySimRedrawSubmission none = {0};
    const bool acknowledged = fly_sim_redraw_displayed(&redraw, token,
                                                       FLY_SIM_VIEW_HOME);
    snapshot(operation, none, acknowledged);
}

int main(void) {
    const FlySimInputContext home = {FLY_SIM_VIEW_HOME, false, true};
    const FlySimInputContext native = {FLY_SIM_VIEW_NATIVE, false, true};
    FlySimRedrawSubmission old, fresh;
    FlySimRedrawContext guarded;
    puts("{\"schema\":1,\"scope\":\"host-only proposed controller\","
         "\"target_modified\":false,\"hardware_verified\":false,\"scenarios\":[");
    begin_case("owned_button_queue_reject_then_display", false, 3u, true);
    button("owned_press", home);
    (void)attempt("queue_reject", safe, false);
    fresh = attempt("queue_accept", safe, true);
    display("home_display", fresh.token);
    printf("]}");

    begin_case("native_press_has_no_flyos_work", false, 3u, false);
    button("native_press", native);
    (void)attempt("no_dirty_work", safe, true);
    printf("]}");

    begin_case("newer_input_invalidates_old_display", false, 3u, false);
    button("owned_press", home);
    old = attempt("old_queue_accept", safe, true);
    button("new_input", home);
    display("old_home_display", old.token);
    fresh = attempt("new_queue_accept", safe, true);
    display("new_home_display", fresh.token);
    printf("]}");

    begin_case("usb_return_requires_eligible_callback", true, 3u, false);
    fly_sim_redraw_usb(&redraw, false);
    mark("detach");
    guarded = safe; guarded.usb_mass_storage = true;
    (void)attempt("cached_usb_active", guarded, true);
    guarded = safe; guarded.view = FLY_SIM_VIEW_NATIVE;
    (void)attempt("native_view", guarded, true);
    guarded = safe; guarded.safe_callback = false;
    (void)attempt("no_safe_callback", guarded, true);
    fresh = attempt("eligible_callback", safe, true);
    display("home_display", fresh.token);
    printf("]}");

    for (unsigned accept = 0u; accept < 2u; ++accept) {
        begin_case(accept ? "acceptance_without_display_is_bounded" :
                           "permanent_rejection_is_bounded", false, 2u, false);
        button("owned_press", home);
        (void)attempt("attempt_one", safe, accept != 0u);
        (void)attempt("attempt_two", safe, accept != 0u);
        button("new_input_does_not_refill", home);
        (void)attempt("budget_exhausted", safe, accept != 0u);
        printf("]}");
    }
    puts("]}");
    return ferror(stdout) ? EXIT_FAILURE : EXIT_SUCCESS;
}
