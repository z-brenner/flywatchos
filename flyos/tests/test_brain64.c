#include "fly/brain64.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(condition)                                                        \
    do {                                                                        \
        if (!(condition)) {                                                     \
            fprintf(stderr, "check failed: %s (%s:%d)\n", #condition,         \
                    __FILE__, __LINE__);                                        \
            exit(EXIT_FAILURE);                                                 \
        }                                                                       \
    } while (0)

static void test_model_contains_exactly_64_activations(void) {
    FlyBrain64 brain = {0};

    CHECK(FLY_BRAIN64_NEURONS == 64u);
    CHECK(sizeof(brain.activation) / sizeof(brain.activation[0]) == 64u);
}

static void test_reconstruction_is_deterministic(void) {
    FlyBrain64 first;
    FlyBrain64 second;
    const FlyBrainInputs inputs = {
        .buttons = FLY_BRAIN64_BUTTON_LIGHT | FLY_BRAIN64_BUTTON_DOWN,
        .valid_mask = FLY_BRAIN64_VALID_HEART_RATE | FLY_BRAIN64_VALID_MOTION |
                      FLY_BRAIN64_VALID_BATTERY | FLY_BRAIN64_VALID_CHARGING,
        .heart_rate_bpm = 72,
        .heart_rate_delta = -3,
        .motion = 240,
        .battery_percent = 87,
        .charging = 1u
    };

    fly_brain64_reconstruct(&first, 0x12345678u, 0x0000abcdu, &inputs);
    fly_brain64_reconstruct(&second, 0x12345678u, 0x0000abcdu, &inputs);
    CHECK(memcmp(&first, &second, sizeof(first)) == 0);
}

static void test_glyph_levels_follow_activation_magnitude(void) {
    FlyBrain64 brain = {0};

    brain.activation[0] = 127;
    brain.activation[1] = -128;
    brain.activation[2] = 256;
    brain.activation[3] = -512;
    CHECK(fly_brain64_level(&brain, 0u) == FLY_BRAIN64_LEVEL_DOT);
    CHECK(fly_brain64_level(&brain, 1u) == FLY_BRAIN64_LEVEL_SMALL_O);
    CHECK(fly_brain64_level(&brain, 2u) == FLY_BRAIN64_LEVEL_LARGE_O);
    CHECK(fly_brain64_level(&brain, 3u) == FLY_BRAIN64_LEVEL_AT);
    CHECK(fly_brain64_level(&brain, FLY_BRAIN64_NEURONS) ==
          FLY_BRAIN64_LEVEL_DOT);
}

static void test_rtc_phase_drives_circadian_neuron(void) {
    FlyBrain64 day;
    FlyBrain64 night;
    const FlyBrainInputs inputs = {0};

    fly_brain64_seed(&day, 0x31415926u, 16u);
    fly_brain64_seed(&night, 0x31415926u, 48u);
    memset(day.activation, 0, sizeof(day.activation));
    memset(night.activation, 0, sizeof(night.activation));
    day.rng_state = 0x6d2b79f5u;
    night.rng_state = day.rng_state;
    fly_brain64_step(&day, &inputs);
    fly_brain64_step(&night, &inputs);
    CHECK(day.activation[5] > 0);
    CHECK(night.activation[5] < 0);
}

static void test_every_button_drives_its_sensory_neuron(void) {
    const FlyBrainInputs none = {0};

    for (unsigned button = 0u; button < 5u; ++button) {
        FlyBrain64 idle;
        FlyBrain64 pressed;
        FlyBrainInputs inputs = none;

        inputs.buttons = (uint8_t)(1u << button);
        fly_brain64_seed(&idle, 0x5a5a5a5au, 9u);
        pressed = idle;
        fly_brain64_step(&idle, &none);
        fly_brain64_step(&pressed, &inputs);
        CHECK(pressed.activation[button] > idle.activation[button]);
        for (unsigned peer = 0u; peer < 5u; ++peer) {
            if (peer != button) {
                CHECK(pressed.activation[peer] == idle.activation[peer]);
            }
        }
    }
}

static void test_each_validity_bit_gates_only_its_optional_population(void) {
    static const uint8_t valid_bits[] = {
        FLY_BRAIN64_VALID_HEART_RATE,
        FLY_BRAIN64_VALID_MOTION,
        FLY_BRAIN64_VALID_BATTERY,
        FLY_BRAIN64_VALID_CHARGING
    };
    const FlyBrainInputs poisoned = {
        .heart_rate_bpm = 220,
        .heart_rate_delta = -80,
        .motion = 30000,
        .battery_percent = 100u,
        .charging = 1u
    };

    for (unsigned index = 0u;
         index < sizeof(valid_bits) / sizeof(valid_bits[0]);
         ++index) {
        FlyBrain64 baseline;
        FlyBrain64 sensed;
        FlyBrainInputs zeroed = { .valid_mask = valid_bits[index] };
        FlyBrainInputs selected = poisoned;

        selected.valid_mask = valid_bits[index];
        fly_brain64_seed(&baseline, 0x1badb002u, 23u);
        sensed = baseline;
        fly_brain64_step(&baseline, &zeroed);
        fly_brain64_step(&sensed, &selected);
        if (valid_bits[index] == FLY_BRAIN64_VALID_HEART_RATE) {
            CHECK(baseline.activation[8] != sensed.activation[8]);
            CHECK(baseline.activation[9] != sensed.activation[9]);
            CHECK(baseline.activation[6] == sensed.activation[6]);
            CHECK(baseline.activation[7] == sensed.activation[7]);
            CHECK(baseline.activation[10] == sensed.activation[10]);
            CHECK(baseline.activation[11] == sensed.activation[11]);
        } else if (valid_bits[index] == FLY_BRAIN64_VALID_MOTION) {
            CHECK(baseline.activation[10] != sensed.activation[10]);
            CHECK(baseline.activation[11] != sensed.activation[11]);
            CHECK(baseline.activation[6] == sensed.activation[6]);
            CHECK(baseline.activation[7] == sensed.activation[7]);
            CHECK(baseline.activation[8] == sensed.activation[8]);
            CHECK(baseline.activation[9] == sensed.activation[9]);
        } else if (valid_bits[index] == FLY_BRAIN64_VALID_BATTERY) {
            CHECK(baseline.activation[7] != sensed.activation[7]);
            CHECK(baseline.activation[6] == sensed.activation[6]);
            CHECK(baseline.activation[8] == sensed.activation[8]);
            CHECK(baseline.activation[9] == sensed.activation[9]);
            CHECK(baseline.activation[10] == sensed.activation[10]);
            CHECK(baseline.activation[11] == sensed.activation[11]);
        } else {
            CHECK(baseline.activation[6] != sensed.activation[6]);
            CHECK(baseline.activation[7] == sensed.activation[7]);
            CHECK(baseline.activation[8] == sensed.activation[8]);
            CHECK(baseline.activation[9] == sensed.activation[9]);
            CHECK(baseline.activation[10] == sensed.activation[10]);
            CHECK(baseline.activation[11] == sensed.activation[11]);
        }
    }
}

static void test_clamp_reaches_exact_saturation_boundaries(void) {
    FlyBrain64 positive;
    FlyBrain64 negative;
    const FlyBrainInputs positive_inputs = {
        .valid_mask = FLY_BRAIN64_VALID_HEART_RATE,
        .heart_rate_delta = INT16_MAX
    };
    const FlyBrainInputs negative_inputs = {
        .valid_mask = FLY_BRAIN64_VALID_HEART_RATE,
        .heart_rate_delta = INT16_MIN
    };

    fly_brain64_seed(&positive, 0x55667788u, 0u);
    negative = positive;
    positive.activation[9] = 0;
    negative.activation[9] = 0;
    fly_brain64_step(&positive, &positive_inputs);
    fly_brain64_step(&negative, &negative_inputs);
    CHECK(positive.activation[9] == 16383);
    CHECK(negative.activation[9] == -16384);
}

static void test_clamp_invariants(void) {
    FlyBrain64 brain;
    FlyBrainInputs inputs = {
        .buttons = 0x1fu,
        .valid_mask = FLY_BRAIN64_VALID_HEART_RATE | FLY_BRAIN64_VALID_MOTION |
                      FLY_BRAIN64_VALID_BATTERY | FLY_BRAIN64_VALID_CHARGING,
        .heart_rate_bpm = 255,
        .heart_rate_delta = 127,
        .motion = 32767,
        .battery_percent = 100u,
        .charging = 1u
    };

    fly_brain64_seed(&brain, 0xfeedc0deu, 0u);
    for (unsigned step = 0u; step < 10000u; ++step) {
        inputs.buttons = (uint8_t)((step >> 2) & 0x1fu);
        fly_brain64_step(&brain, &inputs);
        for (unsigned neuron = 0u; neuron < FLY_BRAIN64_NEURONS; ++neuron) {
            CHECK(brain.activation[neuron] >= -16384);
            CHECK(brain.activation[neuron] <= 16383);
        }
    }
}

int main(void) {
    test_model_contains_exactly_64_activations();
    test_reconstruction_is_deterministic();
    test_glyph_levels_follow_activation_magnitude();
    test_rtc_phase_drives_circadian_neuron();
    test_every_button_drives_its_sensory_neuron();
    test_each_validity_bit_gates_only_its_optional_population();
    test_clamp_reaches_exact_saturation_boundaries();
    test_clamp_invariants();
    puts("brain64 tests: ok");
    return EXIT_SUCCESS;
}
