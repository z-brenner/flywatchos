#ifndef FLY_BRAIN_ASCII_H
#define FLY_BRAIN_ASCII_H

#include <stdint.h>
#include "fly/brain32.h"

typedef struct { uint8_t x; uint8_t y; } FlyBrainPoint;

/* Top-left of a 5x7 cell, indexed by neuron ID. A neuron's only additional
 * activation-dependent pixels are (x+7,y+3) and (x+8,y+3), ink at level >= 2.
 * Other content uses RTC tick, the model's stored state/epoch and button mask;
 * directly changing one activation cannot change those status fields. */
extern const FlyBrainPoint fly_brain_points[32];

/* Requires non-null framebuffer and brain. Clears all 57,600 bytes to 0xff;
 * every subsequent draw writes 0x00. No heap, peripheral or library calls. */
void fly_brain_ascii_render(uint8_t framebuffer[57600], const FlyBrain32 *brain,
                            uint32_t rtc_tick, uint8_t buttons);

#endif
