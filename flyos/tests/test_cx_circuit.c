#include "sim/cx_circuit.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #c); exit(1); } } while (0)

static void check_bound(const FlyCxCircuit *circuit) {
    for (unsigned n = 0; n < FLY_CX_UNITS; ++n)
        CHECK(circuit->activation[n] >= 0 && circuit->activation[n] <= FLY_CX_MAXIMUM);
    for (unsigned n = FLY_CX_UNITS; n < FLY_CX_SLOTS; ++n)
        CHECK(circuit->activation[n] == 0);
}
static void test_quiescence(void) {
    FlyCxCircuit circuit;
    FlyCxInputs inputs = {0};
    fly_cx_reset(&circuit);
    for (unsigned n = 0; n < 100; ++n) fly_cx_step(&circuit, &inputs);
    for (unsigned n = 0; n < FLY_CX_SLOTS; ++n) CHECK(circuit.activation[n] == 0);
    CHECK(circuit.epoch == 100u);
    CHECK(fly_cx_heading(&circuit) == -1 && fly_cx_strength(&circuit) == 0);
}
static void test_published_input_populations(void) {
    FlyCxCircuit circuit;
    FlyCxInputs inputs = {0, 1024, 0};
    fly_cx_reset(&circuit);
    fly_cx_step(&circuit, &inputs);
    for (unsigned n = 0; n < FLY_CX_UNITS; ++n)
        if (n < 34u || n > 51u) CHECK(circuit.activation[n] == 0);
    CHECK(circuit.activation[34] == 2048 && circuit.activation[42] == 2048);
    CHECK(circuit.activation[43] == 2048 && circuit.activation[51] == 2048);
    CHECK(fly_cx_heading(&circuit) == 0);
    fly_cx_reset(&circuit);
    inputs = (FlyCxInputs){0, 0, 1024};
    fly_cx_step(&circuit, &inputs);
    for (unsigned n = 0; n < FLY_CX_UNITS; ++n)
        CHECK(circuit.activation[n] == (n < 8u ? 1024 : 0));
    fly_cx_reset(&circuit);
    inputs.turn_drive = -1024;
    fly_cx_step(&circuit, &inputs);
    for (unsigned n = 0; n < FLY_CX_UNITS; ++n)
        CHECK(circuit.activation[n] == (n >= 8u && n < 16u ? 1024 : 0));
}
static void test_cue_tracking_and_dark_decay(void) {
    FlyCxCircuit circuit;
    FlyCxInputs inputs = {0, 768, 0};
    fly_cx_reset(&circuit);
    for (int angle = 0; angle < 360; angle += 45) {
        inputs.cue_degrees = (int16_t)angle;
        for (unsigned step = 0; step < 120; ++step) {
            fly_cx_step(&circuit, &inputs);
            check_bound(&circuit);
            for (unsigned n = 0; n < FLY_CX_UNITS; ++n)
                CHECK(circuit.activation[n] < FLY_CX_MAXIMUM);
        }
        CHECK(fly_cx_heading(&circuit) == angle);
        CHECK(fly_cx_strength(&circuit) > 0);
    }
    inputs = (FlyCxInputs){0};
    for (unsigned step = 0; step < 240; ++step) fly_cx_step(&circuit, &inputs);
    CHECK(fly_cx_strength(&circuit) == 0);
}
static void test_extreme_drive_and_determinism(void) {
    FlyCxCircuit a, b;
    fly_cx_reset(&a); fly_cx_reset(&b);
    for (unsigned step = 0; step < 2000; ++step) {
        FlyCxInputs inputs = {(int16_t)(step % 360u), 1024,
                              (int16_t)((step & 1u) ? 1024 : -1024)};
        fly_cx_step(&a, &inputs); fly_cx_step(&b, &inputs);
        CHECK(memcmp(&a, &b, sizeof(a)) == 0);
        check_bound(&a);
    }
}
static void test_duplicate_sectors_are_averaged(void) {
    FlyCxCircuit circuit;
    fly_cx_reset(&circuit);
    circuit.activation[34] = 100; circuit.activation[42] = 100;
    circuit.activation[43] = 100; circuit.activation[51] = 100;
    circuit.activation[35] = 150; circuit.activation[44] = 150;
    CHECK(fly_cx_heading(&circuit) == 45);
    CHECK(fly_cx_strength(&circuit) == 150);
}
int main(void) {
    test_quiescence(); test_published_input_populations();
    test_cue_tracking_and_dark_decay(); test_extreme_drive_and_determinism();
    test_duplicate_sectors_are_averaged();
    puts("CX topology explorer: input mapping, cue tracking, decay, duplicate normalization, bounds and determinism passed");
    return 0;
}
