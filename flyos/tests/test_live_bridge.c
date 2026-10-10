#include "sim/live_bridge.h"
#include "sim/host_policy.h"
#include "display/neural_specimen.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition); \
    exit(1); } } while (0)

static uint8_t expected_pixels[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES];

static void equal_brain(const FlyBrain64 *expected) {
    CHECK(fly_lab_neuron_count() == FLY_BRAIN64_NEURONS);
    CHECK(memcmp(fly_lab_activations(), expected->activation,
                 sizeof(expected->activation)) == 0);
    CHECK(fly_lab_state() == expected->state);
    CHECK(fly_lab_epoch() == expected->epoch);
}

static void test_reset_matches_portable_core(void) {
    static const uint32_t seeds[] = {0u, 1u, 0x245f1a5u, UINT32_MAX};
    FlyBrain64 expected;
    FlyBrainInputs inputs = {0};
    for (unsigned i = 0u; i < sizeof(seeds) / sizeof(seeds[0]); ++i) {
        fly_lab_reset(seeds[i]);
        fly_brain64_seed(&expected, seeds[i], 0u);
        equal_brain(&expected);
        CHECK(fly_lab_pixel_count() == sizeof(expected_pixels));
        fly_neural_specimen_render(expected_pixels, &expected, &inputs, 0u);
        CHECK(memcmp(fly_lab_pixels(), expected_pixels, sizeof(expected_pixels)) == 0);
        CHECK(fly_lab_route() == -1);
        CHECK(fly_lab_held() == 0u && fly_lab_active() == 0u);
        CHECK(fly_lab_pulse() == 0u && fly_lab_delivered_pulse() == 0u);
        CHECK(fly_lab_buttons() == 0u && fly_lab_valid_mask() == 0u);
        CHECK(fly_lab_view() == FLY_SIM_VIEW_HOME);
        CHECK(fly_lab_usb() == 0u && fly_lab_ready() == 1u);
        CHECK(fly_lab_rendered() == 1u);
        for (int key = 0; key < 5; ++key) CHECK(fly_lab_owner(key) == 0);
    }
}

static void test_pulse_survives_native_and_usb_once(void) {
    FlyBrain64 expected;
    FlyBrainInputs inputs = {0};
    const uint32_t start = FLY_BRAIN64_BUTTON_START;
    fly_lab_reset(123u);
    fly_brain64_seed(&expected, 123u, 0u);
    CHECK(fly_lab_event(FLY_SIM_KEY_START, FLY_SIM_PRESS) == FLY_SIM_ROUTE_FLYOS);
    CHECK(fly_lab_held() == start && fly_lab_active() == start);
    CHECK(fly_lab_set_context(FLY_SIM_VIEW_NATIVE, 0, 1) == 1);
    CHECK(fly_lab_event(FLY_SIM_KEY_START, FLY_SIM_REPEAT) == FLY_SIM_ROUTE_FLYOS);
    CHECK(fly_lab_event(FLY_SIM_KEY_START, FLY_SIM_RELEASE) == FLY_SIM_ROUTE_FLYOS);
    CHECK(fly_lab_pulse() == start && fly_lab_held() == 0u);
    memcpy(expected_pixels, fly_lab_pixels(), sizeof(expected_pixels));
    for (unsigned step = 0u; step < 4u; ++step) {
        fly_lab_step();
        fly_brain64_step(&expected, &inputs);
        equal_brain(&expected);
        CHECK(fly_lab_pulse() == start && fly_lab_delivered_pulse() == 0u);
        CHECK(fly_lab_buttons() == 0u && fly_lab_rendered() == 0u);
        CHECK(memcmp(fly_lab_pixels(), expected_pixels, sizeof(expected_pixels)) == 0);
    }
    CHECK(fly_lab_set_context(FLY_SIM_VIEW_HOME, 1, 1) == 1);
    fly_lab_step();
    fly_brain64_step(&expected, &inputs);
    equal_brain(&expected);
    CHECK(fly_lab_pulse() == start && fly_lab_buttons() == 0u);
    CHECK(memcmp(fly_lab_pixels(), expected_pixels, sizeof(expected_pixels)) == 0);
    CHECK(fly_lab_set_context(FLY_SIM_VIEW_HOME, 0, 1) == 1);
    inputs.buttons = (uint8_t)start;
    fly_lab_step();
    fly_brain64_step(&expected, &inputs);
    equal_brain(&expected);
    fly_neural_specimen_render(expected_pixels, &expected, &inputs, 5u);
    CHECK(memcmp(fly_lab_pixels(), expected_pixels, sizeof(expected_pixels)) == 0);
    CHECK(fly_lab_pulse() == 0u && fly_lab_delivered_pulse() == start);
    CHECK(fly_lab_buttons() == start && fly_lab_rendered() == 1u);
    CHECK(fly_lab_route() == FLY_SIM_ROUTE_FLYOS);
    inputs.buttons = 0u;
    fly_lab_step();
    fly_brain64_step(&expected, &inputs);
    equal_brain(&expected);
    CHECK(fly_lab_buttons() == 0u && fly_lab_delivered_pulse() == 0u);
}

static void test_native_keys_and_whole_sequence(void) {
    fly_lab_reset(77u);
    CHECK(fly_lab_event(FLY_SIM_KEY_LIGHT, FLY_SIM_PRESS) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_lab_event(FLY_SIM_KEY_LIGHT, FLY_SIM_REPEAT) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_lab_event(FLY_SIM_KEY_LIGHT, FLY_SIM_RELEASE) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_lab_event(FLY_SIM_KEY_BACK, FLY_SIM_PRESS) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_lab_event(FLY_SIM_KEY_START, FLY_SIM_PRESS) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_lab_event(FLY_SIM_KEY_BACK, FLY_SIM_RELEASE) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_lab_event(FLY_SIM_KEY_START, FLY_SIM_REPEAT) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_lab_event(FLY_SIM_KEY_START, FLY_SIM_RELEASE) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_lab_pulse() == 0u && fly_lab_held() == 0u);
    CHECK(fly_lab_set_context(FLY_SIM_VIEW_NATIVE, 0, 1) == 1);
    CHECK(fly_lab_event(FLY_SIM_KEY_DOWN, FLY_SIM_PRESS) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_lab_set_context(FLY_SIM_VIEW_HOME, 0, 1) == 1);
    CHECK(fly_lab_event(FLY_SIM_KEY_DOWN, FLY_SIM_RELEASE) == FLY_SIM_ROUTE_GARMIN);
    CHECK(fly_lab_event(FLY_SIM_KEY_UP, FLY_SIM_PRESS) == FLY_SIM_ROUTE_FLYOS);
    CHECK(fly_lab_set_context(FLY_SIM_VIEW_INVALID, 0, 0) == 1);
    fly_lab_step();
    CHECK(fly_lab_buttons() == FLY_BRAIN64_BUTTON_UP);
    CHECK(fly_lab_held() == FLY_BRAIN64_BUTTON_UP && fly_lab_rendered() == 0u);
    CHECK(fly_lab_event(FLY_SIM_KEY_UP, FLY_SIM_RELEASE) == FLY_SIM_ROUTE_FLYOS);
    CHECK(fly_lab_pulse() == FLY_BRAIN64_BUTTON_UP);
    CHECK(fly_lab_set_context(FLY_SIM_VIEW_HOME, 0, 0) == 1);
    CHECK(fly_lab_event(FLY_SIM_KEY_START, FLY_SIM_PRESS) == FLY_SIM_ROUTE_GARMIN);
}

static void test_rejected_arguments_do_not_mutate(void) {
    static const int bad_contexts[][3] = {
        {-1,0,1},{3,0,1},{INT_MAX,0,1},{1,-1,1},{1,2,1},{1,0,-1},{1,0,2}};
    static const int bad_sensors[][6] = {
        {-1,0,0,0,0,0},{16,0,0,0,0,0},{15,-1,0,0,0,0},
        {15,301,0,0,0,0},{15,0,-301,0,0,0},{15,0,301,0,0,0},
        {15,0,0,-32769,0,0},{15,0,0,32768,0,0},
        {15,0,0,0,-1,0},{15,0,0,0,101,0},{15,0,0,0,0,-1},
        {15,0,0,0,0,2},{0,INT_MAX,0,0,0,0},{0,0,INT_MIN,0,0,0}};
    FlyBrain64 expected;
    FlyBrainInputs inputs = {0};
    fly_lab_reset(17u);
    fly_brain64_seed(&expected, 17u, 0u);
    CHECK(fly_lab_set_sensors(15, 150, -12, 10000, 84, 1) == 1);
    inputs.valid_mask = 15u;
    inputs.heart_rate_bpm = 150u;
    inputs.heart_rate_delta = -12;
    inputs.motion = 10000;
    inputs.battery_percent = 84u;
    inputs.charging = 1u;
    CHECK(fly_lab_event(FLY_SIM_KEY_START, FLY_SIM_PRESS) == FLY_SIM_ROUTE_FLYOS);
    inputs.buttons = FLY_BRAIN64_BUTTON_START;
    CHECK(fly_lab_event(FLY_SIM_KEY_START, FLY_SIM_PRESS) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_lab_event(-1, 0) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_lab_event(5, 0) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_lab_event(INT_MAX, INT_MIN) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_lab_event(1, -1) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_lab_event(1, 3) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_lab_event(3, 2) == FLY_SIM_ROUTE_REJECTED);
    CHECK(fly_lab_held() == 2u && fly_lab_active() == 2u);
    CHECK(fly_lab_owner(1) == 2 && fly_lab_owner(-1) == 0 && fly_lab_owner(5) == 0);
    for (unsigned i = 0; i < sizeof(bad_contexts)/sizeof(bad_contexts[0]); ++i) {
        const int *v = bad_contexts[i];
        CHECK(fly_lab_set_context(v[0], v[1], v[2]) == 0);
        CHECK(fly_lab_view() == 1u && fly_lab_usb() == 0u && fly_lab_ready() == 1u);
    }
    for (unsigned i = 0; i < sizeof(bad_sensors)/sizeof(bad_sensors[0]); ++i) {
        const int *v = bad_sensors[i];
        CHECK(fly_lab_set_sensors(v[0],v[1],v[2],v[3],v[4],v[5]) == 0);
        CHECK(fly_lab_valid_mask() == 15u);
        fly_lab_step();
        fly_brain64_step(&expected, &inputs);
        equal_brain(&expected);
    }
}

static void test_optional_sensor_limits_and_clear(void) {
    FlyBrain64 expected;
    FlyBrainInputs inputs = {0};
    fly_lab_reset(42u);
    fly_brain64_seed(&expected, 42u, 0u);
    CHECK(fly_lab_set_sensors(15,300,-300,-32768,100,1) == 1);
    inputs.valid_mask = 15u;
    inputs.heart_rate_bpm = 300u;
    inputs.heart_rate_delta = -300;
    inputs.motion = -32768;
    inputs.battery_percent = 100u;
    inputs.charging = 1u;
    for (unsigned i = 0u; i < 40u; ++i) {
        fly_lab_step();
        fly_brain64_step(&expected, &inputs);
        equal_brain(&expected);
    }
    CHECK(fly_lab_set_sensors(15,0,300,32767,0,0) == 1);
    inputs.heart_rate_bpm = 0;
    inputs.heart_rate_delta = 300;
    inputs.motion = 32767;
    inputs.battery_percent = 0;
    inputs.charging = 0;
    fly_lab_step();
    fly_brain64_step(&expected, &inputs);
    equal_brain(&expected);
    CHECK(fly_lab_set_sensors(0,300,300,32767,100,1) == 1);
    memset(&inputs, 0, sizeof(inputs));
    fly_lab_step();
    fly_brain64_step(&expected, &inputs);
    equal_brain(&expected);
    CHECK(fly_lab_valid_mask() == 0u);
    fly_neural_specimen_render(expected_pixels, &expected, &inputs, 41u);
    CHECK(memcmp(fly_lab_pixels(), expected_pixels, sizeof(expected_pixels)) == 0);
    fly_lab_reset(42u);
    CHECK(fly_lab_held() == 0u && fly_lab_valid_mask() == 0u && fly_lab_epoch() == 0u);
}

int main(void) {
    test_reset_matches_portable_core();
    test_pulse_survives_native_and_usb_once();
    test_native_keys_and_whole_sequence();
    test_rejected_arguments_do_not_mutate();
    test_optional_sensor_limits_and_clear();
    puts("live bridge: portable core, ownership, pulses, validation, sensor limits passed");
    return 0;
}
