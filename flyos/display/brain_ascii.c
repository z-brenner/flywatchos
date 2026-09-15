#include "display/brain_ascii.h"

const FlyBrainPoint fly_brain_points[32] = {
    {64,65}, {78,65}, {92,65}, {106,65}, {128,65}, {142,65}, {156,65}, {170,65},
    {46,88}, {66,88}, {86,88}, {106,88}, {128,88}, {148,88}, {168,88}, {188,88},
    {46,111},{66,111},{86,111},{106,111},{128,111},{148,111},{168,111},{188,111},
    {64,134},{78,134},{92,134},{106,134},{128,134},{142,134},{156,134},{170,134}
};

static const uint8_t neuron_glyphs[4][7] = {
    {0,0,0,0,0,4,0},                  /* . : 1 pixel */
    {0,0,14,10,14,0,0},               /* o : 8 pixels */
    {14,17,17,17,17,17,14},           /* O : 16 pixels */
    {14,17,23,21,23,16,15}            /* @ : 21 pixels */
};

static const uint8_t *glyph(char c) {
    static const uint8_t blank[7] = {0};
    static const uint8_t digits[10][7] = {
        {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},
        {30,1,1,14,1,1,30},{2,6,10,18,31,2,2},{31,16,16,30,1,1,30},
        {14,16,16,30,17,17,14},{31,1,2,4,8,8,8},{14,17,17,14,17,17,14},
        {14,17,17,15,1,1,14}
    };
    static const uint8_t letters[26][7] = {
        {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{14,17,16,16,16,17,14},
        {30,17,17,17,17,17,30},{31,16,16,30,16,16,31},{31,16,16,30,16,16,16},
        {14,17,16,23,17,17,15},{17,17,17,31,17,17,17},{14,4,4,4,4,4,14},
        {7,2,2,2,18,18,12},{17,18,20,24,20,18,17},{16,16,16,16,16,16,31},
        {17,27,21,21,17,17,17},{17,25,21,19,17,17,17},{14,17,17,17,17,17,14},
        {30,17,17,30,16,16,16},{14,17,17,17,21,18,13},{30,17,17,30,20,18,17},
        {15,16,16,14,1,1,30},{31,4,4,4,4,4,4},{17,17,17,17,17,17,14},
        {17,17,17,17,17,10,4},{17,17,17,21,21,21,10},{17,17,10,4,10,17,17},
        {17,17,10,4,4,4,4},{31,1,2,4,8,16,31}
    };
    static const uint8_t punctuation[6][7] = {
        {1,2,2,4,8,8,16}, /* / */
        {16,8,8,4,2,2,1}, /* backslash */
        {0,0,0,31,0,0,0},/* - */
        {0,0,0,0,0,0,31},/* _ */
        {4,4,4,4,4,4,4}, /* | */
        {0,4,0,0,4,0,0}  /* : */
    };
    if (c >= '0' && c <= '9') return digits[c - '0'];
    if (c >= 'A' && c <= 'Z') return letters[c - 'A'];
    if (c == '/') return punctuation[0];
    if (c == '\\') return punctuation[1];
    if (c == '-') return punctuation[2];
    if (c == '_') return punctuation[3];
    if (c == '|') return punctuation[4];
    if (c == ':') return punctuation[5];
    return blank;
}

static void ink(uint8_t *fb, int x, int y) {
    if ((unsigned)x < 240u && (unsigned)y < 240u)
        fb[(unsigned)y * 240u + (unsigned)x] = 0x00;
}

static void bitmap(uint8_t *fb, int x, int y, const uint8_t rows[7], unsigned scale) {
    for (unsigned row = 0; row < 7; ++row)
        for (unsigned col = 0; col < 5; ++col)
            if (rows[row] & (1u << (4u - col)))
                for (unsigned dy = 0; dy < scale; ++dy)
                    for (unsigned dx = 0; dx < scale; ++dx)
                        ink(fb, x + (int)(col * scale + dx), y + (int)(row * scale + dy));
}

static void text(uint8_t *fb, int x, int y, const char *s, unsigned scale) {
    for (; *s; ++s, x += (int)(6u * scale)) bitmap(fb, x, y, glyph(*s), scale);
}

static void line(uint8_t *fb, int x0, int y0, int x1, int y1) {
    int dx = x1 > x0 ? x1 - x0 : x0 - x1;
    int dy = y1 > y0 ? y0 - y1 : y1 - y0;
    int sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    int error = dx + dy;
    for (;;) {
        ink(fb, x0, y0);
        if (x0 == x1 && y0 == y1) break;
        int twice = 2 * error;
        if (twice >= dy) { error += dy; x0 += sx; }
        if (twice <= dx) { error += dx; y0 += sy; }
    }
}

static void hex4(uint8_t *fb, int x, int y, uint32_t value) {
    static const char digits[] = "0123456789ABCDEF";
    for (unsigned i = 0; i < 4; ++i)
        bitmap(fb, x + (int)(i * 6u), y, glyph(digits[(value >> (12u - 4u * i)) & 15u]), 1);
}

static void silhouette(uint8_t *fb) {
    static const FlyBrainPoint contour[] = {
        {115,58},{104,49},{73,45},{53,53},{37,70},{28,94},
        {29,115},{41,138},{60,152},{83,157},{103,150},{114,140}
    };
    for (unsigned i = 1; i < sizeof(contour) / sizeof(contour[0]); ++i) {
        FlyBrainPoint a = contour[i - 1], b = contour[i];
        line(fb, a.x, a.y, b.x, b.y);
        line(fb, 239 - a.x, a.y, 239 - b.x, b.y);
    }
    text(fb, 114, 58, "__", 1);
    text(fb, 117, 81, ":", 1);
    text(fb, 117, 104, "|", 1);
    text(fb, 117, 123, ":", 1);
    line(fb, 114, 140, 114, 158);
    line(fb, 125, 140, 125, 158);
    text(fb, 114, 155, "__", 1);
    /* Short, interrupted axon strokes deliberately avoid every glyph and pulse. */
    static const uint8_t strokes[][4] = {
        {76,68,76,76},{68,79,76,76},{98,77,108,82},
        {140,68,140,76},{140,76,150,80},{178,79,190,83},
        {56,91,63,91},{96,91,103,91},{158,91,165,91},
        {48,99,48,107},{88,99,88,107},{150,99,150,107},{190,99,190,107},
        {76,114,83,114},{138,114,145,114},{178,114,185,114},
        {58,124,66,130},{96,124,108,129},{130,124,142,129},{174,124,182,120}
    };
    for (unsigned i = 0; i < sizeof(strokes) / sizeof(strokes[0]); ++i)
        line(fb, strokes[i][0], strokes[i][1], strokes[i][2], strokes[i][3]);
}

void fly_brain_ascii_render(uint8_t framebuffer[57600], const FlyBrain32 *brain,
                            uint32_t rtc_tick, uint8_t buttons) {
    for (unsigned i = 0; i < 57600u; ++i) framebuffer[i] = 0xff;
    text(framebuffer, 30, 18, "FLY//32", 2);
    text(framebuffer, 144, 17, "PHASE", 1);
    hex4(framebuffer, 147, 28, rtc_tick);
    /* Tick activity marker is independent of neuron levels. */
    if (rtc_tick & 1u) {
        line(framebuffer, 198, 24, 198, 28);
        line(framebuffer, 196, 26, 200, 26);
    } else ink(framebuffer, 198, 26);
    line(framebuffer, 26, 39, 213, 39);
    silhouette(framebuffer);
    for (unsigned i = 0; i < 32u; ++i) {
        FlyBrainPoint p = fly_brain_points[i];
        unsigned level = fly_brain32_level(brain, i);
        bitmap(framebuffer, p.x, p.y, neuron_glyphs[level], 1);
        if (level >= 2u) {
            ink(framebuffer, p.x + 7, p.y + 3);
            ink(framebuffer, p.x + 8, p.y + 3);
        }
    }
    line(framebuffer, 38, 171, 201, 171);
    text(framebuffer, 43, 181, "STATE", 1);
    const char *state = "REST";
    switch (fly_brain32_state(brain)) {
        case FLY_BRAIN_STATE_MOVEMENT: state = "MOVE"; break;
        case FLY_BRAIN_STATE_AROUSAL: state = "AROUSAL"; break;
        case FLY_BRAIN_STATE_QUIET: state = "QUIET"; break;
        default: break;
    }
    text(framebuffer, 115, 181, state, 1);
    text(framebuffer, 43, 195, "ID PHASE", 1);
    hex4(framebuffer, 115, 195, brain->epoch);
    static const char labels[] = "L1234";
    for (unsigned i = 0; i < 5u; ++i) {
        int x = 69 + (int)(24u * i);
        bitmap(framebuffer, x, 213, glyph(labels[i]), 1);
        if (buttons & (1u << i)) line(framebuffer, x - 2, 223, x + 6, 223);
    }
}
