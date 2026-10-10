#include "sim/live_bridge.h"
#include "sim/host_policy.h"
#include "display/neural_specimen.h"

#ifndef FLY_NEURAL_SPECIMEN_HOST_PREVIEW
#error "live_bridge is host-only and requires FLY_NEURAL_SPECIMEN_HOST_PREVIEW"
#endif

/* All mutable state belongs to this synthetic host instance. No target memory
 * locations, target callbacks, devices, filesystem or external services. */
typedef struct {
    FlyBrain64 brain;
    FlyBrainInputs sensors;
    FlySimKeys keys;
    FlySimInputContext context;
    uint8_t pixels[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES];
    uint8_t pending_pulse;
    uint8_t delivered_pulse;
    uint8_t rendered;
    int last_route;
} FlyLiveLab;

static FlyLiveLab lab;

void fly_lab_reset(uint32_t seed) {
    lab = (FlyLiveLab){0};
    lab.context = (FlySimInputContext){FLY_SIM_VIEW_HOME, false, true};
    lab.last_route = -1;
    fly_sim_keys_init(&lab.keys);
    fly_brain64_seed(&lab.brain, seed, 0u);
    fly_neural_specimen_render(lab.pixels, &lab.brain, &lab.sensors, 0u);
    lab.rendered = 1u;
}

int fly_lab_event(int key, int phase) {
    if (key < 0 || key >= (int)FLY_SIM_KEY_COUNT ||
        phase < (int)FLY_SIM_PRESS || phase > (int)FLY_SIM_RELEASE) {
        lab.last_route = FLY_SIM_ROUTE_REJECTED;
        return lab.last_route;
    }
    lab.last_route = (int)fly_sim_key_event(&lab.keys, (unsigned)key,
        (FlySimKeyPhase)phase, &lab.context);
    if (phase == (int)FLY_SIM_RELEASE && lab.last_route == FLY_SIM_ROUTE_FLYOS)
        lab.pending_pulse |= (uint8_t)(1u << (unsigned)key);
    return lab.last_route;
}

int fly_lab_set_context(int view, int usb, int ready) {
    if (view < FLY_SIM_VIEW_INVALID || view > FLY_SIM_VIEW_NATIVE ||
        (usb != 0 && usb != 1) || (ready != 0 && ready != 1)) return 0;
    lab.context.view = (FlySimView)view;
    lab.context.usb_mass_storage = usb != 0;
    lab.context.input_ready = ready != 0;
    return 1;
}

int fly_lab_set_sensors(int mask, int bpm, int delta, int motion,
                        int battery, int charging) {
    if (mask < 0 || mask > 15 || bpm < 0 || bpm > 300 ||
        delta < -300 || delta > 300 || motion < -32768 || motion > 32767 ||
        battery < 0 || battery > 100 || (charging != 0 && charging != 1)) return 0;
    lab.sensors.valid_mask = (uint8_t)mask;
    lab.sensors.heart_rate_bpm = (mask & FLY_BRAIN64_VALID_HEART_RATE) ? (uint16_t)bpm : 0u;
    lab.sensors.heart_rate_delta = (mask & FLY_BRAIN64_VALID_HEART_RATE) ? (int16_t)delta : 0;
    lab.sensors.motion = (mask & FLY_BRAIN64_VALID_MOTION) ? (int16_t)motion : 0;
    lab.sensors.battery_percent = (mask & FLY_BRAIN64_VALID_BATTERY) ? (uint8_t)battery : 0u;
    lab.sensors.charging = (mask & FLY_BRAIN64_VALID_CHARGING) ? (uint8_t)charging : 0u;
    return 1;
}

void fly_lab_step(void) {
    const uint32_t tick = lab.brain.epoch;
    lab.rendered = (uint8_t)(lab.context.view == FLY_SIM_VIEW_HOME &&
                            !lab.context.usb_mass_storage);
    lab.delivered_pulse = lab.rendered ? lab.pending_pulse : 0u;
    lab.sensors.buttons = lab.keys.flyos_held | lab.delivered_pulse;
    fly_brain64_step(&lab.brain, &lab.sensors);
    fly_neural_specimen_render_if_home(lab.pixels, lab.rendered,
                                       &lab.brain, &lab.sensors, tick);
    if (lab.rendered) lab.pending_pulse = 0u;
}

const uint8_t *fly_lab_pixels(void) { return lab.pixels; }
const int16_t *fly_lab_activations(void) { return lab.brain.activation; }
uint32_t fly_lab_pixel_count(void) { return FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES; }
uint32_t fly_lab_neuron_count(void) { return FLY_BRAIN64_NEURONS; }
int fly_lab_route(void) { return lab.last_route; }
uint32_t fly_lab_held(void) { return lab.keys.flyos_held; }
uint32_t fly_lab_active(void) {
    uint32_t mask = 0u;
    for (unsigned key = 0u; key < FLY_SIM_KEY_COUNT; ++key)
        if (lab.keys.active[key]) mask |= 1u << key;
    return mask;
}
int fly_lab_owner(int key) {
    return key < 0 || key >= (int)FLY_SIM_KEY_COUNT ? FLY_SIM_ROUTE_REJECTED :
           (int)lab.keys.owner[key];
}
uint32_t fly_lab_pulse(void) { return lab.pending_pulse; }
uint32_t fly_lab_delivered_pulse(void) { return lab.delivered_pulse; }
uint32_t fly_lab_buttons(void) { return lab.sensors.buttons; }
uint32_t fly_lab_state(void) { return lab.brain.state; }
uint32_t fly_lab_epoch(void) { return lab.brain.epoch; }
uint32_t fly_lab_view(void) { return (uint32_t)lab.context.view; }
uint32_t fly_lab_usb(void) { return (uint32_t)lab.context.usb_mass_storage; }
uint32_t fly_lab_ready(void) { return (uint32_t)lab.context.input_ready; }
uint32_t fly_lab_valid_mask(void) { return lab.sensors.valid_mask; }
uint32_t fly_lab_rendered(void) { return lab.rendered; }
