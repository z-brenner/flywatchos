#ifndef FLYOS_FLY_BRAIN32_H
#define FLYOS_FLY_BRAIN32_H

#include <stdint.h>

#define FLY_BRAIN_NEURONS 32u

/* input_mask bits are pressed-button bits, in the physical GPIO order. */
enum {
    FLY_BRAIN_INPUT_LIGHT = 1u << 0,
    FLY_BRAIN_INPUT_START = 1u << 1,
    FLY_BRAIN_INPUT_BACK = 1u << 2,
    FLY_BRAIN_INPUT_DOWN = 1u << 3,
    FLY_BRAIN_INPUT_UP = 1u << 4
};

enum {
    FLY_BRAIN_LEVEL_DOT = 0u,
    FLY_BRAIN_LEVEL_SMALL_O = 1u,
    FLY_BRAIN_LEVEL_LARGE_O = 2u,
    FLY_BRAIN_LEVEL_AT = 3u
};

enum {
    FLY_BRAIN_STATE_REST = 0u,
    FLY_BRAIN_STATE_MOVEMENT = 1u,
    FLY_BRAIN_STATE_AROUSAL = 2u,
    FLY_BRAIN_STATE_QUIET = 3u
};

typedef struct FlyBrain32 {
    int16_t activation[FLY_BRAIN_NEURONS];
    uint32_t rng_state;
    uint32_t epoch;
    uint8_t state;
    uint8_t reserved[3];
} FlyBrain32;

void fly_brain32_seed(FlyBrain32 *brain, uint32_t identity_seed, uint32_t epoch);
void fly_brain32_step(FlyBrain32 *brain, uint8_t input_mask);
void fly_brain32_reconstruct(FlyBrain32 *brain, uint32_t identity_seed,
                             uint32_t rtc_tick, uint8_t input_mask);
uint8_t fly_brain32_level(const FlyBrain32 *brain, unsigned neuron);
uint8_t fly_brain32_state(const FlyBrain32 *brain);

#endif
