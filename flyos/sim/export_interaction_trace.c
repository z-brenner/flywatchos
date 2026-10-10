/* Host-only traces. Calls the real portable neuron model and C renderer.
 * No private firmware, device paths or native calls. Documented addresses are
 * used only as integer keys in an injected synthetic memory fixture. */
#include "display/neural_specimen.h"
#include "sim/host_policy.h"
#include "sim/view_classifier.h"

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
    bool classified;
    bool aba_limitation;
    FlySimViewResult classification;
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
        "\"source_locked\":%s,\"usb_locked\":%s,\"state\":%u,",
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
    printf("\"classifier\":{\"source\":\"%s\",\"reason\":\"%s\","
        "\"reads\":%u,\"nodes\":%u,\"limitation\":\"%s\"},\"neurons\":[",
        lab->classified ? "synthetic-reader" : "supplied-context",
        lab->classified ? fly_sim_view_reason_name(lab->classification.reason) : "not-run",
        lab->classified ? lab->classification.read_count : 0u,
        lab->classified ? lab->classification.node_count : 0u,
        lab->aba_limitation ? "complete-ABA" : "none");
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
    lab->classified = false;
    lab->aba_limitation = false;
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

/* Synthetic sparse memory; these integers are never cast to pointers. */
typedef struct {
    uint32_t root;
    uint32_t words[9][4];
    unsigned count;
    unsigned reads;
    unsigned mutation;
    uint32_t unreadable;
} ViewFixture;

static uint32_t fixture_address(unsigned node) {
    return FLY_SIM_VIEW_NODE_MIN + 0x100u + node * 0x100u;
}

static void fixture_init(ViewFixture *fixture, unsigned count) {
    memset(fixture, 0, sizeof(*fixture));
    fixture->count = count;
    fixture->root = count ? fixture_address(0u) : 0u;
    for (unsigned node = 0; node < count; ++node) {
        fixture->words[node][0] = node ? fixture_address(node - 1u) : 0u;
        fixture->words[node][1] = node + 1u < count ? fixture_address(node + 1u) : 0u;
        fixture->words[node][2] = FLY_SIM_VIEW_HOME_IDENTITY;
    }
}

static bool fixture_read(void *context, uint32_t address, uint32_t *value) {
    static const uint32_t offsets[] = {
        FLY_SIM_VIEW_PREV_OFFSET, FLY_SIM_VIEW_NEXT_OFFSET,
        FLY_SIM_VIEW_IDENTITY_OFFSET, FLY_SIM_VIEW_FLAGS_OFFSET};
    ViewFixture *fixture = context;
    ++fixture->reads;
    if (fixture->mutation == 1u && fixture->reads == 7u)
        fixture->words[0][2] = 0x12345u; /* Between single-node captures. */
    if (fixture->mutation == 2u && fixture->reads == 6u)
        fixture->root = fixture_address(1u); /* Before capture's final root. */
    if (fixture->mutation == 3u && fixture->reads == 6u) {
        /* Complete, deliberately unobserved A -> B -> A between samples. */
        fixture->words[0][2] = 0x12345u;
        fixture->words[0][2] = FLY_SIM_VIEW_HOME_IDENTITY;
    }
    if (address == fixture->unreadable) return false;
    if (address == FLY_SIM_VIEW_ROOT_ADDRESS) {
        *value = fixture->root;
        return true;
    }
    for (unsigned node = 0; node < fixture->count; ++node)
        for (unsigned field = 0; field < 4u; ++field)
            if (address == fixture_address(node) + offsets[field]) {
                *value = fixture->words[node][field];
                return true;
            }
    return false;
}

static void classified_frame(Lab *lab, ViewFixture *fixture,
                             const char *action, const char *detail) {
    lab->classification = fly_sim_classify_view(fixture_read, fixture);
    lab->classified = true;
    lab->aba_limitation = fixture->mutation == 3u;
    lab->input.view = lab->classification.classification == FLY_SIM_CLASS_HOME ?
        FLY_SIM_VIEW_HOME : lab->classification.classification == FLY_SIM_CLASS_NON_HOME ?
        FLY_SIM_VIEW_NATIVE : FLY_SIM_VIEW_INVALID;
    lab->callback.view = lab->input.view;
    key(lab, FLY_SIM_KEY_START, FLY_SIM_PRESS);
    submit(lab, true);
    frame(lab, action, detail);
    key(lab, FLY_SIM_KEY_START, FLY_SIM_RELEASE);
    lab->route = -1;
}

int main(int argc, char **argv) {
    Lab lab;
    FlySimRedrawToken old_token;
    ViewFixture fixture;
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
    printf("]}");

    begin(&lab, "classifier-guards", "Trust is earned in bounds",
          "The real host classifier reads a synthetic list. Malformed, cyclic, hidden-only and unreadable lists stay native without triggering a redraw.", false);
    frame(&lab, "Before synthetic capture", "These integer-keyed fixtures are not watch memory or recovered firmware evidence.");
    usb(&lab, true); usb(&lab, false);
    fixture_init(&fixture, 2u); fixture.words[0][3] = FLY_SIM_VIEW_HIDDEN_BIT; fixture.words[1][2] = 0x12345u;
    classified_frame(&lab, &fixture, "Hidden HOME, visible native", "First visible identity wins. A hidden HOME must not hide a visible native view.");
    fixture_init(&fixture, 1u); fixture.root += 1u;
    classified_frame(&lab, &fixture, "Unaligned pointer", "The classifier rejects this pointer before any node read.");
    fixture_init(&fixture, 1u); fixture.root = FLY_SIM_VIEW_NODE_MAX + 4u;
    classified_frame(&lab, &fixture, "Out-of-range node", "The entire documented node must fit the allowed synthetic address range.");
    fixture_init(&fixture, 2u); fixture.words[1][0] = 0u;
    classified_frame(&lab, &fixture, "Broken backlink", "Forward traversal alone is insufficient; each predecessor must match.");
    fixture_init(&fixture, 2u); fixture.words[1][1] = fixture_address(0u);
    classified_frame(&lab, &fixture, "Cycle detected", "Visited nodes cannot be revisited. The read budget stays bounded.");
    fixture_init(&fixture, 9u);
    classified_frame(&lab, &fixture, "Ninth node rejected", "Eight is the maximum. The ninth node is never read.");
    fixture_init(&fixture, 1u); fixture.unreadable = fixture_address(0u) + FLY_SIM_VIEW_FLAGS_OFFSET;
    classified_frame(&lab, &fixture, "Unreadable field", "An unknown reader result cannot be interpreted as HOME.");
    fixture_init(&fixture, 2u); fixture.words[0][3] = FLY_SIM_VIEW_HIDDEN_BIT; fixture.words[1][3] = FLY_SIM_VIEW_HIDDEN_BIT;
    classified_frame(&lab, &fixture, "All nodes hidden", "No visible identity means INVALID. Empty and all-hidden lists fail safely.");
    fixture_init(&fixture, 8u);
    classified_frame(&lab, &fixture, "Eight valid nodes", "Two equal full captures use exactly 68 reads. This is host-model evidence only.");
    printf("]}");

    begin(&lab, "classifier-stability", "Matching is not atomic",
          "Changing captures fail closed. A complete change-and-restore between reads remains invisible; the lab makes that limitation explicit.", false);
    fixture_init(&fixture, 1u);
    classified_frame(&lab, &fixture, "Two matching HOME captures", "The first visible identity is HOME in both bounded captures.");
    fixture_init(&fixture, 1u); fixture.mutation = 1u;
    classified_frame(&lab, &fixture, "Identity changed between captures", "Every captured field is compared. A changed identity selects INVALID and Garmin.");
    fixture_init(&fixture, 1u); fixture.mutation = 2u;
    classified_frame(&lab, &fixture, "Root changed during capture", "Each capture checks the root before and after traversing the list.");
    fixture_init(&fixture, 1u); fixture.words[0][2] = 0x12345u;
    classified_frame(&lab, &fixture, "Stable synthetic native view", "An arbitrary non-HOME fixture remains native. This is not an observed update-prompt identity.");
    fixture_init(&fixture, 1u); fixture.mutation = 3u;
    classified_frame(&lab, &fixture, "Complete ABA is invisible", "HOME is returned here: matching sampled values are not atomic. Complete ABA and post-read changes need a separate concurrency argument.");
    printf("]}]}");
    return ferror(stdout) ? 1 : 0;
}
