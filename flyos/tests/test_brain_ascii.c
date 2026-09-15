#include "display/brain_ascii.h"

#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define CHECK(condition)                                                        \
    do {                                                                        \
        if (!(condition)) {                                                     \
            fprintf(stderr, "check failed: %s (%s:%d)\n", #condition,            \
                    __FILE__, __LINE__);                                        \
            exit(EXIT_FAILURE);                                                 \
        }                                                                       \
    } while (0)

enum { WIDTH = 240, PIXELS = 57600, GUARD = 64 };
static struct {
    uint8_t before[GUARD];
    uint8_t pixels[PIXELS];
    uint8_t after[GUARD];
} guarded;
static uint8_t baseline[PIXELS];

static void render_checked(const FlyBrain32 *brain, uint32_t tick, uint8_t buttons) {
    memset(guarded.before, 0x69, GUARD);
    memset(guarded.after, 0x96, GUARD);
    memset(guarded.pixels, 0xa5, PIXELS);
    fly_brain_ascii_render(guarded.pixels, brain, tick, buttons);
    for (unsigned i = 0; i < GUARD; ++i) {
        CHECK(guarded.before[i] == 0x69);
        CHECK(guarded.after[i] == 0x96);
    }
    for (unsigned i = 0; i < PIXELS; ++i)
        CHECK(guarded.pixels[i] == 0x00 || guarded.pixels[i] == 0xff);
}

static uint64_t cell_pattern(const uint8_t *pixels, FlyBrainPoint p) {
    uint64_t bits = 0;
    for (unsigned y = 0; y < 7; ++y)
        for (unsigned x = 0; x < 5; ++x)
            if (pixels[(p.y + y) * WIDTH + p.x + x] == 0)
                bits |= UINT64_C(1) << (y * 5 + x);
    return bits;
}

static unsigned ink_count(uint64_t pattern) {
    unsigned count = 0;
    for (; pattern; pattern >>= 1) count += (unsigned)(pattern & 1u);
    return count;
}

/* Catch duplicate/overlapping neuron cells, missing clears, stray writes,
 * incorrect neuron indexing, collapsed glyph levels and unthresholded pulses. */
int main(void) {
    FlyBrain32 brain = {0};
    const int16_t values[] = {0, 128, 256, 512};
    for (unsigned i = 0; i < 32; ++i) {
        FlyBrainPoint p = fly_brain_points[i];
        CHECK(p.x + 8 < WIDTH && p.y + 6 < WIDTH);
        for (unsigned j = 0; j < i; ++j) {
            FlyBrainPoint q = fly_brain_points[j];
            CHECK(p.x != q.x || p.y != q.y);
            CHECK(p.x + 8 < q.x || q.x + 8 < p.x ||
                   p.y + 6 < q.y || q.y + 6 < p.y);
        }
    }
    render_checked(&brain, 0x12345678u, 0);
    memcpy(baseline, guarded.pixels, PIXELS);
    CHECK(guarded.pixels[0] == 0xff);
    for (unsigned i = 0; i < 32; ++i) {
        FlyBrainPoint p = fly_brain_points[i];
        uint64_t patterns[4];
        for (unsigned level = 0; level < 4; ++level) {
            brain.activation[i] = values[level];
            render_checked(&brain, 0x12345678u, 0);
            patterns[level] = cell_pattern(guarded.pixels, p);
            for (unsigned prior = 0; prior < level; ++prior)
                CHECK(patterns[prior] != patterns[level]);
            if (level) CHECK(ink_count(patterns[level]) > ink_count(patterns[level - 1]));
            for (unsigned pos = 0; pos < PIXELS; ++pos) {
                if (baseline[pos] != guarded.pixels[pos]) {
                    unsigned x = pos % WIDTH, y = pos / WIDTH;
                    int own_cell = x >= p.x && x < p.x + 5u &&
                                   y >= p.y && y < p.y + 7u;
                    int pulse = y == p.y + 3u &&
                                (x == p.x + 7u || x == p.x + 8u);
                    CHECK(own_cell || pulse);
                }
            }
            for (unsigned dx = 7; dx <= 8; ++dx)
                CHECK(guarded.pixels[(p.y + 3u) * WIDTH + p.x + dx] ==
                       (level >= 2 ? 0x00 : 0xff));
            brain.activation[i] = (int16_t)-values[level];
            render_checked(&brain, 0x12345678u, 0);
            CHECK(cell_pattern(guarded.pixels, p) == patterns[level]);
        }
        brain.activation[i] = 0;
    }
    /* Literal boundary fixtures ensure glyph selection follows absolute Q5.10. */
    const int16_t edges[] = {127, 128, 255, 256, 511, 512, -16384};
    const unsigned levels[] = {0, 1, 1, 2, 2, 3, 3};
    uint64_t reference[4];
    for (unsigned level = 0; level < 4; ++level) {
        brain.activation[0] = values[level];
        render_checked(&brain, UINT32_MAX, 31);
        reference[level] = cell_pattern(guarded.pixels, fly_brain_points[0]);
    }
    for (unsigned e = 0; e < sizeof(edges) / sizeof(edges[0]); ++e) {
        brain.activation[0] = edges[e];
        render_checked(&brain, UINT32_MAX, 31);
        CHECK(cell_pattern(guarded.pixels, fly_brain_points[0]) == reference[levels[e]]);
    }
    for (unsigned buttons = 0; buttons < 32; ++buttons)
        render_checked(&brain, buttons, (uint8_t)buttons);
    puts("brain_ascii: 32 unique cells, four signed levels, pulse locality, full clear and canaries PASS");
    return 0;
}
