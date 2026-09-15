#include "fly/brain32.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(condition)                                                        \
    do {                                                                        \
        if (!(condition)) {                                                     \
            fprintf(stderr, "check failed: %s (%s:%d)\\n", #condition,       \
                    __FILE__, __LINE__);                                        \
            exit(EXIT_FAILURE);                                                 \
        }                                                                       \
    } while (0)

static void test_reconstruction_is_deterministic(void) {
    FlyBrain32 first;
    FlyBrain32 second;
    const uint8_t input = FLY_BRAIN_INPUT_LIGHT | FLY_BRAIN_INPUT_DOWN;

    fly_brain32_reconstruct(&first, 0x12345678u, 0x0000abcdu, input);
    fly_brain32_reconstruct(&second, 0x12345678u, 0x0000abcdu, input);
    CHECK(memcmp(&first, &second, sizeof(first)) == 0);
}

static void test_adjacent_epochs_evolve(void) {
    FlyBrain32 first;
    FlyBrain32 second;

    fly_brain32_seed(&first, 0x31415926u, 41u);
    fly_brain32_seed(&second, 0x31415926u, 42u);
    CHECK(memcmp(first.activation, second.activation, sizeof(first.activation)) != 0);
    CHECK(first.epoch == 41u);
    fly_brain32_step(&first, 0u);
    CHECK(first.epoch == 42u);
}

static void test_glyph_levels(void) {
    FlyBrain32 brain = {0};

    brain.activation[0] = 127;
    brain.activation[1] = -128;
    brain.activation[2] = 256;
    brain.activation[3] = -512;
    CHECK(fly_brain32_level(&brain, 0u) == FLY_BRAIN_LEVEL_DOT);
    CHECK(fly_brain32_level(&brain, 1u) == FLY_BRAIN_LEVEL_SMALL_O);
    CHECK(fly_brain32_level(&brain, 2u) == FLY_BRAIN_LEVEL_LARGE_O);
    CHECK(fly_brain32_level(&brain, 3u) == FLY_BRAIN_LEVEL_AT);
    CHECK(fly_brain32_level(&brain, FLY_BRAIN_NEURONS) == FLY_BRAIN_LEVEL_DOT);
}

static void test_every_button_drives_its_sensory_neuron(void) {
    for (unsigned button = 0u; button < 5u; ++button) {
        FlyBrain32 idle;
        FlyBrain32 pressed;
        uint8_t mask = (uint8_t)(1u << button);

        fly_brain32_seed(&idle, 0x5a5a5a5au, 9u);
        pressed = idle;
        fly_brain32_step(&idle, 0u);
        fly_brain32_step(&pressed, mask);
        CHECK(pressed.activation[button] > idle.activation[button]);
    }
}

static void test_clamp_invariants(void) {
    FlyBrain32 brain;

    fly_brain32_seed(&brain, 0xfeedc0deu, 0u);
    for (unsigned step = 0u; step < 10000u; ++step) {
        uint8_t input = (uint8_t)((step >> 2) & 0x1fu);
        fly_brain32_step(&brain, input);
        for (unsigned neuron = 0u; neuron < FLY_BRAIN_NEURONS; ++neuron) {
            CHECK(brain.activation[neuron] >= -16384);
            CHECK(brain.activation[neuron] <= 16383);
        }
    }
}

int main(void) {
    test_reconstruction_is_deterministic();
    test_adjacent_epochs_evolve();
    test_glyph_levels();
    test_every_button_drives_its_sensory_neuron();
    test_clamp_invariants();
    puts("brain32 tests: ok");
    return EXIT_SUCCESS;
}
