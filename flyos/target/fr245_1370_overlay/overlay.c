#include <stdint.h>

enum {
    SCREEN_WIDTH = 240,
    OVERLAY_X = 50,
    OVERLAY_Y = 102,
    OVERLAY_WIDTH = 140,
    OVERLAY_HEIGHT = 22,
    FLY_X = 54,
    FLY_Y = 105,
    FLY_WIDTH = 21,
    FLY_HEIGHT = 16,
    TEXT_X = 80,
    TEXT_Y = 106,
};

typedef uint32_t (*dispatch_flush_fn)(uint8_t *, int);
typedef void (*dirty_add_fn)(int, int, int, int);

/* 5x7 rows for "FLY LIVES". Bit 4 is the leftmost pixel. */
static const uint8_t fly_lives_rows[9][7] = {
    {0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x10}, /* F */
    {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1f}, /* L */
    {0x11, 0x11, 0x0a, 0x04, 0x04, 0x04, 0x04}, /* Y */
    {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}, /* space */
    {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1f}, /* L */
    {0x1f, 0x04, 0x04, 0x04, 0x04, 0x04, 0x1f}, /* I */
    {0x11, 0x11, 0x11, 0x11, 0x11, 0x0a, 0x04}, /* V */
    {0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x1f}, /* E */
    {0x0f, 0x10, 0x10, 0x0e, 0x01, 0x01, 0x1e}, /* S */
};

/* 21x16 dorsal Drosophila silhouette: head, thorax, wings, abdomen, legs. */
static const uint32_t fly_rows[FLY_HEIGHT] = {
    0x00e00, 0x01f00, 0x39f38, 0x7df7c,
    0xfdf7e, 0xfeefe, 0x7eefc, 0x3eef8,
    0x1eef0, 0x0eee0, 0x43f84, 0x84e42,
    0x04e40, 0x08e20, 0x00e00, 0x00400,
};

static void draw_overlay(uint8_t *framebuffer) {
    unsigned y;
    unsigned x;
    unsigned glyph;
    unsigned row;
    unsigned column;

    for (y = 0; y < OVERLAY_HEIGHT; ++y) {
        uint8_t *line = framebuffer + (OVERLAY_Y + y) * SCREEN_WIDTH + OVERLAY_X;
        for (x = 0; x < OVERLAY_WIDTH; ++x) {
            line[x] = 0xff;
        }
    }

    /* One-pixel specimen-plate rule. */
    for (x = 0; x < OVERLAY_WIDTH; ++x) {
        framebuffer[OVERLAY_Y * SCREEN_WIDTH + OVERLAY_X + x] = 0x00;
        framebuffer[(OVERLAY_Y + OVERLAY_HEIGHT - 1) * SCREEN_WIDTH +
                    OVERLAY_X + x] = 0x00;
    }
    for (y = 1; y + 1 < OVERLAY_HEIGHT; ++y) {
        framebuffer[(OVERLAY_Y + y) * SCREEN_WIDTH + OVERLAY_X] = 0x00;
        framebuffer[(OVERLAY_Y + y) * SCREEN_WIDTH +
                    OVERLAY_X + OVERLAY_WIDTH - 1] = 0x00;
    }

    for (row = 0; row < FLY_HEIGHT; ++row) {
        uint32_t bits = fly_rows[row];
        for (column = 0; column < FLY_WIDTH; ++column) {
            if ((bits & (1u << (FLY_WIDTH - 1u - column))) != 0u) {
                framebuffer[(FLY_Y + row) * SCREEN_WIDTH + FLY_X + column] =
                    0x00;
            }
        }
    }

    for (glyph = 0; glyph < 9; ++glyph) {
        for (row = 0; row < 7; ++row) {
            uint8_t bits = fly_lives_rows[glyph][row];
            for (column = 0; column < 5; ++column) {
                if ((bits & (uint8_t)(0x10u >> column)) != 0) {
                    unsigned px = TEXT_X + glyph * 12 + column * 2;
                    unsigned py = TEXT_Y + row * 2;
                    framebuffer[py * SCREEN_WIDTH + px] = 0x00;
                    framebuffer[py * SCREEN_WIDTH + px + 1] = 0x00;
                    framebuffer[(py + 1) * SCREEN_WIDTH + px] = 0x00;
                    framebuffer[(py + 1) * SCREEN_WIDTH + px + 1] = 0x00;
                }
            }
        }
    }
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
        draw_overlay(framebuffer);
        dirty_add(OVERLAY_X, OVERLAY_Y, OVERLAY_WIDTH, OVERLAY_HEIGHT);
    }
    return dispatch_flush(framebuffer, 0);
}
