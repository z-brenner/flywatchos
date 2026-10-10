/* Host-only traces. Calls the real portable neuron model and C renderer.
 * No private firmware, target addresses, device paths or native calls. */
#include "display/neural_specimen.h"
#include "sim/host_policy.h"

#include <stdio.h>
#include <string.h>

typedef struct {
    FlySimKeys keys;
    FlySimRedraw redraw;
    FlySimInputContext input;
    FlySimRedrawContext callback;
    FlySimRedrawSubmission submission;
    FlyBrain64 brain;
    FlyBrainInputs sensors;
    uint8_t framebuffer[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES];
    uint8_t pulse;
    unsigned tick;
    int route;
    bool completed;
    bool first_frame;
} Lab;

static const char *view_name(FlySimView view) {
    return view == FLY_SIM_VIEW_HOME ? "HOME" :
        view == FLY_SIM_VIEW_NATIVE ? "NON_HOME" : "INVALID";
}

static const char *route_name(int route) {
    return route < 0 ? "NONE" : route == FLY_SIM_ROUTE_FLYOS ? "FLYOS" :
        route == FLY_SIM_ROUTE_GARMIN ? "GARMIN" : "REJECTED";
}

static void reset(Lab *lab) {
    memset(lab, 0, sizeof(*lab));
    fly_sim_keys_init(&lab->keys);
    (void)fly_sim_redraw_init(&lab->redraw, false, 3u);
    lab->input = (FlySimInputContext){FLY_SIM_VIEW_HOME, false, true};
    lab->callback.view = FLY_SIM_VIEW_HOME;
    lab->callback.safe_callback = true;
    lab->callback.retry_due = true;
    lab->route = -1;
    lab->first_frame = true;
    lab->sensors.valid_mask = FLY_BRAIN64_VALID_BATTERY;
    lab->sensors.battery_percent = 87u;
    fly_brain64_seed(&lab->brain, 0x245f1a5u, 0u);
}

static void begin(Lab *lab, const char *id, const char *title,
                  const char *summary, bool first) {
    reset(lab);
    printf("%s{\"id\":\"%s\",\"title\":\"%s\",\"summary\":\"%s\",\"frames\":[",
           first ? "" : ",", id, title, summary);
}

static void frame(Lab *lab, const char *action, const char *detail) {
    const bool render_home = lab->input.view == FLY_SIM_VIEW_HOME &&
                             !lab->input.usb_mass_storage;
    lab->sensors.buttons = lab->keys.flyos_held | (render_home ? lab->pulse : 0u);
    fly_brain64_step(&lab->brain, &lab->sensors);
    fly_neural_specimen_render_if_home(lab->framebuffer,
        (uint8_t)(lab->input.view == FLY_SIM_VIEW_HOME && !lab->input.usb_mass_storage),
        &lab->brain, &lab->sensors, lab->tick);
    printf("%s{\"action\":\"%s\",\"detail\":\"%s\",\"tick\":%u,"
        "\"view\":\"%s\",\"route\":\"%s\",\"held_mask\":%u,\"pulse_mask\":%u,"
        "\"input_buttons\":%u,\"usb\":%s,\"redraw_pending\":%s,\"redraw_complete\":%s,"
        "\"redraw_exhausted\":%s,\"attempts\":%u,\"budget\":%u,"
        "\"epoch\":%llu,\"enqueued\":%s,\"safe_callback\":%s,"
        "\"source_locked\":%s,\"usb_locked\":%s,\"state\":%u,\"neurons\":[",
        lab->first_frame ? "" : ",", action, detail, lab->tick++,
        view_name(lab->input.view), route_name(lab->route), lab->keys.flyos_held,
        lab->pulse, lab->sensors.buttons, lab->input.usb_mass_storage ? "true" : "false",
        lab->redraw.pending ? "true" : "false", lab->completed ? "true" : "false",
        lab->redraw.exhausted ? "true" : "false", lab->redraw.attempts,
        lab->redraw.budget, (unsigned long long)lab->redraw.epoch,
        lab->submission.enqueued ? "true" : "false",
        lab->callback.safe_callback ? "true" : "false",
        lab->callback.source_mutex_locked ? "true" : "false",
        lab->callback.usb_mutex_locked ? "true" : "false", lab->brain.state);
    for (unsigned n = 0; n < FLY_BRAIN64_NEURONS; ++n)
        printf("%s%d", n ? "," : "", lab->brain.activation[n]);
    printf("],\"pixels\":[");
    for (unsigned start = 0; start < sizeof(lab->framebuffer);) {
        unsigned end = start + 1u;
        while (end < sizeof(lab->framebuffer) &&
               lab->framebuffer[end] == lab->framebuffer[start]) ++end;
        printf("%s[%u,%u]", start ? "," : "", lab->framebuffer[start], end - start);
        start = end;
    }
    printf("]}");
    lab->first_frame = false;
    lab->route = -1;
    if (lab->input.view == FLY_SIM_VIEW_HOME && !lab->input.usb_mass_storage)
        lab->pulse = 0;
    lab->submission = (FlySimRedrawSubmission){0};
}

static void key(Lab *lab, unsigned key_id, FlySimKeyPhase phase) {
    lab->route = (int)fly_sim_key_event(&lab->keys, key_id, phase, &lab->input);
    if (phase == FLY_SIM_RELEASE && lab->route == FLY_SIM_ROUTE_FLYOS)
        lab->pulse |= (uint8_t)(1u << key_id);
}

static void view(Lab *lab, FlySimView new_view) {
    lab->input.view = new_view;
    lab->callback.view = new_view;
}

static void usb(Lab *lab, bool attached) {
    fly_sim_redraw_usb(&lab->redraw, attached);
    lab->input.usb_mass_storage = attached;
    lab->callback.usb_mass_storage = attached;
    lab->completed = false;
}

static void submit(Lab *lab, bool accepted) {
    lab->submission = fly_sim_redraw_step(&lab->redraw, &lab->callback, accepted);
}

int main(int argc, char **argv) {
    Lab lab;
    FlySimRedrawToken old_token;
    (void)argv;
    if (argc != 1) {
        fputs("usage: flyos-interaction-exporter (JSON to stdout)\n", stderr);
        return 2;
    }
    printf("{\"schema\":1,\"scope\":\"host-only\",\"hardware_verified\":false,\"scenarios\":[");
    begin(&lab, "home-controls", "A tap that stays visible",
          "START, DOWN and UP keep their owner for a complete sequence. A released tap remains visible for one HOME frame.", true);
    frame(&lab, "HOME ready", "Real 64-neuron C model. Synthetic battery input; no live sensor data.");
    key(&lab, FLY_SIM_KEY_START, FLY_SIM_PRESS);
    frame(&lab, "START pressed", "Ownership is decided once at the beginning of this sequence.");
    key(&lab, FLY_SIM_KEY_START, FLY_SIM_RELEASE);
    frame(&lab, "START released", "The tap pulse survives release and is consumed by this HOME preview.");
    frame(&lab, "Pulse acknowledged", "The next HOME frame has no stale button pulse.");
    key(&lab, FLY_SIM_KEY_DOWN, FLY_SIM_PRESS);
    frame(&lab, "DOWN pressed", "A separate key can own its own independent sequence.");
    key(&lab, FLY_SIM_KEY_UP, FLY_SIM_PRESS);
    frame(&lab, "UP overlaps DOWN", "Both complete sequences remain owned by FlyOS.");
    key(&lab, FLY_SIM_KEY_DOWN, FLY_SIM_RELEASE);
    frame(&lab, "DOWN released", "Releasing DOWN does not release UP.");
    key(&lab, FLY_SIM_KEY_UP, FLY_SIM_RELEASE);
    frame(&lab, "UP released", "Both owners have returned to idle.");
    printf("]}");

    begin(&lab, "native-escape", "Keep the way out",
          "LIGHT remains native for backlight. BACK stays the system escape, and its chord routes fresh presses to Garmin.", false);
    frame(&lab, "HOME ready", "Conservative host policy preserves both native controls.");
    key(&lab, FLY_SIM_KEY_LIGHT, FLY_SIM_PRESS);
    frame(&lab, "LIGHT pressed", "Garmin owns LIGHT; the host does not claim to switch a real backlight.");
    key(&lab, FLY_SIM_KEY_LIGHT, FLY_SIM_RELEASE);
    frame(&lab, "LIGHT released", "The release follows the same native owner.");
    key(&lab, FLY_SIM_KEY_BACK, FLY_SIM_PRESS);
    frame(&lab, "BACK held", "System escape stays available.");
    key(&lab, FLY_SIM_KEY_START, FLY_SIM_PRESS);
    frame(&lab, "BACK + START", "A fresh START press while BACK is held selects Garmin.");
    key(&lab, FLY_SIM_KEY_BACK, FLY_SIM_RELEASE);
    frame(&lab, "BACK released first", "START does not switch owners when the chord ends.");
    key(&lab, FLY_SIM_KEY_START, FLY_SIM_RELEASE);
    frame(&lab, "START released", "The complete chord sequence remains native.");
    printf("]}");

    begin(&lab, "view-transition", "One press. One owner.",
          "A modal arriving during a held press must not split ownership. New presses in the modal stay native.", false);
    frame(&lab, "HOME ready", "A new sequence starts on a valid HOME snapshot.");
    key(&lab, FLY_SIM_KEY_START, FLY_SIM_PRESS);
    frame(&lab, "START pressed", "FlyOS owns the whole sequence.");
    view(&lab, FLY_SIM_VIEW_NATIVE);
    key(&lab, FLY_SIM_KEY_START, FLY_SIM_REPEAT);
    frame(&lab, "Modal interrupts hold", "The held sequence keeps its owner; the renderer leaves native framebuffer contents untouched.");
    key(&lab, FLY_SIM_KEY_UP, FLY_SIM_PRESS);
    frame(&lab, "UP begins in modal", "A fresh press belongs to Garmin on a native view.");
    key(&lab, FLY_SIM_KEY_START, FLY_SIM_RELEASE);
    frame(&lab, "START ends in modal", "No orphan release is delivered to Garmin. The short-tap pulse waits for HOME.");
    frame(&lab, "Modal still visible", "The release pulse remains pending without injecting repeated neural drive.");
    view(&lab, FLY_SIM_VIEW_HOME);
    key(&lab, FLY_SIM_KEY_UP, FLY_SIM_RELEASE);
    frame(&lab, "HOME returns", "UP still ends with Garmin; the pending FlyOS pulse is now shown once.");
    frame(&lab, "Clean next frame", "No stuck key or repeated pulse remains.");
    printf("]}");

    begin(&lab, "usb-detach", "A redraw is a promise",
          "A detach creates pending work. Unsafe callbacks and native views cannot spend the retry budget. Enqueued does not mean displayed.", false);
    frame(&lab, "HOME ready", "This models ordering only; it does not fix the observed ten-second hardware delay.");
    usb(&lab, true); view(&lab, FLY_SIM_VIEW_NATIVE);
    frame(&lab, "USB attached", "Native USB view is preserved.");
    usb(&lab, false); submit(&lab, true);
    frame(&lab, "Detached; modal remains", "Pending survives. No native view is dismissed or repainted by FlyOS.");
    view(&lab, FLY_SIM_VIEW_HOME); lab.callback.source_mutex_locked = true; submit(&lab, true);
    frame(&lab, "Source mutex still held", "No queue call is modeled while either mutex is held.");
    lab.callback.source_mutex_locked = false; lab.callback.safe_callback = false; submit(&lab, true);
    frame(&lab, "Callback is unproved", "A free mutex alone is not enough to establish safe callback lifetime.");
    lab.callback.safe_callback = true; submit(&lab, false);
    frame(&lab, "Queue full", "A nonblocking attempt can fail. Work stays pending.");
    submit(&lab, true); old_token = lab.submission.token;
    frame(&lab, "Retry accepted", "A queued request is still waiting for a confirmed display acknowledgment.");
    lab.completed = fly_sim_redraw_displayed(&lab.redraw, old_token, FLY_SIM_VIEW_HOME);
    frame(&lab, "HOME display acknowledged", "Only the matching request and a confirmed HOME display complete the epoch.");
    printf("]}");

    begin(&lab, "retry-exhaustion", "Bounded work. Honest failure.",
          "A perpetually full queue uses a finite budget. Exhaustion leaves work visibly pending instead of claiming recovery.", false);
    frame(&lab, "HOME ready", "The budget is an abstract host-test policy, not a measured device timing bound.");
    usb(&lab, true); usb(&lab, false);
    frame(&lab, "Detach epoch starts", "Three submission opportunities are allowed in this scenario.");
    for (unsigned n = 0; n < 3; ++n) {
        submit(&lab, false);
        frame(&lab, "Nonblocking queue refusal", "No display acknowledgment has arrived.");
    }
    submit(&lab, true);
    frame(&lab, "Retry budget exhausted", "A later callback cannot silently exceed the budget or report success.");
    printf("]}");

    begin(&lab, "stale-ack", "Yesterday cannot finish today",
          "Reattachment cancels an old detach epoch. Its late display token cannot complete the next epoch.", false);
    frame(&lab, "HOME ready", "Epoch identifiers distinguish successive detach requests.");
    usb(&lab, true); usb(&lab, false); submit(&lab, true); old_token = lab.submission.token;
    frame(&lab, "First request accepted", "The request is queued, with no display acknowledgment yet.");
    usb(&lab, true);
    frame(&lab, "USB reattached", "Pending work for the old detached epoch is cancelled.");
    usb(&lab, false); submit(&lab, true);
    frame(&lab, "A new detach epoch", "The new request has a distinct epoch identifier.");
    lab.completed = fly_sim_redraw_displayed(&lab.redraw, old_token, FLY_SIM_VIEW_HOME);
    frame(&lab, "Old acknowledgment rejected", "The current request remains pending; an old token cannot clear it.");
    printf("]}");

    begin(&lab, "invalid-view", "Uncertainty stays native",
          "Malformed snapshots select Garmin for a fresh sequence. Orphan or duplicate events are rejected without mutating ownership.", false);
    view(&lab, FLY_SIM_VIEW_INVALID);
    frame(&lab, "Snapshot unavailable", "The host receives INVALID; this is not a firmware classifier proof.");
    key(&lab, FLY_SIM_KEY_START, FLY_SIM_PRESS);
    frame(&lab, "START on INVALID", "Uncertain first-visible view means native ownership.");
    view(&lab, FLY_SIM_VIEW_HOME); key(&lab, FLY_SIM_KEY_START, FLY_SIM_RELEASE);
    frame(&lab, "Valid HOME returns", "The release still follows its original native owner.");
    key(&lab, FLY_SIM_KEY_UP, FLY_SIM_RELEASE);
    frame(&lab, "Orphan release", "No new owner is invented for an event with no matching press.");
    key(&lab, FLY_SIM_KEY_START, FLY_SIM_PRESS);
    frame(&lab, "New valid START", "A genuinely fresh HOME sequence can select FlyOS.");
    key(&lab, FLY_SIM_KEY_START, FLY_SIM_PRESS);
    frame(&lab, "Duplicate press", "Rejected without resetting or stealing the existing owner.");
    key(&lab, FLY_SIM_KEY_START, FLY_SIM_RELEASE);
    frame(&lab, "Original release", "The original valid sequence can still finish normally.");
    printf("]}]}");
    return ferror(stdout) ? 1 : 0;
}
