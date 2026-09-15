#include "fly/network.h"
#include "display/garmin_row_packer.h"

#include <stdint.h>

#define WIDTH 240u
#define HEIGHT 240u

/* RAM-only buffers. No physical display transport is claimed. */
static uint8_t framebuffer[HEIGHT][WIDTH];
static volatile uint8_t packed_probe_row[FLY_DISPLAY_STAGING_ROW_BYTES];
static FlyNetwork fly;

static void pixel(unsigned x, unsigned y, uint8_t color) {
    if (x < WIDTH && y < HEIGHT) framebuffer[y][x] = color;
}

static const uint8_t *glyph(char character) {
    static const uint8_t blank[7] = {0u};
    static const uint8_t f[7] = {31u,16u,16u,30u,16u,16u,16u};
    static const uint8_t l[7] = {16u,16u,16u,16u,16u,16u,31u};
    static const uint8_t y[7] = {17u,17u,10u,4u,4u,4u,4u};
    static const uint8_t i[7] = {14u,4u,4u,4u,4u,4u,14u};
    static const uint8_t v[7] = {17u,17u,17u,17u,17u,10u,4u};
    static const uint8_t e[7] = {31u,16u,16u,30u,16u,16u,31u};
    static const uint8_t s[7] = {15u,16u,16u,14u,1u,1u,30u};
    switch (character) {
        case 'F': return f;
        case 'L': return l;
        case 'Y': return y;
        case 'I': return i;
        case 'V': return v;
        case 'E': return e;
        case 'S': return s;
        default: return blank;
    }
}

static void draw_text(unsigned x, unsigned y, const char *text, uint8_t color,
                      unsigned scale) {
    while (*text != '\0') {
        const uint8_t *rows = glyph(*text++);
        for (unsigned row = 0; row < 7u; ++row) {
            for (unsigned column = 0; column < 5u; ++column) {
                if ((rows[row] & (1u << (4u - column))) == 0u) continue;
                for (unsigned dy = 0; dy < scale; ++dy)
                    for (unsigned dx = 0; dx < scale; ++dx)
                        pixel(x + column * scale + dx, y + row * scale + dy, color);
            }
        }
        x += 6u * scale;
    }
}

static void render_fly(uint16_t activity) {
    for (unsigned y = 0; y < HEIGHT; ++y)
        for (unsigned x = 0; x < WIDTH; ++x) framebuffer[y][x] = 0u;
    draw_text(39u, 105u, "FLY LIVES", 3u, 3u);
    for (unsigned node = 0; node < 16u; ++node) {
        unsigned x = 92u + ((node * 23u + activity) % 57u);
        unsigned y = 48u + ((node * 17u + activity / 3u) % 45u);
        pixel(x, y, 2u);
        pixel(x + 1u, y, 2u);
    }
}

__attribute__((noreturn))
void flyos_target_main(void) {
    uint8_t staging[FLY_DISPLAY_STAGING_ROW_BYTES];
    fly_network_init(&fly, 0x46594c31u);
    for (;;) {
        fly_network_step(&fly, 0u);
        render_fly(fly_network_activity(&fly));
        fly_display_pack_row(framebuffer[105u], staging, false);
        for (unsigned index = 0; index < FLY_DISPLAY_STAGING_ROW_BYTES; ++index) {
            packed_probe_row[index] = staging[index];
        }
        for (volatile uint32_t delay = 0u; delay < 200000u; ++delay) {
            __asm volatile("nop");
        }
    }
}
