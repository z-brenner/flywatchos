#ifndef FLYOS_DISPLAY_GARMIN_ROW_PACKER_H
#define FLYOS_DISPLAY_GARMIN_ROW_PACKER_H

#include <stdbool.h>
#include <stdint.h>

#include "display/framebuffer.h"

#define FLY_DISPLAY_STAGING_ROW_BYTES (FLY_DISPLAY_WIDTH + 4u)

/*
 * Convert one 240-byte logical framebuffer row to the verified 244-byte
 * staging layout used by the official firmware. This is a RAM-only layout
 * transform; it does not touch FLEXIO, DMA, GPIO, or the display panel.
 */
void fly_display_pack_row(const uint8_t source[FLY_DISPLAY_WIDTH],
                          uint8_t staging[FLY_DISPLAY_STAGING_ROW_BYTES],
                          bool reverse);

#endif
