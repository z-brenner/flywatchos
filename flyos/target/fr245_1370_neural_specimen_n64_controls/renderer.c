#include <stdint.h>
#include "fly/brain64.h"

#define W 240u
#define H 240u

static void pixel(uint8_t *fb, unsigned x, unsigned y, uint8_t color) {
    if (x < W && y < H) fb[y * W + x] = color;
}

static void line(uint8_t *fb, int x0, int y0, int x1, int y1, uint8_t color) {
    int dx = x1 > x0 ? x1 - x0 : x0 - x1;
    int sx = x0 < x1 ? 1 : -1;
    int dy = y1 > y0 ? y0 - y1 : y1 - y0;
    int sy = y0 < y1 ? 1 : -1;
    int error = dx + dy;
    for (;;) {
        pixel(fb, (unsigned)x0, (unsigned)y0, color);
        if (x0 == x1 && y0 == y1) return;
        int twice = error + error;
        if (twice >= dy) { error += dy; x0 += sx; }
        if (twice <= dx) { error += dx; y0 += sy; }
    }
}

/* 3x5 scientific-instrument face. Each glyph is five packed three-bit rows. */
static uint16_t glyph(char c) {
    static const uint16_t letters[26] = {
        0x5beau,0x6baeu,0x3923u,0x6b6eu,0x79a7u,0x49a7u,0x3b63u,
        0x5bedu,0x7497u,0x2a49u,0x5badu,0x7924u,0x5bfdu,0x5ffdu,
        0x2b6au,0x49aeu,0x3f6au,0x5baeu,0x62a3u,0x2497u,0x7b6du,
        0x2b6du,0x5fedu,0x5aadu,0x24adu,0x788fu
    };
    static const uint16_t digits[10] = {
        0x7b6fu,0x74b2u,0x788eu,0x628eu,0x13edu,
        0x63a7u,0x7be3u,0x248fu,0x7befu,0x63efu
    };
    if (c >= 'A' && c <= 'Z') return letters[c - 'A'];
    if (c >= '0' && c <= '9') return digits[c - '0'];
    if (c == '-') return 0x01c0u;
    if (c == '/') return 0x4889u;
    if (c == '>') return 0x4454u;
    return 0u;
}

static void text(uint8_t *fb, unsigned x, unsigned y, const char *s) {
    while (*s != '\0') {
        uint16_t bits = glyph(*s++);
        for (unsigned row = 0u; row < 5u; ++row)
            for (unsigned col = 0u; col < 3u; ++col)
                if ((bits & (1u << (row * 3u + col))) != 0u)
                    pixel(fb, x + 2u - col, y + row, 0x3fu);
        x += 4u;
    }
}

static void number(uint8_t *fb, unsigned x, unsigned y, uint8_t value) {
    if (value >= 100u) { text(fb, x, y, "100"); return; }
    else if (value >= 10u) { char d[2] = {(char)('0' + value / 10u), 0}; text(fb,x,y,d); x += 4u; value %= 10u; }
    char d[2] = {(char)('0' + value), 0}; text(fb, x, y, d);
}

static void cell(uint8_t *fb, unsigned neuron, int16_t activation) {
    static const uint8_t base[8] = {93u,93u,89u,89u,89u,89u,93u,93u};
    static const uint8_t gap[8] = {7u,7u,8u,8u,8u,8u,7u,7u};
    unsigned row = neuron >> 3;
    unsigned x = base[row] + (neuron & 7u) * gap[row];
    unsigned y = 76u + row * 9u;
    uint32_t magnitude = (uint32_t)(activation < 0 ? -(int32_t)activation : activation);
    unsigned level = magnitude < 128u ? 0u : magnitude < 256u ? 1u : magnitude < 512u ? 2u : 3u;
    uint8_t color = activation < 0 ? 0x33u :
        (((neuron < 5u || neuron >= 56u) && level == 3u) ? 0x38u : 0x0cu);
    if (level == 0u) {
        pixel(fb, x + 2u, y + 2u, color); pixel(fb, x + 3u, y + 2u, color);
    } else if (level == 1u) {
        line(fb, (int)x + 2, (int)y, (int)x + 2, (int)y + 5, color);
        line(fb, (int)x, (int)y + 2, (int)x + 5, (int)y + 2, color);
    } else if (level == 2u) {
        line(fb,(int)x,(int)y,(int)x+5,(int)y,color); line(fb,(int)x+5,(int)y,(int)x+5,(int)y+5,color);
        line(fb,(int)x+5,(int)y+5,(int)x,(int)y+5,color); line(fb,(int)x,(int)y+5,(int)x,(int)y,color);
    } else {
        for (unsigned r=0u;r<6u;++r) for(unsigned c=0u;c<6u;++c) pixel(fb,x+c,y+r,color);
    }
}

static const char *footer(uint8_t buttons) {
    if ((buttons & 1u) != 0u) return " LIGHT>LUX ";
    if ((buttons & 2u) != 0u) return "START>BURST";
    if ((buttons & 4u) != 0u) return "BACK>SYSTEM";
    if ((buttons & 8u) != 0u) return " DOWN>CALM ";
    if ((buttons & 16u) != 0u) return "  UP>PULSE ";
    return " PRESS>KEYS";
}

void n64_render(uint8_t *fb, const FlyBrain64 *brain, const FlyBrainInputs *in,
                uint32_t tick, uint8_t usb_ms) {
    static const uint8_t contour[] = {
        120,48, 96,54, 70,74, 52,110, 68,150, 92,168, 120,172,
        148,168, 172,150, 188,110, 170,74, 144,54, 120,48
    };
    (void)usb_ms;
    for (unsigned i=0u;i<W*H;++i) fb[i]=0u;
    text(fb,110u,22u,"FLYOS");
    text(fb,99u,32u,"SPECIMEN 64");
    pixel(fb,100u+(tick&31u),42u,0x3fu);
    line(fb,96,54,76,43,0x2a); line(fb,76,43,66,49,0x2a);
    line(fb,144,54,164,43,0x2a); line(fb,164,43,174,49,0x2a);
    for (unsigned i=0u;i+3u<sizeof(contour);i+=2u)
        line(fb,contour[i],contour[i+1u],contour[i+2u],contour[i+3u],0x2a);
    for (unsigned n=0u;n<64u;++n) cell(fb,n,brain->activation[n]);
    line(fb,62,178,178,178,0x2a); line(fb,62,196,178,196,0x2a);
    text(fb,64u,185u,"STATE");
    {
        static const char states[4][2] = {"R","M","A","Q"};
        text(fb,88u,185u,states[brain->state < 4u ? brain->state : 0u]);
    }
    text(fb,112u,185u,"B");
    if ((in->valid_mask & FLY_BRAIN64_VALID_BATTERY) != 0u) number(fb,120u,185u,in->battery_percent);
    else text(fb,120u,185u,"--");
    text(fb,98u,204u,footer(in->buttons));
}
