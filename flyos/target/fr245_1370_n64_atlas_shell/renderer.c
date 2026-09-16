#include "renderer.h"

#include "display/n64_atlas_layout.h"

#define W 240u
#define H 240u

/* Reviewed RGB222 bytes: scaffold gray, white text, green, magenta, amber. */
#define GRAY 0x2au
#define WHITE 0x3fu
#define GREEN 0x0cu
#define MAGENTA 0x33u
#define AMBER 0x38u

/* Physical key order: LIGHT, START, BACK, DOWN, UP. */
static const char keys[5][6] = {"LIGHT", "START", "BACK", "DOWN", "UP"};
static const char effects[5][6] = {"LUX", "MOTOR", "MODE", "CALM", "PULSE"};
static const char states[4][7] = {"REST", "MOVE", "AROUSE", "QUIET"};
/* Glyph count of "<key> // <effect>", plus " BURST" for START. */
static const uint8_t press_width[5] = {12u, 20u, 12u, 12u, 11u};

/*
 * The one and only framebuffer store in this payload.  It is kept out of line
 * and behind an optimisation barrier so the bound check compiles to a real
 * branch rather than a Thumb IT block: a single unconditional store is what
 * makes "this payload writes nowhere but the framebuffer" auditable straight
 * out of the disassembly, and it is what linker.ld pins into .primary.
 */
__attribute__((noinline))
static void pixel(uint8_t *fb, unsigned x, unsigned y, uint8_t color) {
    if (x >= W || y >= H) return;
    __asm__ volatile ("");
    fb[y * W + x] = color;
}

/* Draws one label fragment and returns the pen position after it. */
static unsigned text(uint8_t *fb, unsigned x, unsigned y, const char *s) {
    for (; *s != '\0'; ++s, x += FLY_N64_ATLAS_GLYPH_PITCH) {
        uint16_t bits = fly_n64_atlas_glyph(*s);
        for (unsigned row = 0u; row < 5u; ++row)
            for (unsigned column = 0u; column < 3u; ++column)
                if ((bits >> (row * 3u + column) & 1u) != 0u)
                    pixel(fb, x + 2u - column, y + row, WHITE);
    }
    return x;
}

static void centred(uint8_t *fb, unsigned y, const char *s) {
    unsigned chars = 0u;

    while (s[chars] != '\0') ++chars;
    (void)text(fb, fly_n64_atlas_centre(chars), y, s);
}

/* "<KEY> // <EFFECT>" on the footer line, widened to MOTOR BURST for START. */
static void press_label(uint8_t *fb, unsigned key) {
    unsigned x = fly_n64_atlas_centre(press_width[key]);

    x = text(fb, x, FLY_N64_ATLAS_FOOTER_Y, keys[key]);
    x = text(fb, x, FLY_N64_ATLAS_FOOTER_Y, " // ");
    x = text(fb, x, FLY_N64_ATLAS_FOOTER_Y, effects[key]);
    if (key == 1u) (void)text(fb, x, FLY_N64_ATLAS_FOOTER_Y, " BURST");
}

/* Walks the shared scaffold display list; every direction advances right/down. */
static void scaffold(uint8_t *fb) {
    for (unsigned index = 0u; index < FLY_N64_ATLAS_STROKES; ++index) {
        const uint8_t *stroke = fly_n64_atlas_stroke[index];
        int x = stroke[0];
        int y = stroke[1];

        for (unsigned step = 0u; step < stroke[3]; ++step) {
            pixel(fb, (unsigned)x, (unsigned)y, GRAY);
            x += fly_n64_atlas_step[0][stroke[2]];
            y += fly_n64_atlas_step[1][stroke[2]];
        }
    }
}

static void cell(uint8_t *fb, unsigned neuron, int16_t activation) {
    FlyN64AtlasPoint point = fly_n64_atlas_point(neuron);
    uint8_t level = fly_n64_atlas_level(activation);
    uint8_t color = activation < 0 ? MAGENTA :
        (level == 3u &&
         fly_n64_atlas_population(neuron) == FLY_N64_POPULATION_ACTION_FAN) ?
            AMBER : GREEN;

    for (unsigned row = 0u; row < FLY_N64_ATLAS_MASK; ++row)
        for (unsigned column = 0u; column < FLY_N64_ATLAS_MASK; ++column)
            if ((fly_n64_atlas_density[level][row] >> column & 1u) != 0u)
                pixel(fb, point.x + column, point.y + row, color);
}

void n64_render(uint8_t *fb, const FlyBrain64 *brain, const FlyBrainInputs *in,
                uint32_t tick, uint8_t ui_flags) {
    /* The atlas is a fixed anatomy; nothing on it is driven by the clock.
     * FLY_UI_USB is wired through but has no presentation of its own yet. */
    (void)tick;
    for (unsigned i = 0u; i < W * H; ++i) fb[i] = 0u;
    scaffold(fb);
    centred(fb, FLY_N64_ATLAS_TITLE_Y, "FLYOS // N64");
    for (unsigned neuron = 0u; neuron < FLY_N64_ATLAS_NEURONS; ++neuron)
        cell(fb, neuron, brain->activation[neuron]);
    centred(fb, FLY_N64_ATLAS_STATE_Y, states[brain->state < 4u ? brain->state : 0u]);
    if ((ui_flags & FLY_UI_SYSTEM) != 0u) {
        centred(fb, FLY_N64_ATLAS_FOOTER_Y, "GARMIN//SYSTEM");
        return;
    }
    if ((ui_flags & FLY_UI_CHORD_ARMED) != 0u) {
        centred(fb, FLY_N64_ATLAS_FOOTER_Y, "SYSTEM//HOLD");
        return;
    }
    for (unsigned key = 0u; key < 5u; ++key)
        if ((in->buttons >> key & 1u) != 0u) {
            press_label(fb, key);
            return;
        }
    for (unsigned key = 0u; key < 5u; ++key)
        (void)text(fb, fly_n64_atlas_callout[key][0], fly_n64_atlas_callout[key][1],
                   effects[key]);
}
