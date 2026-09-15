#include "display/garmin_row_packer.h"

static uint8_t primary(uint8_t first, uint8_t second) {
    return (uint8_t)(((first & 0xeau) >> 1u) | (second & 0xeau));
}

static uint8_t secondary(uint8_t first, uint8_t second) {
    return (uint8_t)((first & 0x15u) | ((second & 0x15u) << 1u));
}

void fly_display_pack_row(const uint8_t source[FLY_DISPLAY_WIDTH],
                          uint8_t staging[FLY_DISPLAY_STAGING_ROW_BYTES],
                          bool reverse) {
    staging[0] = 0u;
    staging[121] = 0u;
    staging[122] = 0u;
    staging[243] = 0u;

    for (unsigned word = 0; word < 60u; ++word) {
        unsigned source_offset = word * 4u;
        unsigned output_offset = reverse ? 1u + (59u - word) * 2u : 1u + word * 2u;
        uint8_t a = source[source_offset];
        uint8_t b = source[source_offset + 1u];
        uint8_t c = source[source_offset + 2u];
        uint8_t d = source[source_offset + 3u];
        if (reverse) {
            uint8_t temporary = a;
            a = d;
            d = temporary;
            temporary = b;
            b = c;
            c = temporary;
        }
        staging[output_offset] = primary(a, b);
        staging[output_offset + 1u] = primary(c, d);
        staging[122u + output_offset] = secondary(a, b);
        staging[123u + output_offset] = secondary(c, d);
    }
}
