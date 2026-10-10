/* Native trace oracle for the Wasm differential test, not a target program. */
#include "sim/live_bridge.h"

#include <inttypes.h>
#include <stdio.h>

static void snapshot(int result) {
    printf("{\"result\":%d,\"route\":%d,\"held\":%" PRIu32
           ",\"active\":%" PRIu32 ",\"pulse\":%" PRIu32
           ",\"delivered_pulse\":%" PRIu32 ",\"buttons\":%" PRIu32
           ",\"state\":%" PRIu32 ",\"epoch\":%" PRIu32
           ",\"view\":%" PRIu32 ",\"usb\":%" PRIu32
           ",\"ready\":%" PRIu32 ",\"valid_mask\":%" PRIu32
           ",\"rendered\":%" PRIu32 ",\"owners\":[",
           result, fly_lab_route(), fly_lab_held(), fly_lab_active(),
           fly_lab_pulse(), fly_lab_delivered_pulse(), fly_lab_buttons(),
           fly_lab_state(), fly_lab_epoch(), fly_lab_view(), fly_lab_usb(),
           fly_lab_ready(), fly_lab_valid_mask(), fly_lab_rendered());
    for (int key = 0; key < 5; ++key)
        printf("%s%d", key ? "," : "", fly_lab_owner(key));
    fputs("],\"neurons\":[", stdout);
    for (uint32_t n = 0u; n < fly_lab_neuron_count(); ++n)
        printf("%s%d", n ? "," : "", (int)fly_lab_activations()[n]);
    fputs("],\"pixels\":\"", stdout);
    for (uint32_t n = 0u; n < fly_lab_pixel_count(); ++n)
        putchar('0' + fly_lab_pixels()[n]);
    fputs("\"}\n", stdout);
}

int main(void) {
    char line[256];
    while (fgets(line, sizeof(line), stdin) != NULL) {
        uint32_t seed;
        int values[6];
        int result = 0;
        if (line[0] == 'R' && sscanf(line + 1, "%" SCNu32, &seed) == 1) {
            fly_lab_reset(seed);
        } else if (line[0] == 'E' && sscanf(line + 1, "%d%d", &values[0], &values[1]) == 2) {
            result = fly_lab_event(values[0], values[1]);
        } else if (line[0] == 'C' && sscanf(line + 1, "%d%d%d", &values[0], &values[1], &values[2]) == 3) {
            result = fly_lab_set_context(values[0], values[1], values[2]);
        } else if (line[0] == 'S' && sscanf(line + 1, "%d%d%d%d%d%d", &values[0], &values[1],
                    &values[2], &values[3], &values[4], &values[5]) == 6) {
            result = fly_lab_set_sensors(values[0], values[1], values[2], values[3], values[4], values[5]);
        } else if (line[0] == 'T') {
            fly_lab_step();
        } else {
            fputs("invalid trace command\n", stderr);
            return 2;
        }
        snapshot(result);
    }
    return ferror(stdin) || ferror(stdout) ? 1 : 0;
}
