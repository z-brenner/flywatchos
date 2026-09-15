#include "fly/brain32.h"

#define FLY_BRAIN_MINIMUM (-16384)
#define FLY_BRAIN_MAXIMUM 16383
#define FLY_BRAIN_INPUT_DRIVE 4096

typedef struct {
    uint8_t source;
    uint8_t target;
    uint8_t shift;
    uint8_t positive;
} FlyBrain32Edge;

/*
 * Contributions are powers of two to keep the on-watch step to integer adds
 * and shifts.  The table covers sensory, heading, association, identity, and
 * action populations.  The heading rows are its two ring neighbours plus its
 * opposite node; the rest are deliberately sparse recurrent motifs.
 */
static const FlyBrain32Edge fly_brain32_edges[] = {
    { 0u,  5u, 2u, 1u }, { 1u,  6u, 2u, 1u },
    { 2u,  7u, 2u, 1u }, { 3u,  8u, 2u, 1u },
    { 4u,  9u, 2u, 1u },

    {  5u,  6u, 3u, 1u }, {  6u,  5u, 3u, 1u },
    {  6u,  7u, 3u, 1u }, {  7u,  6u, 3u, 1u },
    {  7u,  8u, 3u, 1u }, {  8u,  7u, 3u, 1u },
    {  8u,  9u, 3u, 1u }, {  9u,  8u, 3u, 1u },
    {  9u, 10u, 3u, 1u }, { 10u,  9u, 3u, 1u },
    { 10u, 11u, 3u, 1u }, { 11u, 10u, 3u, 1u },
    { 11u, 12u, 3u, 1u }, { 12u, 11u, 3u, 1u },
    { 12u,  5u, 3u, 1u }, {  5u, 12u, 3u, 1u },
    {  5u,  9u, 4u, 0u }, {  6u, 10u, 4u, 0u },
    {  7u, 11u, 4u, 0u }, {  8u, 12u, 4u, 0u },
    {  9u,  5u, 4u, 0u }, { 10u,  6u, 4u, 0u },
    { 11u,  7u, 4u, 0u }, { 12u,  8u, 4u, 0u },

    {  5u, 13u, 3u, 1u }, {  6u, 14u, 3u, 1u },
    {  7u, 15u, 3u, 1u }, {  8u, 16u, 3u, 1u },
    {  9u, 17u, 3u, 1u }, { 10u, 18u, 3u, 1u },
    { 11u, 19u, 3u, 1u }, { 12u, 20u, 3u, 1u },
    { 13u, 16u, 4u, 1u }, { 16u, 19u, 4u, 1u },
    { 19u, 22u, 4u, 1u }, { 22u, 13u, 4u, 1u },
    { 14u, 17u, 4u, 1u }, { 17u, 20u, 4u, 1u },
    { 20u, 23u, 4u, 1u }, { 23u, 14u, 4u, 1u },
    { 15u, 18u, 4u, 1u }, { 18u, 21u, 4u, 1u },
    { 21u, 24u, 4u, 1u }, { 24u, 15u, 4u, 1u },
    { 13u, 20u, 5u, 0u }, { 14u, 21u, 5u, 0u },
    { 15u, 22u, 5u, 0u }, { 16u, 23u, 5u, 0u },
    { 17u, 24u, 5u, 0u }, { 18u, 13u, 5u, 0u },

    { 25u, 26u, 5u, 1u }, { 26u, 27u, 5u, 1u },
    { 27u, 28u, 5u, 1u }, { 28u, 25u, 5u, 1u },
    { 25u, 14u, 5u, 1u }, { 26u, 17u, 5u, 1u },
    { 27u, 20u, 5u, 1u }, { 28u, 23u, 5u, 1u },

    { 13u, 29u, 3u, 1u }, { 16u, 29u, 3u, 1u },
    { 19u, 29u, 3u, 1u }, { 22u, 29u, 3u, 1u },
    { 14u, 30u, 3u, 1u }, { 17u, 30u, 3u, 1u },
    { 20u, 30u, 3u, 1u }, { 23u, 30u, 3u, 1u },
    { 15u, 31u, 3u, 1u }, { 18u, 31u, 3u, 1u },
    { 21u, 31u, 3u, 1u }, { 24u, 31u, 3u, 1u },
    { 29u, 16u, 5u, 1u }, { 30u, 19u, 5u, 1u },
    { 31u, 22u, 5u, 1u }
};

static uint32_t fly_brain32_xorshift32(uint32_t *state) {
    uint32_t value = *state;
    value ^= value << 13;
    value ^= value >> 17;
    value ^= value << 5;
    *state = value;
    return value;
}

static int16_t fly_brain32_clamp(int32_t value) {
    if (value > FLY_BRAIN_MAXIMUM) return FLY_BRAIN_MAXIMUM;
    if (value < FLY_BRAIN_MINIMUM) return FLY_BRAIN_MINIMUM;
    return (int16_t)value;
}

static int32_t fly_brain32_absolute(int16_t value) {
    int32_t wide = value;
    if (wide < 0) return -wide;
    return wide;
}

/* Defined arithmetic right shift for signed Q5.10 values. */
static int32_t fly_brain32_scale_shift(int16_t value, uint8_t shift) {
    int32_t wide = value;

    if (wide >= 0) return wide >> shift;
    return -((-wide + (int32_t)((1u << shift) - 1u)) >> shift);
}

static void fly_brain32_update_state(FlyBrain32 *brain) {
    int32_t movement = fly_brain32_absolute(brain->activation[29]);
    int32_t arousal = fly_brain32_absolute(brain->activation[30]);
    int32_t quiet = fly_brain32_absolute(brain->activation[31]);

    brain->state = FLY_BRAIN_STATE_REST;
    if (movement >= 512 && movement >= arousal && movement >= quiet) {
        brain->state = FLY_BRAIN_STATE_MOVEMENT;
    } else if (arousal >= 512 && arousal >= quiet) {
        brain->state = FLY_BRAIN_STATE_AROUSAL;
    } else if (quiet >= 512) {
        brain->state = FLY_BRAIN_STATE_QUIET;
    }
}

void fly_brain32_seed(FlyBrain32 *brain, uint32_t identity_seed, uint32_t epoch) {
    uint32_t seed = identity_seed ^ (epoch << 16) ^ (epoch >> 7) ^ 0x9e3779b9u;

    if (seed == 0u) seed = 0x6d2b79f5u;
    brain->rng_state = seed;
    brain->epoch = epoch;
    brain->state = FLY_BRAIN_STATE_REST;
    brain->reserved[0] = 0u;
    brain->reserved[1] = 0u;
    brain->reserved[2] = 0u;

    for (unsigned neuron = 0u; neuron < FLY_BRAIN_NEURONS; ++neuron) {
        uint32_t sample = fly_brain32_xorshift32(&brain->rng_state);
        int32_t value = (int32_t)(sample & 0x1ffu) - 256;
        if (neuron >= 25u && neuron <= 28u) {
            value = (int32_t)(sample & 0x7ffu) - 1024;
            value += value;
        }
        brain->activation[neuron] = fly_brain32_clamp(value);
    }
    fly_brain32_update_state(brain);
}

void fly_brain32_step(FlyBrain32 *brain, uint8_t input_mask) {
    int16_t previous[FLY_BRAIN_NEURONS];
    int32_t next[FLY_BRAIN_NEURONS];

    for (unsigned neuron = 0u; neuron < FLY_BRAIN_NEURONS; ++neuron) {
        previous[neuron] = brain->activation[neuron];
        next[neuron] = fly_brain32_scale_shift(previous[neuron], 1u) +
                       fly_brain32_scale_shift(previous[neuron], 2u);
    }

    for (unsigned edge = 0u;
         edge < (unsigned)(sizeof(fly_brain32_edges) / sizeof(fly_brain32_edges[0]));
        ++edge) {
        const FlyBrain32Edge *connection = &fly_brain32_edges[edge];
        int32_t contribution = fly_brain32_scale_shift(
            previous[connection->source], connection->shift);
        if (connection->positive != 0u) next[connection->target] += contribution;
        else next[connection->target] -= contribution;
    }

    for (unsigned sensory = 0u; sensory < 5u; ++sensory) {
        if ((input_mask & (uint8_t)(1u << sensory)) != 0u) {
            next[sensory] += FLY_BRAIN_INPUT_DRIVE;
        }
    }

    for (unsigned neuron = 0u; neuron < FLY_BRAIN_NEURONS; ++neuron) {
        int32_t noise = (int32_t)(fly_brain32_xorshift32(&brain->rng_state) & 0x1fu) - 16;
        brain->activation[neuron] = fly_brain32_clamp(next[neuron] + noise);
    }

    ++brain->epoch;
    fly_brain32_update_state(brain);
}

void fly_brain32_reconstruct(FlyBrain32 *brain, uint32_t identity_seed,
                             uint32_t rtc_tick, uint8_t input_mask) {
    uint32_t epoch = rtc_tick >> 3;
    unsigned steps = (unsigned)(rtc_tick & 0x7u) + 1u;

    fly_brain32_seed(brain, identity_seed, epoch);
    for (unsigned step = 0u; step < steps; ++step) {
        fly_brain32_step(brain, input_mask);
    }
}

uint8_t fly_brain32_level(const FlyBrain32 *brain, unsigned neuron) {
    int32_t magnitude;

    if (neuron >= FLY_BRAIN_NEURONS) return FLY_BRAIN_LEVEL_DOT;
    magnitude = fly_brain32_absolute(brain->activation[neuron]);
    if (magnitude < 128) return FLY_BRAIN_LEVEL_DOT;
    if (magnitude < 256) return FLY_BRAIN_LEVEL_SMALL_O;
    if (magnitude < 512) return FLY_BRAIN_LEVEL_LARGE_O;
    return FLY_BRAIN_LEVEL_AT;
}

uint8_t fly_brain32_state(const FlyBrain32 *brain) {
    return brain->state;
}
