#include "display/n64_atlas_layout.h"
#include "display/neural_specimen.h"

#include <stdio.h>
#include <stdlib.h>

#define CHECK(condition)                                                        \
    do {                                                                        \
        if (!(condition)) {                                                     \
            fprintf(stderr, "check failed: %s (%s:%d)\n", #condition,         \
                    __FILE__, __LINE__);                                        \
            exit(EXIT_FAILURE);                                                 \
        }                                                                       \
    } while (0)

static uint8_t mask_centre(const uint8_t framebuffer[], unsigned neuron) {
    FlyN64AtlasPoint point = fly_n64_atlas_point(neuron);

    return framebuffer[((unsigned)point.y + 2u) * FLY_NEURAL_SPECIMEN_WIDTH +
                       (unsigned)point.x + 2u];
}

int main(void) {
    static uint8_t framebuffer[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES];
    FlyBrain64 brain = {0};
    const FlyBrainInputs inputs = {0};

    brain.activation[0] = 512;
    brain.activation[1] = -512;
    brain.activation[56] = 512;
    fly_neural_specimen_render(framebuffer, &brain, &inputs, 0u);
    CHECK(mask_centre(framebuffer, 0u) == FLY_NEURAL_SPECIMEN_EXCITATORY);
    CHECK(mask_centre(framebuffer, 1u) == FLY_NEURAL_SPECIMEN_INHIBITORY);
    CHECK(mask_centre(framebuffer, 56u) == FLY_NEURAL_SPECIMEN_SATURATED);
    CHECK(fly_n64_atlas_population(56u) == FLY_N64_POPULATION_ACTION_FAN);
    CHECK(FLY_NEURAL_SPECIMEN_EXCITATORY != FLY_NEURAL_SPECIMEN_INHIBITORY);
    CHECK(FLY_NEURAL_SPECIMEN_SATURATED != FLY_NEURAL_SPECIMEN_EXCITATORY);
    puts("neural specimen preview role tests: ok");
    return EXIT_SUCCESS;
}
