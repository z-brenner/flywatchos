#include <stdint.h>

enum {
    SCREEN_WIDTH = 240,
    SCREEN_HEIGHT = 240,
    SCREEN_BYTES = SCREEN_WIDTH * SCREEN_HEIGHT,
    FLY_WIDTH = 21,
    FLY_HEIGHT = 16,
};

typedef uint32_t (*dispatch_flush_fn)(uint8_t *, int);
typedef void (*dirty_add_fn)(int, int, int, int);

enum { SP, A, E, F, G, I, L, Q, S, T, U, V, Y, N0, N1, N2, N3, N4, COLON };

static const uint8_t font[19][7] = {
    {0,0,0,0,0,0,0},                              /* space */
    {0x04,0x0a,0x11,0x11,0x1f,0x11,0x11},        /* A */
    {0x1f,0x10,0x10,0x1e,0x10,0x10,0x1f},        /* E */
    {0x1f,0x10,0x10,0x1e,0x10,0x10,0x10},        /* F */
    {0x0f,0x10,0x10,0x13,0x11,0x11,0x0f},        /* G */
    {0x1f,0x04,0x04,0x04,0x04,0x04,0x1f},        /* I */
    {0x10,0x10,0x10,0x10,0x10,0x10,0x1f},        /* L */
    {0x0e,0x11,0x11,0x11,0x15,0x12,0x0d},        /* Q */
    {0x0f,0x10,0x10,0x0e,0x01,0x01,0x1e},        /* S */
    {0x1f,0x04,0x04,0x04,0x04,0x04,0x04},        /* T */
    {0x11,0x11,0x11,0x11,0x11,0x11,0x0e},        /* U */
    {0x11,0x11,0x11,0x11,0x11,0x0a,0x04},        /* V */
    {0x11,0x11,0x0a,0x04,0x04,0x04,0x04},        /* Y */
    {0x0e,0x11,0x13,0x15,0x19,0x11,0x0e},        /* 0 */
    {0x04,0x0c,0x04,0x04,0x04,0x04,0x0e},        /* 1 */
    {0x0e,0x11,0x01,0x02,0x04,0x08,0x1f},        /* 2 */
    {0x0e,0x11,0x01,0x02,0x01,0x11,0x0e},        /* 3 */
    {0x02,0x06,0x0a,0x12,0x1f,0x02,0x02},        /* 4 */
    {0,0x04,0x04,0,0x04,0x04,0},                 /* : */
};

static const uint8_t title[] = {F,L,Y,SP,L,I,V,E,S};
static const uint8_t state[] = {S,T,A,T,E,SP,Q,U,I,E,T};
static const uint8_t age[] = {A,G,E,SP,N0,N1,COLON,N4,N2,COLON,N3,N2};
static const uint8_t markers[] = {L,N1,N2,N3,N4};

/* 21x16 dorsal Drosophila silhouette: head, thorax, wings, abdomen, legs. */
static const uint32_t fly_rows[FLY_HEIGHT] = {
    0x00e00,0x01f00,0x39f38,0x7df7c,
    0xfdf7e,0xfeefe,0x7eefc,0x3eef8,
    0x1eef0,0x0eee0,0x43f84,0x84e42,
    0x04e40,0x08e20,0x00e00,0x00400,
};

static void draw_text(uint8_t *fb, const uint8_t *text, unsigned glyphs,
                      unsigned x, unsigned y, unsigned scale) {
    unsigned glyph, row, column, dx, dy;
    for (glyph = 0; glyph < glyphs; ++glyph) {
        for (row = 0; row < 7; ++row) {
            uint8_t bits = font[text[glyph]][row];
            for (column = 0; column < 5; ++column) {
                if ((bits & (uint8_t)(0x10u >> column)) != 0u) {
                    unsigned px = x + (glyph * 6 + column) * scale;
                    unsigned py = y + row * scale;
                    for (dy = 0; dy < scale; ++dy)
                        for (dx = 0; dx < scale; ++dx)
                            fb[(py + dy) * SCREEN_WIDTH + px + dx] = 0x00;
                }
            }
        }
    }
}

static uint32_t read_buttons(void) {
    uint32_t a = *(volatile const uint32_t *)0x400ff010u;
    uint32_t c = *(volatile const uint32_t *)0x400ff090u;
    uint32_t d = *(volatile const uint32_t *)0x400ff0d0u;
    return (((c & 0x00000800u) == 0u) << 0) |
           (((d & 0x00000400u) == 0u) << 1) |
           (((d & 0x00000002u) == 0u) << 2) |
           (((a & 0x00100000u) == 0u) << 3) |
           (((a & 0x00400000u) == 0u) << 4);
}

static void draw_button_markers(uint8_t *fb, uint32_t pressed) {
    unsigned key, x, y, row, column;
    for (key = 0; key < 5; ++key) {
        unsigned left = 42 + key * 36;
        uint8_t fill = (pressed & (1u << key)) != 0u ? 0x00 : 0xff;
        uint8_t ink = (uint8_t)~fill;
        for (y = 0; y < 12; ++y)
            for (x = 0; x < 12; ++x)
                fb[(214 + y) * SCREEN_WIDTH + left + x] =
                    (x == 0 || x == 11 || y == 0 || y == 11) ? 0x00 : fill;
        for (row = 0; row < 7; ++row) {
            uint8_t bits = font[markers[key]][row];
            for (column = 0; column < 5; ++column)
                if ((bits & (uint8_t)(0x10u >> column)) != 0u)
                    fb[(216 + row) * SCREEN_WIDTH + left + 3 + column] = ink;
        }
    }
}

__attribute__((used))
void flyos_render_fullscreen(uint8_t *fb) {
    unsigned i, x, y, row, column, dx, dy;

    /* Own every logical pixel on every flush so Garmin UI cannot bleed through. */
    for (i = 0; i < SCREEN_BYTES; ++i)
        fb[i] = 0xff;

    /* Sparse scientific-instrument frame and specimen dividers. */
    for (x = 10; x < 230; ++x) {
        fb[10 * SCREEN_WIDTH + x] = 0x00;
        fb[229 * SCREEN_WIDTH + x] = 0x00;
        fb[52 * SCREEN_WIDTH + x] = 0x00;
        fb[168 * SCREEN_WIDTH + x] = 0x00;
        fb[211 * SCREEN_WIDTH + x] = 0x00;
    }
    for (y = 10; y < 230; ++y) {
        fb[y * SCREEN_WIDTH + 10] = 0x00;
        fb[y * SCREEN_WIDTH + 229] = 0x00;
    }

    draw_text(fb, title, 9, 39, 20, 3);

    /* Large centered fly: 21x16 source pixels at 4x scale -> 84x64. */
    for (row = 0; row < FLY_HEIGHT; ++row) {
        uint32_t bits = fly_rows[row];
        for (column = 0; column < FLY_WIDTH; ++column) {
            if ((bits & (1u << (FLY_WIDTH - 1u - column))) != 0u) {
                unsigned px = 78 + column * 4;
                unsigned py = 79 + row * 4;
                for (dy = 0; dy < 4; ++dy)
                    for (dx = 0; dx < 4; ++dx)
                        fb[(py + dy) * SCREEN_WIDTH + px + dx] = 0x00;
            }
        }
    }

    draw_text(fb, state, 11, 54, 175, 2);
    draw_text(fb, age, 12, 48, 193, 2);
    draw_button_markers(fb, read_buttons());
}

__attribute__((section(".overlay.entry"), used))
uint32_t overlay_then_flush(uint8_t *framebuffer, int original_wait) {
    volatile const uint32_t *active_backend =
        (volatile const uint32_t *)0x1ffdb754u;
    volatile const uint8_t *startup_complete =
        (volatile const uint8_t *)0x1fff223cu;
    dirty_add_fn dirty_add = (dirty_add_fn)0x0000f2e9u;
    dispatch_flush_fn dispatch_flush = (dispatch_flush_fn)0x0000e1a5u;

    (void)original_wait;
    if (framebuffer != (uint8_t *)0 &&
        *active_backend == 0x0000ebfcu &&
        *startup_complete == 1u) {
        flyos_render_fullscreen(framebuffer);
        dirty_add(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT);
    }
    return dispatch_flush(framebuffer, 0);
}
