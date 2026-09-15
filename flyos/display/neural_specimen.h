#ifndef FLYOS_DISPLAY_NEURAL_SPECIMEN_H
#define FLYOS_DISPLAY_NEURAL_SPECIMEN_H

#include <stdint.h>

#include "fly/brain64.h"

#define FLY_NEURAL_SPECIMEN_WIDTH 240u
#define FLY_NEURAL_SPECIMEN_HEIGHT 240u
#define FLY_NEURAL_SPECIMEN_CELLS 64u
#define FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES \
    (FLY_NEURAL_SPECIMEN_WIDTH * FLY_NEURAL_SPECIMEN_HEIGHT)

/* Host previews use semantic indices; target roles use only proven 0x00/0xff. */
#ifdef FLY_NEURAL_SPECIMEN_HOST_PREVIEW
enum {
    FLY_NEURAL_SPECIMEN_BLACK = 0u,
    FLY_NEURAL_SPECIMEN_SCAFFOLD = 1u,
    FLY_NEURAL_SPECIMEN_TEXT = 2u,
    FLY_NEURAL_SPECIMEN_EXCITATORY = 3u,
    FLY_NEURAL_SPECIMEN_INHIBITORY = 4u,
    FLY_NEURAL_SPECIMEN_SATURATED = 5u
};
#else
enum {
    FLY_NEURAL_SPECIMEN_BLACK = 0x00u,
    FLY_NEURAL_SPECIMEN_SCAFFOLD = 0xffu,
    FLY_NEURAL_SPECIMEN_TEXT = 0xffu,
    FLY_NEURAL_SPECIMEN_EXCITATORY = 0xffu,
    FLY_NEURAL_SPECIMEN_INHIBITORY = 0xffu,
    FLY_NEURAL_SPECIMEN_SATURATED = 0xffu
};
#endif

typedef struct FlyNeuralSpecimenPoint {
    uint8_t x;
    uint8_t y;
    uint8_t width;
    uint8_t height;
} FlyNeuralSpecimenPoint;

extern const FlyNeuralSpecimenPoint
    fly_neural_specimen_points[FLY_NEURAL_SPECIMEN_CELLS];

const char *fly_neural_specimen_button_label(uint8_t buttons);
const char *fly_neural_specimen_unavailable_label(unsigned rail);

void fly_neural_specimen_render(
    uint8_t framebuffer[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES],
    const FlyBrain64 *brain, const FlyBrainInputs *inputs, uint32_t rtc_tick);
void fly_neural_specimen_render_if_home(
    uint8_t framebuffer[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES], uint8_t home_gate,
    const FlyBrain64 *brain, const FlyBrainInputs *inputs, uint32_t rtc_tick);

#endif
