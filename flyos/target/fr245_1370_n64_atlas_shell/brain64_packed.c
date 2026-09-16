#include "fly/brain64.h"

#define FLY_BRAIN64_MINIMUM (-16384)
#define FLY_BRAIN64_MAXIMUM 16383
#define FLY_BRAIN64_BUTTON_DRIVE 4096

typedef uint16_t FlyBrain64Edge;

/*
 * The rows connect each required population: sensory inputs feed the central
 * complex and association layer; modulation and identity form sparse motifs;
 * action cells collect the resulting drives.  Power, cardiac, and motion are
 * addressed through their population IDs (6-11) by fly_brain64_input_drive.
 */
static const FlyBrain64Edge fly_brain64_edges[] = {
    0xa300u, 0xa381u, 0xa402u, 0xa483u, 0xa504u, 0xb585u, 0xb346u, 0xb3c7u, 0xb448u, 0xb4c9u,
    0xb54au, 0xb5cbu, 0xb34cu, 0xb38du, 0xb3ceu, 0xb40fu, 0xb450u, 0xb491u, 0xb4d2u, 0xb513u,
    0xb554u, 0xb595u, 0xb5d6u, 0xb317u, 0x448cu, 0x44cdu, 0x450eu, 0x454fu, 0x4590u, 0x45d1u,
    0xb60cu, 0xb64du, 0xb68eu, 0xb6cfu, 0xb710u, 0xb751u, 0xb792u, 0xb7d3u, 0xb814u, 0xb855u,
    0xb896u, 0xb8d7u, 0xc918u, 0xc9dbu, 0x561eu, 0x56e1u, 0xc7a4u, 0xc867u, 0xc959u, 0xc89cu,
    0x565fu, 0x5722u, 0xc7e5u, 0xc8e6u, 0xca18u, 0x4a5bu, 0xca9eu, 0xcae1u, 0xcb24u, 0xcb67u,
    0xcb9au, 0xcbe3u, 0xcc28u, 0xcc69u, 0xccaau, 0xccebu, 0xcd2cu, 0xcd6du, 0xcdaeu, 0xcdefu,
    0xdd30u, 0x5d71u, 0xddb2u, 0x5df3u, 0xbe30u, 0xbe71u, 0xbeb2u, 0xbef3u, 0xbf34u, 0xbf75u,
    0xbfb6u, 0xbff7u, 0xdc78u, 0xdcb9u, 0xdcfau, 0xdd3bu, 0xdd7cu, 0xddbdu, 0xddfeu, 0xdc3fu
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
            FlyBrain64Edge connection = fly_brain64_edges[edge];

            if (((connection >> 6) & 63u) == target) {
                int32_t contribution = fly_brain64_scale_shift(
                    previous[connection & 63u],
                    (uint8_t)((connection >> 12) & 7u));
                if ((connection & 0x8000u) != 0u) next += contribution;
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
