#include "display/framebuffer.h"
#include "display/garmin_row_packer.h"
#include "fly/network.h"
#include "fly/persistence.h"
#include "input/mock_input.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(condition)                                                        \
    do {                                                                        \
        if (!(condition)) {                                                     \
            fprintf(stderr, "check failed: %s (%s:%d)\n", #condition,         \
                    __FILE__, __LINE__);                                        \
            exit(EXIT_FAILURE);                                                 \
        }                                                                       \
    } while (0)

static void test_network_is_deterministic_and_evolves(void) {
    FlyNetwork a;
    FlyNetwork b;
    fly_network_init(&a, 0x12345678u);
    fly_network_init(&b, 0x12345678u);

    for (unsigned tick = 0; tick < 200; ++tick) {
        uint8_t input = (tick % 17u == 0u) ? FLY_INPUT_SELECT : 0u;
        fly_network_step(&a, input);
        fly_network_step(&b, input);
    }

    CHECK(memcmp(&a, &b, sizeof(a)) == 0);
    CHECK(a.tick == 200u);
    CHECK(fly_network_activity(&a) > 0u);
}

static void test_persistence_falls_back_to_older_valid_slot(void) {
    const char *base = "flyos_test_state";
    fly_persistence_remove(base);

    FlyPersistentState first;
    fly_persistent_state_init(&first, 7u);
    for (unsigned i = 0; i < 8; ++i) fly_network_step(&first.network, 0u);
    CHECK(fly_persistence_save(base, &first) == FLY_PERSIST_OK);

    FlyPersistentState second = first;
    fly_network_step(&second.network, FLY_INPUT_UP);
    CHECK(fly_persistence_save(base, &second) == FLY_PERSIST_OK);

    CHECK(fly_persistence_corrupt_newest_for_test(base) == FLY_PERSIST_OK);
    FlyPersistentState loaded;
    CHECK(fly_persistence_load(base, &loaded) == FLY_PERSIST_OK);
    CHECK(loaded.network.tick == first.network.tick);
    CHECK(loaded.sequence == first.sequence);
    fly_persistence_remove(base);
}

static void test_framebuffer_renders_required_text(void) {
    FlyFramebuffer fb;
    fly_framebuffer_clear(&fb, FLY_COLOR_BLACK);
    fly_framebuffer_render_status(&fb, 14u, 52u, "QUIET", 11662u, 41u);

    CHECK(fly_framebuffer_count_color(&fb, FLY_COLOR_TEXT) > 80u);
    CHECK(fly_framebuffer_region_nonzero(&fb, 75u, 205u, 165u, 220u));
}

static void test_mock_keyboard_mapping(void) {
    CHECK(fly_button_from_key('w') == FLY_INPUT_UP);
    CHECK(fly_button_from_key('s') == FLY_INPUT_DOWN);
    CHECK(fly_button_from_key('a') == FLY_INPUT_BACK);
    CHECK(fly_button_from_key('d') == FLY_INPUT_SELECT);
    CHECK(fly_button_from_key('q') == FLY_INPUT_LIGHT);
    CHECK(fly_button_from_key('x') == 0u);
}

static void test_panel_row_packer_uses_verified_pair_layout(void) {
    uint8_t source[FLY_DISPLAY_WIDTH] = {0};
    uint8_t staging[FLY_DISPLAY_WIDTH + 4u];
    memset(staging, 0xa5, sizeof(staging));
    source[0] = 0x00u;
    source[1] = 0xffu;
    source[238] = 0x15u;
    source[239] = 0xeau;

    fly_display_pack_row(source, staging, false);
    CHECK(staging[0] == 0u);
    CHECK(staging[1] == 0xeau);
    CHECK(staging[120] == 0xeau);
    CHECK(staging[121] == 0u);
    CHECK(staging[122] == 0u);
    CHECK(staging[123] == 0x2au);
    CHECK(staging[242] == 0x15u);
    CHECK(staging[243] == 0u);

    fly_display_pack_row(source, staging, true);
    CHECK(staging[1] == 0x75u);
    CHECK(staging[120] == 0x75u);
    CHECK(staging[123] == 0x2au);
    CHECK(staging[242] == 0x15u);
}

int main(void) {
    test_network_is_deterministic_and_evolves();
    test_persistence_falls_back_to_older_valid_slot();
    test_framebuffer_renders_required_text();
    test_mock_keyboard_mapping();
    test_panel_row_packer_uses_verified_pair_layout();
    puts("flyos tests: ok");
    return 0;
}
