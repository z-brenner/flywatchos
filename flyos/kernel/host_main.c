#include "display/framebuffer.h"
#include "fly/network.h"
#include "fly/persistence.h"
#include "input/mock_input.h"

#include <stdio.h>
#include <time.h>

int main(void) {
    FlyPersistentState state;
    if (fly_persistence_load("flyos-state", &state) != FLY_PERSIST_OK)
        fly_persistent_state_init(&state, 0x245f1a5u);

    puts("FlyOS host mock: w/s/a/d/q = five buttons, x = exit");
    for (;;) {
        FlyFramebuffer fb;
        time_t now = time(NULL);
        struct tm *clock = localtime(&now);
        unsigned hour = clock ? (unsigned)clock->tm_hour : 0u;
        unsigned minute = clock ? (unsigned)clock->tm_min : 0u;
        fly_framebuffer_render_status(&fb, hour, minute,
                                      state.network.mood > 132u ? "ALERT" : "QUIET",
                                      state.accumulated_age_seconds,
                                      fly_network_activity(&state.network));
        if (fly_framebuffer_write_ppm(&fb, "flyos-screen.ppm") != 0) {
            fputs("could not write flyos-screen.ppm\n", stderr);
            return 1;
        }
        printf("tick=%lu mood=%u activity=%u > ", (unsigned long)state.network.tick,
               state.network.mood, fly_network_activity(&state.network));
        char input[16];
        if (!fgets(input, sizeof(input), stdin) || input[0] == 'x' || input[0] == 'X') break;
        fly_network_step(&state.network, fly_button_from_key(input[0]));
        ++state.accumulated_age_seconds;
    }
    return fly_persistence_save("flyos-state", &state) == FLY_PERSIST_OK ? 0 : 1;
}
