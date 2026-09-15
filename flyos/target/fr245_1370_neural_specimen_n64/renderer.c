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
    unsigned x = 96u + (neuron & 7u) * 6u;
    unsigned y = 79u + (neuron >> 3) * 8u;
    uint32_t magnitude = (uint32_t)(activation < 0 ? -(int32_t)activation : activation);
    unsigned level = magnitude < 128u ? 0u : magnitude < 256u ? 1u : magnitude < 512u ? 2u : 3u;
    uint8_t color = activation < 0 ? 0x33u : (neuron >= 56u && level == 3u ? 0x38u : 0x0cu);
    if (level == 0u) pixel(fb, x + 2u, y + 2u, color);
    else if (level == 1u) {
        line(fb, (int)x + 2, (int)y, (int)x + 2, (int)y + 4, color);
        line(fb, (int)x, (int)y + 2, (int)x + 4, (int)y + 2, color);
    } else if (level == 2u) {
        line(fb,(int)x,(int)y,(int)x+4,(int)y,color); line(fb,(int)x+4,(int)y,(int)x+4,(int)y+4,color);
        line(fb,(int)x+4,(int)y+4,(int)x,(int)y+4,color); line(fb,(int)x,(int)y+4,(int)x,(int)y,color);
    } else {
        for (unsigned r=0u;r<5u;++r) for(unsigned c=0u;c<5u;++c) pixel(fb,x+c,y+r,color);
    }
}

static const char *footer(uint8_t buttons) {
    if ((buttons & 1u) != 0u) return "LIGHT>LUX";
    if ((buttons & 2u) != 0u) return "START>BURST";
    if ((buttons & 8u) != 0u) return "DOWN>CALM";
    if ((buttons & 16u) != 0u) return "UP>PULSE";
    return "N64READY";
}

void n64_render(uint8_t *fb, const FlyBrain64 *brain, const FlyBrainInputs *in,
                uint32_t tick, uint8_t usb_ms) {
    static const uint8_t contour[] = {
        120,50, 98,56, 73,76, 55,110, 70,146, 94,163, 120,168,
        146,163, 170,146, 185,110, 167,76, 142,56, 120,50
    };
    for (unsigned i=0u;i<W*H;++i) fb[i]=0u;
    text(fb,110u,18u,"PHASE");
    text(fb,98u,30u,"FLYOS // N64");
    pixel(fb,88u+(tick&63u),27u,0x3fu);
    line(fb,98,56,76,43,0x2a); line(fb,76,43,66,49,0x2a);
    line(fb,142,56,164,43,0x2a); line(fb,164,43,174,49,0x2a);
    for (unsigned i=0u;i+3u<sizeof(contour);i+=2u)
        line(fb,contour[i],contour[i+1u],contour[i+2u],contour[i+3u],0x2a);
    line(fb,73,76,94,90,0x2a); line(fb,55,110,92,116,0x2a); line(fb,70,146,94,133,0x2a);
    line(fb,167,76,146,90,0x2a); line(fb,185,110,148,116,0x2a); line(fb,170,146,146,133,0x2a);
    text(fb,58u,67u,"LUX"); text(fb,48u,110u,"WAKE"); text(fb,50u,151u,"CALM");
    text(fb,166u,67u,"PULSE"); text(fb,175u,151u,"SYS");
    for (unsigned n=0u;n<64u;++n) cell(fb,n,brain->activation[n]);
    line(fb,55,173,185,173,0x2a); line(fb,55,199,185,199,0x2a);
    text(fb,59u,180u,"HR --"); text(fb,104u,180u,"B");
    if ((in->valid_mask & FLY_BRAIN64_VALID_BATTERY) != 0u) number(fb,112u,180u,in->battery_percent);
    else text(fb,112u,180u,"--");
    text(fb,146u,180u,usb_ms != 0u ? "USB MS" : "MS --");
    {
        static const char states[4][2] = {"R","M","A","Q"};
        text(fb,59u,190u,"MOTION --");
        text(fb,146u,190u,"STATE");
        text(fb,170u,190u,states[brain->state < 4u ? brain->state : 0u]);
    }
    text(fb,74u,211u,footer(in->buttons));
}
