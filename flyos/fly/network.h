#ifndef FLYOS_FLY_NETWORK_H
#define FLYOS_FLY_NETWORK_H

#include <stdint.h>

#define FLY_NEURON_COUNT 64u

enum {
    FLY_INPUT_UP = 1u << 0,
    FLY_INPUT_DOWN = 1u << 1,
    FLY_INPUT_BACK = 1u << 2,
    FLY_INPUT_SELECT = 1u << 3,
    FLY_INPUT_LIGHT = 1u << 4
};

typedef struct {
    uint32_t tick;
    uint32_t rng_state;
    int16_t activation[FLY_NEURON_COUNT]; /* Signed Q8.8 values. */
    uint8_t mood;
    uint8_t reserved[3];
} FlyNetwork;

void fly_network_init(FlyNetwork *network, uint32_t identity_seed);
void fly_network_step(FlyNetwork *network, uint8_t input_mask);
uint16_t fly_network_activity(const FlyNetwork *network);

#endif
