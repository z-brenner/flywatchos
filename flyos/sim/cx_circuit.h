#ifndef FLYOS_SIM_CX_CIRCUIT_H
#define FLYOS_SIM_CX_CIRCUIT_H
/* HOST-ONLY published-topology explorer. Not a target ABI or biological fit. */
#include <stdint.h>
#define FLY_CX_UNITS 60u
#define FLY_CX_SLOTS 64u
#define FLY_CX_SCALE 1024
#define FLY_CX_MAXIMUM 16383

/* Core input precondition: angle0..359, strength0..1024, turn -1024..1024.
 * The public live bridge validates atomically before invoking this core. */
typedef struct {
    int16_t cue_degrees;
    int16_t cue_strength;
    int16_t turn_drive;
} FlyCxInputs;
typedef struct {
    int16_t activation[FLY_CX_SLOTS];
    uint32_t epoch;
} FlyCxCircuit;
void fly_cx_reset(FlyCxCircuit *circuit);
void fly_cx_step(FlyCxCircuit *circuit, const FlyCxInputs *inputs);
void fly_cx_render(uint8_t *pixels, const FlyCxCircuit *circuit);
int fly_cx_heading(const FlyCxCircuit *circuit);
int fly_cx_strength(const FlyCxCircuit *circuit);
uint32_t fly_cx_edge_count(void);
int fly_cx_edge_source(int edge);
int fly_cx_edge_target(int edge);
double fly_cx_edge_raw_weight(int edge);
int fly_cx_edge_sign(int edge);
int fly_cx_edge_weight_q(int edge);
#endif
