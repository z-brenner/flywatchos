#include "display/neural_specimen.h"

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

#define FRAMEBUFFER_BYTES 57600u

static unsigned pixel_at(const uint8_t framebuffer[FRAMEBUFFER_BYTES],
                         unsigned x, unsigned y) {
    return framebuffer[y * FLY_NEURAL_SPECIMEN_WIDTH + x];
}

static unsigned count_cell_pixels(const uint8_t framebuffer[FRAMEBUFFER_BYTES],
                                  const FlyNeuralSpecimenPoint *cell) {
    unsigned count = 0u;

    for (unsigned y = cell->y; y < cell->y + cell->height; ++y)
        for (unsigned x = cell->x; x < cell->x + cell->width; ++x)
            if (pixel_at(framebuffer, x, y) != FLY_NEURAL_SPECIMEN_BLACK) ++count;
    return count;
}

static int inside_cell(unsigned x, unsigned y, const FlyNeuralSpecimenPoint *cell) {
    return x >= cell->x && x < cell->x + cell->width &&
           y >= cell->y && y < cell->y + cell->height;
}

static void test_cells_are_distinct_non_overlapping_and_inside_safe_circle(void) {
    CHECK(FLY_NEURAL_SPECIMEN_CELLS == 64u);

    for (unsigned i = 0u; i < FLY_NEURAL_SPECIMEN_CELLS; ++i) {
        const FlyNeuralSpecimenPoint *cell = &fly_neural_specimen_points[i];

        CHECK(cell->width > 0u && cell->height > 0u);
        CHECK(cell->x + cell->width <= FLY_NEURAL_SPECIMEN_WIDTH);
        CHECK(cell->y + cell->height <= FLY_NEURAL_SPECIMEN_HEIGHT);
        for (unsigned y = cell->y; y < cell->y + cell->height; ++y) {
            for (unsigned x = cell->x; x < cell->x + cell->width; ++x) {
                int dx = (int)x - 120;
                int dy = (int)y - 120;
                CHECK(dx * dx + dy * dy <= 105 * 105);
            }
        }
        for (unsigned j = i + 1u; j < FLY_NEURAL_SPECIMEN_CELLS; ++j) {
            const FlyNeuralSpecimenPoint *other = &fly_neural_specimen_points[j];
            CHECK(cell->x + cell->width <= other->x ||
                  other->x + other->width <= cell->x ||
                  cell->y + cell->height <= other->y ||
                  other->y + other->height <= cell->y);
        }
    }
}

static void test_each_neuron_changes_only_its_corresponding_cell(void) {
    uint8_t baseline[FRAMEBUFFER_BYTES];
    uint8_t changed[FRAMEBUFFER_BYTES];
    FlyBrain64 quiet = {0};
    const FlyBrainInputs inputs = {0};
    fly_neural_specimen_render(baseline, &quiet, &inputs, 0u);

    for (unsigned neuron = 0u; neuron < FLY_NEURAL_SPECIMEN_CELLS; ++neuron) {
        FlyBrain64 active = {0};
        const FlyNeuralSpecimenPoint *cell = &fly_neural_specimen_points[neuron];

        active.activation[neuron] = 512;
        fly_neural_specimen_render(changed, &active, &inputs, 0u);
        CHECK(count_cell_pixels(changed, cell) > count_cell_pixels(baseline, cell));
        for (unsigned y = 0u; y < FLY_NEURAL_SPECIMEN_HEIGHT; ++y)
            for (unsigned x = 0u; x < FLY_NEURAL_SPECIMEN_WIDTH; ++x)
                if (!inside_cell(x, y, cell))
                    CHECK(pixel_at(baseline, x, y) == pixel_at(changed, x, y));
    }
}

static void test_activation_levels_have_increasing_cell_density(void) {
    uint8_t framebuffer[FRAMEBUFFER_BYTES];
    FlyBrain64 brain = {0};
    const FlyBrainInputs inputs = {0};
    unsigned density[4];

    brain.activation[0] = 0;
    brain.activation[1] = 128;
    brain.activation[2] = 256;
    brain.activation[3] = 512;
    fly_neural_specimen_render(framebuffer, &brain, &inputs, 0u);
    for (unsigned level = 0u; level < 4u; ++level)
        density[level] = count_cell_pixels(framebuffer, &fly_neural_specimen_points[level]);
    CHECK(density[0] < density[1]);
    CHECK(density[1] < density[2]);
    CHECK(density[2] < density[3]);
}

static void test_invalid_optional_sensors_render_as_unavailable_and_drive_nothing(void) {
    uint8_t invalid[FRAMEBUFFER_BYTES];
    uint8_t zeroed[FRAMEBUFFER_BYTES];
    FlyBrain64 brain = {0};
    const FlyBrainInputs poisoned = {
        .heart_rate_bpm = 220u,
        .heart_rate_delta = -80,
        .motion = 30000,
        .battery_percent = 100u,
        .charging = 1u
    };
    const FlyBrainInputs unavailable = {0};

    fly_neural_specimen_render(invalid, &brain, &poisoned, 0u);
    fly_neural_specimen_render(zeroed, &brain, &unavailable, 0u);
    CHECK(memcmp(invalid, zeroed, sizeof(invalid)) == 0);
    CHECK(pixel_at(invalid, 76u, 177u) != FLY_NEURAL_SPECIMEN_BLACK);
    CHECK(pixel_at(invalid, 80u, 177u) != FLY_NEURAL_SPECIMEN_BLACK);
}

static void test_physical_buttons_replace_footer_with_real_effect(void) {
    uint8_t baseline[FRAMEBUFFER_BYTES];
    uint8_t pressed[FRAMEBUFFER_BYTES];
    FlyBrain64 brain = {0};
    const FlyBrainInputs none = {0};
    static const char *labels[] = {"LIGHT > LUX GATE", "START > MOTOR BURST",
                                   "BACK > GARMIN VIEW", "DOWN > CALM FIELD",
                                   "UP > PULSE SEEK"};

    fly_neural_specimen_render(baseline, &brain, &none, 0u);
    for (unsigned button = 0u; button < 5u; ++button) {
        FlyBrainInputs input = { .buttons = (uint8_t)(1u << button) };

        fly_neural_specimen_render(pressed, &brain, &input, 0u);
        CHECK(strcmp(fly_neural_specimen_button_label((uint8_t)(1u << button)),
                     labels[button]) == 0);
        CHECK(memcmp(baseline + 210u * FLY_NEURAL_SPECIMEN_WIDTH,
                     pressed + 210u * FLY_NEURAL_SPECIMEN_WIDTH,
                     14u * FLY_NEURAL_SPECIMEN_WIDTH) != 0);
    }
}

static void test_renderer_owns_every_framebuffer_byte(void) {
    uint8_t framebuffer[FRAMEBUFFER_BYTES];
    FlyBrain64 brain = {0};
    const FlyBrainInputs inputs = {0};

    memset(framebuffer, 0xa5, sizeof(framebuffer));
    fly_neural_specimen_render(framebuffer, &brain, &inputs, 0u);
    for (unsigned index = 0u; index < sizeof(framebuffer); ++index)
        CHECK(framebuffer[index] == 0x00u || framebuffer[index] == 0xffu);
}
static void test_noop_gate_preserves_entire_incoming_frame(void) {
    uint8_t framebuffer[FRAMEBUFFER_BYTES]; FlyBrain64 brain = {0}; FlyBrainInputs inputs = {0};
    for (unsigned i=0u;i<FRAMEBUFFER_BYTES;++i) framebuffer[i]=(uint8_t)(i*37u);
    uint8_t before[FRAMEBUFFER_BYTES]; memcpy(before,framebuffer,sizeof(before));
    fly_neural_specimen_render_if_home(framebuffer,0u,&brain,&inputs,0u);
    CHECK(memcmp(before,framebuffer,sizeof(before))==0);
    CHECK(strcmp(fly_neural_specimen_unavailable_label(0u),"HR --")==0);
    CHECK(strcmp(fly_neural_specimen_unavailable_label(1u),"MOTION --")==0);
    CHECK(strcmp(fly_neural_specimen_unavailable_label(2u),"B --")==0);
}

static void test_whole_rendered_frame_is_inside_the_circular_safe_area(void) {
    uint8_t framebuffer[FRAMEBUFFER_BYTES];
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

    brain.state = FLY_BRAIN64_STATE_AROUSAL;
    fly_neural_specimen_render(framebuffer, &brain, &inputs, 63u);
    for (unsigned y = 0u; y < FLY_NEURAL_SPECIMEN_HEIGHT; ++y)
        for (unsigned x = 0u; x < FLY_NEURAL_SPECIMEN_WIDTH; ++x)
            if (pixel_at(framebuffer, x, y) != FLY_NEURAL_SPECIMEN_BLACK) {
                int dx = (int)x - 120;
                int dy = (int)y - 120;
                CHECK(dx * dx + dy * dy <= 114 * 114);
            }
}

int main(void) {
    test_cells_are_distinct_non_overlapping_and_inside_safe_circle();
    test_each_neuron_changes_only_its_corresponding_cell();
    test_activation_levels_have_increasing_cell_density();
    test_invalid_optional_sensors_render_as_unavailable_and_drive_nothing();
    test_physical_buttons_replace_footer_with_real_effect();
    test_renderer_owns_every_framebuffer_byte();
    test_noop_gate_preserves_entire_incoming_frame();
    test_whole_rendered_frame_is_inside_the_circular_safe_area();
    puts("neural specimen tests: ok");
    return EXIT_SUCCESS;
}
