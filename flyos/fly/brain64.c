#include "fly/brain64.h"

#define FLY_BRAIN64_MINIMUM (-16384)
#define FLY_BRAIN64_MAXIMUM 16383
#define FLY_BRAIN64_BUTTON_DRIVE 4096

typedef struct {
    uint8_t source;
    uint8_t target;
    uint8_t shift;
    uint8_t positive;
} FlyBrain64Edge;

/*
 * The rows connect each required population: sensory inputs feed the central
 * complex and association layer; modulation and identity form sparse motifs;
 * action cells collect the resulting drives.  Power, cardiac, and motion are
 * addressed through their population IDs (6-11) by fly_brain64_input_drive.
 */
static const FlyBrain64Edge fly_brain64_edges[] = {
    {  0u, 12u, 2u, 1u }, {  1u, 14u, 2u, 1u },
    {  2u, 16u, 2u, 1u }, {  3u, 18u, 2u, 1u },
    {  4u, 20u, 2u, 1u }, {  5u, 22u, 3u, 1u },
    {  6u, 13u, 3u, 1u }, {  7u, 15u, 3u, 1u },
    {  8u, 17u, 3u, 1u }, {  9u, 19u, 3u, 1u },
    { 10u, 21u, 3u, 1u }, { 11u, 23u, 3u, 1u },

    { 12u, 13u, 3u, 1u }, { 13u, 14u, 3u, 1u },
    { 14u, 15u, 3u, 1u }, { 15u, 16u, 3u, 1u },
    { 16u, 17u, 3u, 1u }, { 17u, 18u, 3u, 1u },
    { 18u, 19u, 3u, 1u }, { 19u, 20u, 3u, 1u },
    { 20u, 21u, 3u, 1u }, { 21u, 22u, 3u, 1u },
    { 22u, 23u, 3u, 1u }, { 23u, 12u, 3u, 1u },
    { 12u, 18u, 4u, 0u }, { 13u, 19u, 4u, 0u },
    { 14u, 20u, 4u, 0u }, { 15u, 21u, 4u, 0u },
    { 16u, 22u, 4u, 0u }, { 17u, 23u, 4u, 0u },

    { 12u, 24u, 3u, 1u }, { 13u, 25u, 3u, 1u },
    { 14u, 26u, 3u, 1u }, { 15u, 27u, 3u, 1u },
    { 16u, 28u, 3u, 1u }, { 17u, 29u, 3u, 1u },
    { 18u, 30u, 3u, 1u }, { 19u, 31u, 3u, 1u },
    { 20u, 32u, 3u, 1u }, { 21u, 33u, 3u, 1u },
    { 22u, 34u, 3u, 1u }, { 23u, 35u, 3u, 1u },
    { 24u, 36u, 4u, 1u }, { 27u, 39u, 4u, 1u },
    { 30u, 24u, 5u, 0u }, { 33u, 27u, 5u, 0u },
    { 36u, 30u, 4u, 1u }, { 39u, 33u, 4u, 1u },
    { 25u, 37u, 4u, 1u }, { 28u, 34u, 4u, 1u },
    { 31u, 25u, 5u, 0u }, { 34u, 28u, 5u, 0u },
    { 37u, 31u, 4u, 1u }, { 38u, 35u, 4u, 1u },

    { 24u, 40u, 4u, 1u }, { 27u, 41u, 4u, 0u },
    { 30u, 42u, 4u, 1u }, { 33u, 43u, 4u, 1u },
    { 36u, 44u, 4u, 1u }, { 39u, 45u, 4u, 1u },
    { 26u, 46u, 4u, 1u }, { 35u, 47u, 4u, 1u },
    { 40u, 48u, 4u, 1u }, { 41u, 49u, 4u, 1u },
    { 42u, 50u, 4u, 1u }, { 43u, 51u, 4u, 1u },
    { 44u, 52u, 4u, 1u }, { 45u, 53u, 4u, 1u },
    { 46u, 54u, 4u, 1u }, { 47u, 55u, 4u, 1u },
    { 48u, 52u, 5u, 1u }, { 49u, 53u, 5u, 0u },
    { 50u, 54u, 5u, 1u }, { 51u, 55u, 5u, 0u },

    { 48u, 56u, 3u, 1u }, { 49u, 57u, 3u, 1u },
    { 50u, 58u, 3u, 1u }, { 51u, 59u, 3u, 1u },
    { 52u, 60u, 3u, 1u }, { 53u, 61u, 3u, 1u },
    { 54u, 62u, 3u, 1u }, { 55u, 63u, 3u, 1u },
    { 56u, 49u, 5u, 1u }, { 57u, 50u, 5u, 1u },
    { 58u, 51u, 5u, 1u }, { 59u, 52u, 5u, 1u },
    { 60u, 53u, 5u, 1u }, { 61u, 54u, 5u, 1u },
    { 62u, 55u, 5u, 1u }, { 63u, 48u, 5u, 1u }
};

static uint32_t fly_brain64_xorshift32(uint32_t *state) {
    uint32_t value = *state;

    value ^= value << 13;
    value ^= value >> 17;
    value ^= value << 5;
    *state = value;
    return value;
}

static int16_t fly_brain64_clamp(int32_t value) {
    if (value > FLY_BRAIN64_MAXIMUM) return FLY_BRAIN64_MAXIMUM;
    if (value < FLY_BRAIN64_MINIMUM) return FLY_BRAIN64_MINIMUM;
    return (int16_t)value;
}

static int32_t fly_brain64_absolute(int16_t value) {
    int32_t wide = value;

    if (wide < 0) return -wide;
    return wide;
}

/* Defined floor division by a power of two for signed Q5.10 values. */
static int32_t fly_brain64_scale_shift(int16_t value, uint8_t shift) {
    int32_t wide = value;

    if (wide >= 0) return wide >> shift;
    return -((-wide + (int32_t)((1u << shift) - 1u)) >> shift);
}

/* A 64-epoch triangular RTC phase cycle, expressed directly in Q5.10. */
static int32_t fly_brain64_phase_drive(uint32_t epoch) {
    uint32_t phase = epoch & 0x3fu;

    if (phase < 16u) return (int32_t)phase * 128;
    if (phase < 32u) return (int32_t)(32u - phase) * 128;
    if (phase < 48u) return -(int32_t)(phase - 32u) * 128;
    return -(int32_t)(64u - phase) * 128;
}

static int32_t fly_brain64_input_drive(const FlyBrainInputs *inputs,
                                       unsigned neuron) {
    int32_t drive = 0;

    if (neuron < 5u && (inputs->buttons & (uint8_t)(1u << neuron)) != 0u) {
        drive += FLY_BRAIN64_BUTTON_DRIVE;
    }
    if ((inputs->valid_mask & FLY_BRAIN64_VALID_CHARGING) != 0u &&
        neuron == 6u && inputs->charging != 0u) {
        drive += 4096;
    }
    if ((inputs->valid_mask & FLY_BRAIN64_VALID_BATTERY) != 0u && neuron == 7u) {
        drive += (int32_t)inputs->battery_percent * 32;
    }
    if ((inputs->valid_mask & FLY_BRAIN64_VALID_HEART_RATE) != 0u) {
        if (neuron == 8u) drive += (int32_t)inputs->heart_rate_bpm * 16;
        if (neuron == 9u) drive += (int32_t)inputs->heart_rate_delta * 32;
    }
    if ((inputs->valid_mask & FLY_BRAIN64_VALID_MOTION) != 0u) {
        if (neuron == 10u) drive += (int32_t)inputs->motion / 8;
        if (neuron == 11u) drive -= (int32_t)inputs->motion / 16;
    }
    return drive;
}

static void fly_brain64_update_state(FlyBrain64 *brain) {
    int32_t movement = fly_brain64_absolute(brain->activation[58]);
    int32_t arousal = fly_brain64_absolute(brain->activation[63]);
    int32_t quiet = fly_brain64_absolute(brain->activation[61]);

    brain->state = FLY_BRAIN64_STATE_REST;
    if (movement >= 512 && movement >= arousal && movement >= quiet) {
        brain->state = FLY_BRAIN64_STATE_MOVEMENT;
    } else if (arousal >= 512 && arousal >= quiet) {
        brain->state = FLY_BRAIN64_STATE_AROUSAL;
    } else if (quiet >= 512) {
        brain->state = FLY_BRAIN64_STATE_QUIET;
    }
}

void fly_brain64_seed(FlyBrain64 *brain, uint32_t identity_seed, uint32_t epoch) {
    uint32_t seed = identity_seed ^ (epoch << 16) ^ (epoch >> 7) ^ 0x9e3779b9u;

    if (seed == 0u) seed = 0x6d2b79f5u;
    brain->rng_state = seed;
    brain->epoch = epoch;
    brain->state = FLY_BRAIN64_STATE_REST;
    brain->reserved[0] = 0u;
    brain->reserved[1] = 0u;
    brain->reserved[2] = 0u;

    for (unsigned neuron = 0u; neuron < FLY_BRAIN64_NEURONS; ++neuron) {
        uint32_t sample = fly_brain64_xorshift32(&brain->rng_state);
        int32_t value = (int32_t)(sample & 0x1ffu) - 256;

        if (neuron >= 40u && neuron <= 47u) {
            value = (int32_t)(sample & 0x7ffu) - 1024;
            value += value;
        }
        brain->activation[neuron] = fly_brain64_clamp(value);
    }
    fly_brain64_update_state(brain);
}

void fly_brain64_step(FlyBrain64 *brain, const FlyBrainInputs *inputs) {
    int16_t previous[FLY_BRAIN64_NEURONS];

    for (unsigned neuron = 0u; neuron < FLY_BRAIN64_NEURONS; ++neuron) {
        previous[neuron] = brain->activation[neuron];
    }

    for (unsigned target = 0u; target < FLY_BRAIN64_NEURONS; ++target) {
        int32_t next = fly_brain64_scale_shift(previous[target], 1u) +
                       fly_brain64_scale_shift(previous[target], 2u) +
                       fly_brain64_input_drive(inputs, target);

        if (target == 5u) next += fly_brain64_phase_drive(brain->epoch);

        for (unsigned edge = 0u;
             edge < (unsigned)(sizeof(fly_brain64_edges) /
                               sizeof(fly_brain64_edges[0]));
             ++edge) {
            const FlyBrain64Edge *connection = &fly_brain64_edges[edge];

            if (connection->target == target) {
                int32_t contribution = fly_brain64_scale_shift(
                    previous[connection->source], connection->shift);
                if (connection->positive != 0u) next += contribution;
                else next -= contribution;
            }
        }
        next += (int32_t)(fly_brain64_xorshift32(&brain->rng_state) & 0x1fu) - 16;
        brain->activation[target] = fly_brain64_clamp(next);
    }

    ++brain->epoch;
    fly_brain64_update_state(brain);
}

void fly_brain64_reconstruct(FlyBrain64 *brain, uint32_t identity_seed,
                             uint32_t rtc_tick, const FlyBrainInputs *inputs) {
    uint32_t epoch = rtc_tick >> 3;
    unsigned steps = (unsigned)(rtc_tick & 0x7u) + 1u;

    fly_brain64_seed(brain, identity_seed, epoch);
    for (unsigned step = 0u; step < steps; ++step) {
        fly_brain64_step(brain, inputs);
    }
}

uint8_t fly_brain64_level(const FlyBrain64 *brain, unsigned neuron) {
    int32_t magnitude;

    if (neuron >= FLY_BRAIN64_NEURONS) return FLY_BRAIN64_LEVEL_DOT;
    magnitude = fly_brain64_absolute(brain->activation[neuron]);
    if (magnitude < 128) return FLY_BRAIN64_LEVEL_DOT;
    if (magnitude < 256) return FLY_BRAIN64_LEVEL_SMALL_O;
    if (magnitude < 512) return FLY_BRAIN64_LEVEL_LARGE_O;
    return FLY_BRAIN64_LEVEL_AT;
}

uint8_t fly_brain64_state(const FlyBrain64 *brain) {
    return brain->state;
}
