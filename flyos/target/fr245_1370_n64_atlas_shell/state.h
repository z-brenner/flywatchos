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
 * empty, malformed, cyclic, over-long or changing list: it means "we do not
 * know", never "not home", and it always fails open to Garmin.
 */
enum FlyViewClass { FLY_VIEW_INVALID = 0, FLY_VIEW_HOME = 1, FLY_VIEW_NON_HOME = 2 };

/* Sentinel returned by the validated readers for a complement mismatch. */
#define FLY_STATE_INVALID 0xFFu

/*
 * One complement-protected byte: value in bits 0-3, its complement in bits 4-7.
 *
 * fly_state_word(local, mode) == fly_state_byte(local) | (fly_state_byte(mode) << 8),
 * so on this little-endian core the local nibble lives entirely in the byte at
 * record offset 0x36 and the mode nibble entirely in the byte at 0x37.  The
 * target addresses those two bytes independently, which is what keeps the
 * ownership subsystem and the system/detach subsystems from ever clobbering one
 * another: they write different addresses, and an aligned byte store is atomic
 * on this core, so neither needs a read-modify-write of the other's nibble.
 * Every value the target stores is a compile-time constant, so these fold to
 * immediates and generate no code.
 */
static inline uint8_t fly_state_byte(uint8_t value) {
    return (uint8_t)((value & 15u) | (((value & 15u) ^ 15u) << 4));
}

/* Returns the byte's nibble, or FLY_STATE_INVALID if its complement is wrong. */
static inline uint8_t fly_state_read_byte(uint8_t byte) {
    uint8_t value = (uint8_t)(byte & 15u);
    return (uint8_t)(byte == fly_state_byte(value) ? value : FLY_STATE_INVALID);
}

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
