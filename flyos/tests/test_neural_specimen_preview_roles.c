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

static uint8_t cell_center(const uint8_t framebuffer[], unsigned neuron) {
    const FlyNeuralSpecimenPoint *cell = &fly_neural_specimen_points[neuron];
    return framebuffer[((unsigned)cell->y + 3u) * FLY_NEURAL_SPECIMEN_WIDTH +
                       (unsigned)cell->x + 3u];
}

int main(void) {
    uint8_t framebuffer[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES];
    FlyBrain64 brain = {0};
    const FlyBrainInputs inputs = {0};

    brain.activation[0] = 512;
    brain.activation[1] = -512;
    brain.activation[56] = 512;
    fly_neural_specimen_render(framebuffer, &brain, &inputs, 0u);
    CHECK(cell_center(framebuffer, 0u) == FLY_NEURAL_SPECIMEN_EXCITATORY);
    CHECK(cell_center(framebuffer, 1u) == FLY_NEURAL_SPECIMEN_INHIBITORY);
    CHECK(cell_center(framebuffer, 56u) == FLY_NEURAL_SPECIMEN_SATURATED);
    CHECK(FLY_NEURAL_SPECIMEN_EXCITATORY != FLY_NEURAL_SPECIMEN_INHIBITORY);
    CHECK(FLY_NEURAL_SPECIMEN_SATURATED != FLY_NEURAL_SPECIMEN_EXCITATORY);
    puts("neural specimen preview role tests: ok");
    return EXIT_SUCCESS;
}
