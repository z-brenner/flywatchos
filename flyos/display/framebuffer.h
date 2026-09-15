#ifndef FLYOS_DISPLAY_FRAMEBUFFER_H
#define FLYOS_DISPLAY_FRAMEBUFFER_H

#include <stdbool.h>
#include <stdint.h>

#define FLY_DISPLAY_WIDTH 240u
#define FLY_DISPLAY_HEIGHT 240u

enum {
    FLY_COLOR_BLACK = 0,
    FLY_COLOR_DIM = 1,
    FLY_COLOR_NEURAL = 2,
    FLY_COLOR_TEXT = 3
};

typedef struct {
    uint8_t pixels[FLY_DISPLAY_HEIGHT][FLY_DISPLAY_WIDTH];
} FlyFramebuffer;

void fly_framebuffer_clear(FlyFramebuffer *fb, uint8_t color);
void fly_framebuffer_render_status(FlyFramebuffer *fb, unsigned hour, unsigned minute,
                                   const char *state, uint32_t age_seconds,
                                   uint16_t neural_activity);
unsigned fly_framebuffer_count_color(const FlyFramebuffer *fb, uint8_t color);
bool fly_framebuffer_region_nonzero(const FlyFramebuffer *fb, unsigned x0, unsigned y0,
                                    unsigned x1, unsigned y1);
int fly_framebuffer_write_ppm(const FlyFramebuffer *fb, const char *path);

#endif
