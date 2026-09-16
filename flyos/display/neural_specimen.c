#include "display/neural_specimen.h"

#include <string.h>

/* Effect names, in physical key order, doubling as the idle callouts. */
static const char *const fly_neural_specimen_effects[5] = {
    "LUX", "MOTOR", "MODE", "CALM", "PULSE"
};

const char *fly_neural_specimen_button_label(uint8_t buttons) {
    static const char *const labels[5] = {
        "LIGHT // LUX", "START // MOTOR BURST", "BACK // MODE",
        "DOWN // CALM", "UP // PULSE"
    };

    for (unsigned key = 0u; key < 5u; ++key)
        if ((buttons & (uint8_t)(1u << key)) != 0u) return labels[key];
    return "";
}

const char *fly_neural_specimen_state_label(uint8_t state) {
    static const char *const names[4] = {"REST", "MOVE", "AROUSE", "QUIET"};

    return names[state < 4u ? state : 0u];
}

static void fly_neural_specimen_pixel(uint8_t framebuffer[], unsigned x,
                                      unsigned y, uint8_t role) {
    if (x < FLY_NEURAL_SPECIMEN_WIDTH && y < FLY_NEURAL_SPECIMEN_HEIGHT)
        framebuffer[y * FLY_NEURAL_SPECIMEN_WIDTH + x] = role;
}

static void fly_neural_specimen_text(uint8_t framebuffer[], unsigned x,
                                     unsigned y, const char *text, uint8_t role) {
    for (; *text != '\0'; ++text, x += FLY_N64_ATLAS_GLYPH_PITCH) {
        uint16_t bits = fly_n64_atlas_glyph(*text);

        for (unsigned row = 0u; row < 5u; ++row)
            for (unsigned column = 0u; column < 3u; ++column)
                if ((bits >> (row * 3u + column) & 1u) != 0u)
                    fly_neural_specimen_pixel(framebuffer, x + 2u - column,
                                              y + row, role);
    }
}

static void fly_neural_specimen_centred(uint8_t framebuffer[], unsigned y,
                                        const char *text, uint8_t role) {
    fly_neural_specimen_text(framebuffer, fly_n64_atlas_centre((unsigned)strlen(text)),
                             y, text, role);
}

/* Walks the shared scaffold display list; every stroke advances right/down. */
static void fly_neural_specimen_scaffold(uint8_t framebuffer[]) {
    for (unsigned stroke = 0u; stroke < FLY_N64_ATLAS_STROKES; ++stroke) {
        const uint8_t *entry = fly_n64_atlas_stroke[stroke];
        int x = entry[0];
        int y = entry[1];

        for (unsigned step = 0u; step < entry[3]; ++step) {
            fly_neural_specimen_pixel(framebuffer, (unsigned)x, (unsigned)y,
                                      FLY_NEURAL_SPECIMEN_SCAFFOLD);
            x += fly_n64_atlas_step[0][entry[2]];
            y += fly_n64_atlas_step[1][entry[2]];
        }
    }
}

static void fly_neural_specimen_cell(uint8_t framebuffer[], unsigned neuron,
                                     int16_t activation) {
    FlyN64AtlasPoint point = fly_n64_atlas_point(neuron);
    uint8_t level = fly_n64_atlas_level(activation);
    uint8_t role = activation < 0 ? FLY_NEURAL_SPECIMEN_INHIBITORY :
        (level == 3u &&
         fly_n64_atlas_population(neuron) == FLY_N64_POPULATION_ACTION_FAN) ?
            FLY_NEURAL_SPECIMEN_SATURATED : FLY_NEURAL_SPECIMEN_EXCITATORY;

    for (unsigned row = 0u; row < FLY_N64_ATLAS_MASK; ++row)
        for (unsigned column = 0u; column < FLY_N64_ATLAS_MASK; ++column)
            if ((fly_n64_atlas_density[level][row] >> column & 1u) != 0u)
                fly_neural_specimen_pixel(framebuffer, point.x + column,
                                          point.y + row, role);
}

void fly_neural_specimen_render_if_home(
    uint8_t framebuffer[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES], uint8_t home_gate,
    const FlyBrain64 *brain, const FlyBrainInputs *inputs, uint32_t rtc_tick) {
    if (home_gate != 0u) fly_neural_specimen_render(framebuffer, brain, inputs, rtc_tick);
}

void fly_neural_specimen_render(
    uint8_t framebuffer[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES],
    const FlyBrain64 *brain, const FlyBrainInputs *inputs, uint32_t rtc_tick) {
    const char *pressed = fly_neural_specimen_button_label(inputs->buttons);

    /* The atlas is a static anatomy: nothing on it is driven by the clock. */
    (void)rtc_tick;
    memset(framebuffer, FLY_NEURAL_SPECIMEN_BLACK,
           FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES);
    fly_neural_specimen_scaffold(framebuffer);
    fly_neural_specimen_centred(framebuffer, FLY_N64_ATLAS_TITLE_Y, "FLYOS // N64",
                                FLY_NEURAL_SPECIMEN_TEXT);
    for (unsigned neuron = 0u; neuron < FLY_N64_ATLAS_NEURONS; ++neuron)
        fly_neural_specimen_cell(framebuffer, neuron, brain->activation[neuron]);
    fly_neural_specimen_centred(framebuffer, FLY_N64_ATLAS_STATE_Y,
                                fly_neural_specimen_state_label(brain->state),
                                FLY_NEURAL_SPECIMEN_TEXT);
    if (pressed[0] != '\0') {
        fly_neural_specimen_centred(framebuffer, FLY_N64_ATLAS_FOOTER_Y, pressed,
                                    FLY_NEURAL_SPECIMEN_TEXT);
        return;
    }
    for (unsigned key = 0u; key < 5u; ++key)
        fly_neural_specimen_text(framebuffer, fly_n64_atlas_callout[key][0],
                                 fly_n64_atlas_callout[key][1],
                                 fly_neural_specimen_effects[key],
                                 FLY_NEURAL_SPECIMEN_TEXT);
}
