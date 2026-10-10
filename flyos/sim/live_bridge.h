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

void fly_lab_reset(uint32_t seed);
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
 * Held FlyOS keys retain ownership and drive the brain across context changes.
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
