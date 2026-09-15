#ifndef FLYOS_FLY_BRAIN64_H
#define FLYOS_FLY_BRAIN64_H

#include <stdint.h>

#define FLY_BRAIN64_NEURONS 64u

/* buttons uses the physical GPIO order: LIGHT, START, BACK, DOWN, UP. */
enum {
    FLY_BRAIN64_BUTTON_LIGHT = 1u << 0,
    FLY_BRAIN64_BUTTON_START = 1u << 1,
    FLY_BRAIN64_BUTTON_BACK = 1u << 2,
    FLY_BRAIN64_BUTTON_DOWN = 1u << 3,
    FLY_BRAIN64_BUTTON_UP = 1u << 4
};

/* Optional values contribute only while their corresponding bit is set. */
enum {
    FLY_BRAIN64_VALID_HEART_RATE = 1u << 0,
    FLY_BRAIN64_VALID_MOTION = 1u << 1,
    FLY_BRAIN64_VALID_BATTERY = 1u << 2,
    FLY_BRAIN64_VALID_CHARGING = 1u << 3
};

enum {
    FLY_BRAIN64_LEVEL_DOT = 0u,
    FLY_BRAIN64_LEVEL_SMALL_O = 1u,
    FLY_BRAIN64_LEVEL_LARGE_O = 2u,
    FLY_BRAIN64_LEVEL_AT = 3u
};

enum {
    FLY_BRAIN64_STATE_REST = 0u,
    FLY_BRAIN64_STATE_MOVEMENT = 1u,
    FLY_BRAIN64_STATE_AROUSAL = 2u,
    FLY_BRAIN64_STATE_QUIET = 3u
};

typedef struct FlyBrainInputs {
    uint8_t buttons;
    uint8_t valid_mask;
    uint16_t heart_rate_bpm;
    int16_t heart_rate_delta;
    int16_t motion;
    uint8_t battery_percent;
    uint8_t charging;
} FlyBrainInputs;

typedef struct FlyBrain64 {
    int16_t activation[FLY_BRAIN64_NEURONS];
    uint32_t rng_state;
    uint32_t epoch;
    uint8_t state;
    uint8_t reserved[3];
} FlyBrain64;

void fly_brain64_seed(FlyBrain64 *brain, uint32_t identity_seed, uint32_t epoch);
void fly_brain64_step(FlyBrain64 *brain, const FlyBrainInputs *inputs);
void fly_brain64_reconstruct(FlyBrain64 *brain, uint32_t identity_seed,
                             uint32_t rtc_tick, const FlyBrainInputs *inputs);
uint8_t fly_brain64_level(const FlyBrain64 *brain, unsigned neuron);
uint8_t fly_brain64_state(const FlyBrain64 *brain);

#endif
