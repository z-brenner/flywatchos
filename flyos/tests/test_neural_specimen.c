#include "display/n64_atlas_layout.h"
#include "display/neural_specimen.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* The target's packed Brain64 is linked beside the shared one with its public
 * symbols renamed (see flyos/CMakeLists.txt) so both can be driven side by
 * side from one process. */
void packed_brain64_reconstruct(FlyBrain64 *brain, uint32_t identity_seed,
                                uint32_t rtc_tick, const FlyBrainInputs *inputs);

#define CHECK(condition)                                                        \
    do {                                                                        \
        if (!(condition)) {                                                     \
            fprintf(stderr, "check failed: %s (%s:%d)\n", #condition,         \
                    __FILE__, __LINE__);                                        \
            exit(EXIT_FAILURE);                                                 \
        }                                                                       \
    } while (0)

#define FRAMEBUFFER_BYTES 57600u

static uint8_t framebuffer_a[FRAMEBUFFER_BYTES];
static uint8_t framebuffer_b[FRAMEBUFFER_BYTES];
static uint8_t occupancy[FRAMEBUFFER_BYTES];

static unsigned pixel_at(const uint8_t framebuffer[FRAMEBUFFER_BYTES],
                         unsigned x, unsigned y) {
    return framebuffer[y * FLY_NEURAL_SPECIMEN_WIDTH + x];
}

static int inside_radius(unsigned x, unsigned y) {
    int dx = (int)x - FLY_N64_ATLAS_CENTER;
    int dy = (int)y - FLY_N64_ATLAS_CENTER;

    return dx * dx + dy * dy <= FLY_N64_ATLAS_RADIUS * FLY_N64_ATLAS_RADIUS;
}

static unsigned count_mask_pixels(const uint8_t framebuffer[FRAMEBUFFER_BYTES],
                                  FlyN64AtlasPoint point) {
    unsigned count = 0u;

    for (unsigned y = point.y; y < point.y + FLY_N64_ATLAS_MASK; ++y)
        for (unsigned x = point.x; x < point.x + FLY_N64_ATLAS_MASK; ++x)
            if (pixel_at(framebuffer, x, y) != FLY_NEURAL_SPECIMEN_BLACK) ++count;
    return count;
}

static int inside_mask(unsigned x, unsigned y, FlyN64AtlasPoint point) {
    return x >= point.x && x < point.x + FLY_N64_ATLAS_MASK &&
           y >= point.y && y < point.y + FLY_N64_ATLAS_MASK;
}

/* Every neuron owns a 5x5 mask, no two masks share a pixel, and no mask pixel
 * leaves the 98-pixel safe circle.  This is the brief's occupancy sweep. */
static void test_atlas_masks_are_disjoint_and_inside_the_safe_circle(void) {
    CHECK(FLY_N64_ATLAS_NEURONS == 64u);
    CHECK(FLY_NEURAL_SPECIMEN_CELLS == FLY_N64_ATLAS_NEURONS);
    memset(occupancy, 0, sizeof(occupancy));
    for (unsigned neuron = 0u; neuron < FLY_N64_ATLAS_NEURONS; ++neuron) {
        FlyN64AtlasPoint point = fly_n64_atlas_point(neuron);

        CHECK(inside_radius(point.x, point.y));
        for (unsigned y = point.y; y < point.y + FLY_N64_ATLAS_MASK; ++y)
            for (unsigned x = point.x; x < point.x + FLY_N64_ATLAS_MASK; ++x) {
                CHECK(inside_radius(x, y));
                CHECK(occupancy[y * FLY_NEURAL_SPECIMEN_WIDTH + x]++ == 0u);
            }
    }
}

/* The six populations own exactly the id ranges the atlas contract names. */
static void test_atlas_populations_cover_every_neuron_exactly(void) {
    static const struct { unsigned first, last; uint8_t population; } ranges[] = {
        { 0u, 11u, FLY_N64_POPULATION_SENSORY_RIM },
        {12u, 23u, FLY_N64_POPULATION_CENTRAL_RING },
        {24u, 39u, FLY_N64_POPULATION_MUSHROOM_BODY },
        {40u, 47u, FLY_N64_POPULATION_MODULATORY },
        {48u, 55u, FLY_N64_POPULATION_IDENTITY },
        {56u, 63u, FLY_N64_POPULATION_ACTION_FAN }
    };
    unsigned covered = 0u;

    for (unsigned range = 0u; range < 6u; ++range) {
        CHECK(ranges[range].first == covered);
        for (unsigned neuron = ranges[range].first; neuron <= ranges[range].last; ++neuron)
            CHECK(fly_n64_atlas_population(neuron) == ranges[range].population);
        covered = ranges[range].last + 1u;
    }
    CHECK(covered == FLY_N64_ATLAS_NEURONS);
    CHECK(fly_n64_atlas_population(0u) != fly_n64_atlas_population(12u));
}

/* Magnitude is communicated by density alone: 1, 9, 16 and 25 lit pixels. */
static void test_activation_levels_light_exactly_1_9_16_and_25_pixels(void) {
    static const int16_t activations[4] = {0, 128, 256, 512};
    static const unsigned densities[4] = {1u, 9u, 16u, 25u};

    for (unsigned level = 0u; level < 4u; ++level) {
        FlyBrain64 brain = {0};
        const FlyBrainInputs inputs = {0};

        CHECK(fly_n64_atlas_density_pixels(level) == densities[level]);
        for (unsigned neuron = 0u; neuron < FLY_N64_ATLAS_NEURONS; ++neuron)
            brain.activation[neuron] = activations[level];
        fly_neural_specimen_render(framebuffer_a, &brain, &inputs, 0u);
        for (unsigned neuron = 0u; neuron < FLY_N64_ATLAS_NEURONS; ++neuron)
            CHECK(count_mask_pixels(framebuffer_a, fly_n64_atlas_point(neuron)) ==
                  densities[level]);
    }
}

/* The scaffold, tracts and callouts must not reach inside any neuron mask: at
 * level 0 exactly the mask centre is lit, so any intruding stroke shows up. */
static void test_static_scaffold_never_intrudes_into_a_neuron_mask(void) {
    FlyBrain64 brain = {0};
    const FlyBrainInputs inputs = { .buttons = FLY_BRAIN64_BUTTON_START };

    fly_neural_specimen_render(framebuffer_a, &brain, &inputs, 0u);
    for (unsigned neuron = 0u; neuron < FLY_N64_ATLAS_NEURONS; ++neuron) {
        FlyN64AtlasPoint point = fly_n64_atlas_point(neuron);

        CHECK(count_mask_pixels(framebuffer_a, point) == 1u);
        CHECK(pixel_at(framebuffer_a, point.x + 2u, point.y + 2u) !=
              FLY_NEURAL_SPECIMEN_BLACK);
    }
}

static void test_each_neuron_changes_only_its_own_mask(void) {
    FlyBrain64 quiet = {0};
    const FlyBrainInputs inputs = {0};

    fly_neural_specimen_render(framebuffer_a, &quiet, &inputs, 0u);
    for (unsigned neuron = 0u; neuron < FLY_N64_ATLAS_NEURONS; ++neuron) {
        FlyBrain64 active = {0};
        FlyN64AtlasPoint point = fly_n64_atlas_point(neuron);

        active.activation[neuron] = 512;
        fly_neural_specimen_render(framebuffer_b, &active, &inputs, 0u);
        CHECK(count_mask_pixels(framebuffer_b, point) >
              count_mask_pixels(framebuffer_a, point));
        for (unsigned y = 0u; y < FLY_NEURAL_SPECIMEN_HEIGHT; ++y)
            for (unsigned x = 0u; x < FLY_NEURAL_SPECIMEN_WIDTH; ++x)
                if (!inside_mask(x, y, point))
                    CHECK(pixel_at(framebuffer_a, x, y) == pixel_at(framebuffer_b, x, y));
    }
}

static void test_invalid_optional_inputs_contribute_exactly_zero(void) {
    FlyBrain64 brain = {0};
    const FlyBrainInputs poisoned = {
        .heart_rate_bpm = 220u,
        .heart_rate_delta = -80,
        .motion = 30000,
        .battery_percent = 100u,
        .charging = 1u
    };
    const FlyBrainInputs unavailable = {0};

    fly_neural_specimen_render(framebuffer_a, &brain, &poisoned, 0u);
    fly_neural_specimen_render(framebuffer_b, &brain, &unavailable, 0u);
    CHECK(memcmp(framebuffer_a, framebuffer_b, FRAMEBUFFER_BYTES) == 0);
}

static void test_every_physical_button_names_its_own_effect(void) {
    static const char *labels[] = {"LIGHT // LUX", "START // MOTOR BURST",
                                   "BACK // MODE", "DOWN // CALM", "UP // PULSE"};
    FlyBrain64 brain = {0};
    const FlyBrainInputs none = {0};

    CHECK(fly_neural_specimen_button_label(0u)[0] == '\0');
    fly_neural_specimen_render(framebuffer_a, &brain, &none, 0u);
    for (unsigned button = 0u; button < 5u; ++button) {
        FlyBrainInputs input = { .buttons = (uint8_t)(1u << button) };

        CHECK(strcmp(fly_neural_specimen_button_label((uint8_t)(1u << button)),
                     labels[button]) == 0);
        fly_neural_specimen_render(framebuffer_b, &brain, &input, 0u);
        CHECK(memcmp(framebuffer_a, framebuffer_b, FRAMEBUFFER_BYTES) != 0);
    }
}

static void test_every_state_renders_its_full_name(void) {
    static const char *names[] = {"REST", "MOVE", "AROUSE", "QUIET"};

    for (unsigned state = 0u; state < 4u; ++state)
        CHECK(strcmp(fly_neural_specimen_state_label((uint8_t)state), names[state]) == 0);
    CHECK(strcmp(fly_neural_specimen_state_label(9u), names[0]) == 0);
}

static void test_renderer_owns_every_framebuffer_byte(void) {
    FlyBrain64 brain = {0};
    const FlyBrainInputs inputs = {0};

    memset(framebuffer_a, 0xa5, FRAMEBUFFER_BYTES);
    fly_neural_specimen_render(framebuffer_a, &brain, &inputs, 0u);
    for (unsigned index = 0u; index < FRAMEBUFFER_BYTES; ++index)
        CHECK(framebuffer_a[index] == 0x00u || framebuffer_a[index] == 0xffu);
}

static void test_noop_gate_preserves_entire_incoming_frame(void) {
    FlyBrain64 brain = {0};
    const FlyBrainInputs inputs = {0};

    for (unsigned i = 0u; i < FRAMEBUFFER_BYTES; ++i)
        framebuffer_a[i] = (uint8_t)(i * 37u);
    memcpy(framebuffer_b, framebuffer_a, FRAMEBUFFER_BYTES);
    fly_neural_specimen_render_if_home(framebuffer_a, 0u, &brain, &inputs, 0u);
    CHECK(memcmp(framebuffer_b, framebuffer_a, FRAMEBUFFER_BYTES) == 0);
}

static void test_whole_rendered_frame_is_inside_the_safe_circle(void) {
    FlyBrain64 brain = {0};
    const FlyBrainInputs inputs = {
        .buttons = FLY_BRAIN64_BUTTON_START,
        .valid_mask = FLY_BRAIN64_VALID_HEART_RATE | FLY_BRAIN64_VALID_MOTION |
                      FLY_BRAIN64_VALID_BATTERY | FLY_BRAIN64_VALID_CHARGING,
        .heart_rate_bpm = 255u,
        .motion = -32768,
        .battery_percent = 100u,
        .charging = 1u
    };

    for (unsigned state = 0u; state < 4u; ++state) {
        brain.state = (uint8_t)state;
        for (unsigned neuron = 0u; neuron < FLY_N64_ATLAS_NEURONS; ++neuron)
            brain.activation[neuron] = (int16_t)(neuron % 2u ? -512 : 512);
        fly_neural_specimen_render(framebuffer_a, &brain, &inputs, 63u);
        for (unsigned y = 0u; y < FLY_NEURAL_SPECIMEN_HEIGHT; ++y)
            for (unsigned x = 0u; x < FLY_NEURAL_SPECIMEN_WIDTH; ++x)
                if (pixel_at(framebuffer_a, x, y) != FLY_NEURAL_SPECIMEN_BLACK)
                    CHECK(inside_radius(x, y));
    }
}

/* 32 button masks x 3 optional-input profiles x 49 RTC ticks = 4,704 fixtures;
 * every one must leave the shared and the target-packed Brain64 byte-identical
 * across all 140 struct bytes (658,560 compared bytes). */
static void test_shared_and_packed_brain64_agree_over_every_fixture(void) {
    static const uint8_t profiles[3] = {
        0u,
        FLY_BRAIN64_VALID_BATTERY,
        FLY_BRAIN64_VALID_HEART_RATE | FLY_BRAIN64_VALID_MOTION |
            FLY_BRAIN64_VALID_BATTERY | FLY_BRAIN64_VALID_CHARGING
    };
    unsigned long fixtures = 0ul;
    unsigned long compared = 0ul;

    for (unsigned buttons = 0u; buttons < 32u; ++buttons)
        for (unsigned profile = 0u; profile < 3u; ++profile)
            for (unsigned step = 0u; step < 49u; ++step) {
                FlyBrain64 shared;
                FlyBrain64 packed;
                FlyBrainInputs inputs;
                uint32_t tick = (uint32_t)step * 8191u + (uint32_t)buttons * 131071u +
                                (uint32_t)profile * 7u;

                memset(&shared, 0, sizeof(shared));
                memset(&packed, 0, sizeof(packed));
                memset(&inputs, 0, sizeof(inputs));
                inputs.buttons = (uint8_t)buttons;
                inputs.valid_mask = profiles[profile];
                inputs.heart_rate_bpm = (uint16_t)(40u + step * 3u);
                inputs.heart_rate_delta = (int16_t)((int)step - 24);
                inputs.motion = (int16_t)((int)step * 601 - 15000);
                inputs.battery_percent = (uint8_t)(step * 2u);
                inputs.charging = (uint8_t)(step & 1u);
                fly_brain64_reconstruct(&shared, 0x46594f53u, tick, &inputs);
                packed_brain64_reconstruct(&packed, 0x46594f53u, tick, &inputs);
                CHECK(memcmp(&shared, &packed, sizeof(shared)) == 0);
                ++fixtures;
                compared += sizeof(shared);
            }
    CHECK(fixtures == 4704ul);
    CHECK(compared == 658560ul);
}

int main(void) {
    test_atlas_masks_are_disjoint_and_inside_the_safe_circle();
    test_atlas_populations_cover_every_neuron_exactly();
    test_activation_levels_light_exactly_1_9_16_and_25_pixels();
    test_static_scaffold_never_intrudes_into_a_neuron_mask();
    test_each_neuron_changes_only_its_own_mask();
    test_invalid_optional_inputs_contribute_exactly_zero();
    test_every_physical_button_names_its_own_effect();
    test_every_state_renders_its_full_name();
    test_renderer_owns_every_framebuffer_byte();
    test_noop_gate_preserves_entire_incoming_frame();
    test_whole_rendered_frame_is_inside_the_safe_circle();
    test_shared_and_packed_brain64_agree_over_every_fixture();
    puts("neural specimen tests: ok");
    return EXIT_SUCCESS;
}
