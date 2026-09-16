#ifndef FLYOS_FR245_1370_N64_ATLAS_SHELL_STATE_H
#define FLYOS_FR245_1370_N64_ATLAS_SHELL_STATE_H

#include <stdint.h>

/*
 * Complement-protected 16-bit key-record state word.
 *
 * Each audited key halfword packs two 4-bit fields, each mirrored by its
 * one's-complement in the adjacent nibble:
 *
 *   bits 0-3   local   (owner/pulse state for this physical key)
 *   bits 4-7   ~local  (complement, detects reset/garbage/torn writes)
 *   bits 8-11  mode    (only LIGHT's word uses FlySystemMode; only START's
 *                        word uses FlyDetachMode; BACK/DOWN/UP require 0)
 *   bits 12-15 ~mode   (complement)
 *
 * A word whose stored nibble does not equal the complement of its neighbor
 * is invalid and must be treated as an unrecognized/reset encoding, never as
 * a decoded local/mode value.
 */

enum FlyLocalState { FLY_IDLE = 0, FLY_HELD = 1, FLY_PULSE = 2, GARMIN_HELD = 3 };
enum FlySystemMode { NORMAL = 0, CHORD_HOLD = 1, SYSTEM_PENDING = 2,
                     SYSTEM_HOME = 3, SYSTEM_EXCURSION = 4 };
enum FlyDetachMode { DETACH_NONE = 0, DETACH_PENDING = 1, DETACH_RETRY1 = 2,
                     DETACH_RETRY2 = 3, DETACH_RETRY3 = 4,
                     DETACH_QUEUED = 5, DETACH_EXHAUSTED = 6 };

/*
 * Tri-state classification of Garmin's bounded view list.  INVALID covers an
 * empty, malformed, cyclic, over-long, or changing list: it is "we do not
 * know", never "not home", and always fails open to Garmin.
 */
enum FlyViewClass { FLY_VIEW_INVALID = 0, FLY_VIEW_HOME = 1, FLY_VIEW_NON_HOME = 2 };

struct FlyViewResult {
    uint32_t home; /* first-visible watch-face node, or 0 unless kind is HOME */
    uint8_t kind;  /* enum FlyViewClass */
};

/* Renderer flags passed as n64_render's final argument. */
#define FLY_UI_USB 1u
#define FLY_UI_CHORD_ARMED 2u
#define FLY_UI_SYSTEM 4u

/* Sentinel returned by the validated readers for a complement mismatch. */
#define FLY_STATE_INVALID 0xFFu

static inline uint16_t fly_state_word(uint8_t local, uint8_t mode) {
    return (uint16_t)(local | ((local ^ 15u) << 4) |
                      ((uint16_t)mode << 8) | ((uint16_t)(mode ^ 15u) << 12));
}

/* Returns the local nibble, or FLY_STATE_INVALID if its complement is wrong. */
static inline uint8_t fly_state_read_local(uint16_t word) {
    uint8_t local = (uint8_t)(word & 0xFu);
    uint8_t complement = (uint8_t)((word >> 4) & 0xFu);
    return (uint8_t)(complement == (uint8_t)(local ^ 15u) ? local : FLY_STATE_INVALID);
}

/* Returns the mode nibble, or FLY_STATE_INVALID if its complement is wrong. */
static inline uint8_t fly_state_read_mode(uint16_t word) {
    uint8_t mode = (uint8_t)((word >> 8) & 0xFu);
    uint8_t complement = (uint8_t)((word >> 12) & 0xFu);
    return (uint8_t)(complement == (uint8_t)(mode ^ 15u) ? mode : FLY_STATE_INVALID);
}

#endif
