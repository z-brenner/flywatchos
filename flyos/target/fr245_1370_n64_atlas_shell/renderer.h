#ifndef FLYOS_FR245_1370_N64_ATLAS_SHELL_RENDERER_H
#define FLYOS_FR245_1370_N64_ATLAS_SHELL_RENDERER_H

#include <stdint.h>

#include "fly/brain64.h"

/*
 * Presentation flags the overlay entry point hands to the renderer.  There is
 * deliberately no charging flag: charging telemetry is not a proved input on
 * this image and must never be fabricated.
 */
enum {
    FLY_UI_USB = 1u,          /* USB mass storage is mounted */
    FLY_UI_CHORD_ARMED = 2u,  /* a system chord is being held down */
    FLY_UI_SYSTEM = 4u        /* a deliberate Garmin system session is running */
};

void n64_render(uint8_t *framebuffer, const FlyBrain64 *brain,
                const FlyBrainInputs *inputs, uint32_t tick, uint8_t ui_flags);

#endif
