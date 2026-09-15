#include "display/framebuffer.h"

#include <stdio.h>
#include <string.h>

static const uint8_t *glyph(char c) {
    static const uint8_t blank[7] = {0};
    static const uint8_t digits[10][7] = {
        {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},
        {30,1,1,14,1,1,30},{2,6,10,18,31,2,2},{31,16,16,30,1,1,30},
        {14,16,16,30,17,17,14},{31,1,2,4,8,8,8},{14,17,17,14,17,17,14},
        {14,17,17,15,1,1,14}};
    static const uint8_t alpha[26][7] = {
        {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{14,17,16,16,16,17,14},
        {30,17,17,17,17,17,30},{31,16,16,30,16,16,31},{31,16,16,30,16,16,16},
        {14,17,16,23,17,17,15},{17,17,17,31,17,17,17},{14,4,4,4,4,4,14},
        {7,2,2,2,18,18,12},{17,18,20,24,20,18,17},{16,16,16,16,16,16,31},
        {17,27,21,21,17,17,17},{17,25,21,19,17,17,17},{14,17,17,17,17,17,14},
        {30,17,17,30,16,16,16},{14,17,17,17,21,18,13},{30,17,17,30,20,18,17},
        {15,16,16,14,1,1,30},{31,4,4,4,4,4,4},{17,17,17,17,17,17,14},
        {17,17,17,17,17,10,4},{17,17,17,21,21,21,10},{17,17,10,4,10,17,17},
        {17,17,10,4,4,4,4},{31,1,2,4,8,16,31}};
    static const uint8_t colon[7] = {0,4,4,0,4,4,0};
    if (c >= '0' && c <= '9') return digits[c - '0'];
    if (c >= 'A' && c <= 'Z') return alpha[c - 'A'];
    if (c == ':') return colon;
    return blank;
}

static void pixel(FlyFramebuffer *fb, int x, int y, uint8_t color) {
    if (x >= 0 && x < (int)FLY_DISPLAY_WIDTH && y >= 0 && y < (int)FLY_DISPLAY_HEIGHT)
        fb->pixels[y][x] = color;
}

static void text5x7(FlyFramebuffer *fb, int x, int y, const char *text, uint8_t color,
                    unsigned scale) {
    for (; *text; ++text, x += (int)(6u * scale)) {
        const uint8_t *rows = glyph(*text);
        for (unsigned row = 0; row < 7u; ++row)
            for (unsigned col = 0; col < 5u; ++col)
                if (rows[row] & (1u << (4u - col)))
                    for (unsigned dy = 0; dy < scale; ++dy)
                        for (unsigned dx = 0; dx < scale; ++dx)
                            pixel(fb, x + (int)(col * scale + dx),
                                  y + (int)(row * scale + dy), color);
    }
}

static void line(FlyFramebuffer *fb, int x0, int y0, int x1, int y1, uint8_t color) {
    int dx = x1 > x0 ? x1 - x0 : x0 - x1;
    int sx = x0 < x1 ? 1 : -1;
    int dy = y1 > y0 ? y0 - y1 : y1 - y0;
    int sy = y0 < y1 ? 1 : -1;
    int error = dx + dy;
    for (;;) {
        pixel(fb, x0, y0, color);
        if (x0 == x1 && y0 == y1) break;
        int twice = 2 * error;
        if (twice >= dy) { error += dy; x0 += sx; }
        if (twice <= dx) { error += dx; y0 += sy; }
    }
}

void fly_framebuffer_clear(FlyFramebuffer *fb, uint8_t color) {
    memset(fb->pixels, color, sizeof(fb->pixels));
}

void fly_framebuffer_render_status(FlyFramebuffer *fb, unsigned hour, unsigned minute,
                                   const char *state, uint32_t age_seconds,
                                   uint16_t neural_activity) {
    char buffer[32];
    fly_framebuffer_clear(fb, FLY_COLOR_BLACK);
    snprintf(buffer, sizeof(buffer), "%02u:%02u", hour % 24u, minute % 60u);
    text5x7(fb, 75, 12, buffer, FLY_COLOR_TEXT, 3u);

    /* Symmetric scientific-specimen outline: head, thorax, abdomen, wings, legs. */
    line(fb, 113, 59, 127, 59, FLY_COLOR_DIM);
    line(fb, 127, 59, 133, 66, FLY_COLOR_DIM);
    line(fb, 133, 66, 130, 78, FLY_COLOR_DIM);
    line(fb, 130, 78, 110, 78, FLY_COLOR_DIM);
    line(fb, 110, 78, 107, 66, FLY_COLOR_DIM);
    line(fb, 107, 66, 113, 59, FLY_COLOR_DIM);

    line(fb, 110, 80, 102, 94, FLY_COLOR_DIM);
    line(fb, 102, 94, 108, 112, FLY_COLOR_DIM);
    line(fb, 108, 112, 132, 112, FLY_COLOR_DIM);
    line(fb, 132, 112, 138, 94, FLY_COLOR_DIM);
    line(fb, 138, 94, 130, 80, FLY_COLOR_DIM);

    line(fb, 108, 114, 111, 137, FLY_COLOR_DIM);
    line(fb, 111, 137, 120, 153, FLY_COLOR_DIM);
    line(fb, 120, 153, 129, 137, FLY_COLOR_DIM);
    line(fb, 129, 137, 132, 114, FLY_COLOR_DIM);
    line(fb, 120, 81, 120, 151, FLY_COLOR_DIM);

    line(fb, 105, 88, 79, 70, FLY_COLOR_DIM);
    line(fb, 79, 70, 56, 76, FLY_COLOR_DIM);
    line(fb, 56, 76, 70, 111, FLY_COLOR_DIM);
    line(fb, 70, 111, 104, 105, FLY_COLOR_DIM);
    line(fb, 135, 88, 161, 70, FLY_COLOR_DIM);
    line(fb, 161, 70, 184, 76, FLY_COLOR_DIM);
    line(fb, 184, 76, 170, 111, FLY_COLOR_DIM);
    line(fb, 170, 111, 136, 105, FLY_COLOR_DIM);
    line(fb, 60, 78, 99, 101, FLY_COLOR_DIM);
    line(fb, 180, 78, 141, 101, FLY_COLOR_DIM);

    line(fb, 106, 91, 82, 118, FLY_COLOR_DIM);
    line(fb, 82, 118, 62, 126, FLY_COLOR_DIM);
    line(fb, 106, 101, 84, 133, FLY_COLOR_DIM);
    line(fb, 84, 133, 67, 145, FLY_COLOR_DIM);
    line(fb, 111, 119, 98, 145, FLY_COLOR_DIM);
    line(fb, 98, 145, 86, 156, FLY_COLOR_DIM);
    line(fb, 134, 91, 158, 118, FLY_COLOR_DIM);
    line(fb, 158, 118, 178, 126, FLY_COLOR_DIM);
    line(fb, 134, 101, 156, 133, FLY_COLOR_DIM);
    line(fb, 156, 133, 173, 145, FLY_COLOR_DIM);
    line(fb, 129, 119, 142, 145, FLY_COLOR_DIM);
    line(fb, 142, 145, 154, 156, FLY_COLOR_DIM);
    for (unsigned i = 0; i < 16u; ++i) {
        int x = 110 + (int)((i * 23u + neural_activity) % 21u);
        int y = 65 + (int)((i * 17u + neural_activity / 3u) % 79u);
        pixel(fb, x, y, FLY_COLOR_NEURAL);
        pixel(fb, x + 1, y, FLY_COLOR_NEURAL);
        if (i) line(fb, x, y, 110 + (int)(((i - 1u) * 23u + neural_activity) % 21u),
                    65 + (int)(((i - 1u) * 17u + neural_activity / 3u) % 79u),
                    FLY_COLOR_DIM);
    }

    text5x7(fb, 28, 166, "STATE", FLY_COLOR_DIM, 1u);
    text5x7(fb, 92, 166, state, FLY_COLOR_TEXT, 1u);
    snprintf(buffer, sizeof(buffer), "%02u:%02u:%02u",
             (unsigned)(age_seconds / 3600u) % 100u,
             (unsigned)(age_seconds / 60u) % 60u,
             (unsigned)age_seconds % 60u);
    text5x7(fb, 28, 181, "AGE", FLY_COLOR_DIM, 1u);
    text5x7(fb, 92, 181, buffer, FLY_COLOR_TEXT, 1u);
    text5x7(fb, 92, 208, "FLY LIVES", FLY_COLOR_TEXT, 1u);
}

unsigned fly_framebuffer_count_color(const FlyFramebuffer *fb, uint8_t color) {
    unsigned count = 0;
    for (unsigned y = 0; y < FLY_DISPLAY_HEIGHT; ++y)
        for (unsigned x = 0; x < FLY_DISPLAY_WIDTH; ++x)
            if (fb->pixels[y][x] == color) ++count;
    return count;
}

bool fly_framebuffer_region_nonzero(const FlyFramebuffer *fb, unsigned x0, unsigned y0,
                                    unsigned x1, unsigned y1) {
    if (x1 > FLY_DISPLAY_WIDTH) x1 = FLY_DISPLAY_WIDTH;
    if (y1 > FLY_DISPLAY_HEIGHT) y1 = FLY_DISPLAY_HEIGHT;
    for (unsigned y = y0; y < y1; ++y)
        for (unsigned x = x0; x < x1; ++x)
            if (fb->pixels[y][x] != FLY_COLOR_BLACK) return true;
    return false;
}

int fly_framebuffer_write_ppm(const FlyFramebuffer *fb, const char *path) {
    static const uint8_t palette[4][3] = {
        {8, 10, 9}, {54, 69, 59}, {135, 184, 122}, {218, 231, 211}};
    FILE *file = fopen(path, "wb");
    if (!file) return -1;
    fprintf(file, "P6\n%u %u\n255\n", FLY_DISPLAY_WIDTH, FLY_DISPLAY_HEIGHT);
    for (unsigned y = 0; y < FLY_DISPLAY_HEIGHT; ++y)
        for (unsigned x = 0; x < FLY_DISPLAY_WIDTH; ++x) {
            uint8_t color = fb->pixels[y][x] & 3u;
            if (fwrite(palette[color], 1, 3, file) != 3u) { fclose(file); return -1; }
        }
    return fclose(file);
}
