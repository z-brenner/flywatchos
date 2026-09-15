#include "fly/network.h"

#include <string.h>

static uint32_t xorshift32(uint32_t *state) {
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

static int16_t clamp_q8_8(int32_t value) {
    if (value > 4096) return 4096;
    if (value < -4096) return -4096;
    return (int16_t)value;
}

void fly_network_init(FlyNetwork *network, uint32_t identity_seed) {
    memset(network, 0, sizeof(*network));
    network->rng_state = identity_seed ? identity_seed : 0x6d2b79f5u;
    for (unsigned i = 0; i < FLY_NEURON_COUNT; ++i) {
        uint32_t value = xorshift32(&network->rng_state);
        network->activation[i] = (int16_t)((int32_t)(value & 0xffu) - 128);
    }
    network->mood = 128u;
}

void fly_network_step(FlyNetwork *network, uint8_t input_mask) {
    int16_t previous[FLY_NEURON_COUNT];
    memcpy(previous, network->activation, sizeof(previous));

    for (unsigned i = 0; i < FLY_NEURON_COUNT; ++i) {
        unsigned a = (i + FLY_NEURON_COUNT - 1u) % FLY_NEURON_COUNT;
        unsigned b = (i + FLY_NEURON_COUNT - 7u) % FLY_NEURON_COUNT;
        unsigned c = (i + 13u) % FLY_NEURON_COUNT;
        int32_t sum = (previous[i] * 3) / 4;
        sum += (previous[a] * 96) / 256;
        sum -= (previous[b] * 56) / 256;
        sum += (previous[c] * 32) / 256;

        if (i < 5u && (input_mask & (1u << i))) sum += 640;
        if (i >= 48u && i < 56u) sum += ((int32_t)network->mood - 128) * 2;

        int32_t noise = (int32_t)(xorshift32(&network->rng_state) & 0x1fu) - 16;
        network->activation[i] = clamp_q8_8(sum + noise);
    }

    uint32_t motor = 0;
    for (unsigned i = 56u; i < 64u; ++i) {
        motor += (uint32_t)(network->activation[i] < 0 ? -network->activation[i]
                                                       : network->activation[i]);
    }
    if (motor > 1024u && network->mood < 250u) ++network->mood;
    else if (motor <= 1024u && network->mood > 5u) --network->mood;
    ++network->tick;
}

uint16_t fly_network_activity(const FlyNetwork *network) {
    uint32_t total = 0;
    for (unsigned i = 0; i < FLY_NEURON_COUNT; ++i) {
        int32_t value = network->activation[i];
        total += (uint32_t)(value < 0 ? -value : value);
    }
    total /= FLY_NEURON_COUNT;
    return total > UINT16_MAX ? UINT16_MAX : (uint16_t)total;
}
