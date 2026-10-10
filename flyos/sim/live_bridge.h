#ifndef FLYOS_SIM_LIVE_BRIDGE_H
#define FLYOS_SIM_LIVE_BRIDGE_H

/* HOST-ONLY synthetic interactive fixture. Never link into watch firmware.
 * This single bounded instance wraps the portable C brain, renderer, and key
 * policy. Context is explicitly supplied, not discovered from any device.
 * No allocation, I/O, wall clock, redraw queue, hardware or target API exists.
 * The browser must call reset before interacting and validate JS numbers as
 * integers before invoking WebAssembly (its i32 arguments coerce JS numbers).
 */
#include <stdint.h>

enum { FLY_LAB_MODEL_BRAIN64 = 0, FLY_LAB_MODEL_CX = 1 };
/* Starts a new host session. Invalid model leaves the entire session intact.
 * Legacy reset(seed) always selects the exact original Brain64 baseline. */
void fly_lab_reset(uint32_t seed);
int fly_lab_reset_model(int model, uint32_t seed);
uint32_t fly_lab_model(void);
/* Actual model units; neuron_count remains the stable 64-slot buffer width. */
uint32_t fly_lab_model_node_count(void);
/* Synthetic, dimensionless circuit input. These are not watch sensors or
 * measured visual/rotation signals. angle 0..359 degrees; strength 0..1024;
 * turn -1024..1024. Invalid calls leave all fields unchanged. Brain64 stores
 * but ignores these inputs; the alternate circuit ignores watch inputs. */
int fly_lab_set_stimulus(int cue_degrees, int cue_strength, int turn_drive);
int fly_lab_stimulus_angle(void);
int fly_lab_stimulus_strength(void);
int fly_lab_stimulus_turn(void);
/* Coarse strongest E-PG sector, not a calibrated behavioral estimate.
 * Heading is -1 for the baseline or a quiescent circuit; strength is the
 * winning sector mean in Q10 arbitrary model activity, not Hz. */
int fly_lab_readout_heading(void);
int fly_lab_readout_strength(void);
/* key: LIGHT=0, START=1, BACK=2, DOWN=3, UP=4.
 * phase: press=0, repeat=1, release=2. Returns 0 rejected, 1 native, 2 FlyOS.
 * Most recent route persists until another event or reset (-1).
 */
int fly_lab_event(int key, int phase);
/* view: invalid=0, HOME=1, native=2; usb and ready must be exactly 0 or 1.
 * Invalid calls return 0 and change nothing. Success returns 1.
 */
int fly_lab_set_context(int view, int usb, int ready);
/* mask uses FlyBrainInputs availability bits (0..15). All values, even for
 * unavailable inputs, are validated before mutation: bpm 0..300, delta
 * -300..300, motion -32768..32767, battery 0..100, charging 0 or 1. These are
 * fixture bounds, not sensor specifications or medical interpretation.
 * Unavailable values are cleared; mask=0 with zero values clears all sensors.
 */
int fly_lab_set_sensors(int mask, int bpm, int delta, int motion,
                        int battery, int charging);
/* Each call advances the real C brain once; it is not a physical clock tick.
 * Only HOME and !USB permits rendering and consumes a pending release pulse.
 * Native/invalid/USB steps preserve framebuffer and pending release pulses.
 * Held FlyOS keys retain ownership across context changes and drive Brain64.
 * CX60 uses only its separate circuit stimulus, regardless of watch inputs.
 */
void fly_lab_step(void);

/* Stable pointers; Wasm exposes byte offsets into exported linear memory.
 * pixels: 240*240 uint8_t semantic role indices, 0..5 (host preview build).
 * activations: 64 signed int16_t entries. Read only; callers must not write.
 */
const uint8_t *fly_lab_pixels(void);
const int16_t *fly_lab_activations(void);
uint32_t fly_lab_pixel_count(void);
uint32_t fly_lab_neuron_count(void);
/* Exact active C graph, never copied into JavaScript. Invalid index yields
 * endpoints -1 and weight/denominator/sign 0. Magnitudes are raw/denominator;
 * sign is +1 or -1. Baseline uses sign*floor(activation/denominator), with
 * raw=1. Edge provenance and alternative-model arithmetic are documented in
 * circuit_models.json. No edge weight claims a measured physiological gain. */
uint32_t fly_lab_edge_count(void);
int fly_lab_edge_source(int edge);
int fly_lab_edge_target(int edge);
double fly_lab_edge_raw_weight(int edge);
/* Signed implemented coefficient in Q10, including adaptation rounding. */
int fly_lab_edge_weight_q(int edge);
int fly_lab_edge_denominator(int edge);
int fly_lab_edge_sign(int edge);
int fly_lab_route(void);
uint32_t fly_lab_held(void);
uint32_t fly_lab_active(void);
int fly_lab_owner(int key);
uint32_t fly_lab_pulse(void);
uint32_t fly_lab_delivered_pulse(void);
uint32_t fly_lab_buttons(void);
uint32_t fly_lab_state(void);
uint32_t fly_lab_epoch(void);
uint32_t fly_lab_view(void);
uint32_t fly_lab_usb(void);
uint32_t fly_lab_ready(void);
uint32_t fly_lab_valid_mask(void);
uint32_t fly_lab_rendered(void);

#endif
