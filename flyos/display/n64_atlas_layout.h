#ifndef FLYOS_DISPLAY_N64_ATLAS_LAYOUT_H
#define FLYOS_DISPLAY_N64_ATLAS_LAYOUT_H

#include <stdint.h>

/*
 * Authoritative 64-neuron Drosophila atlas layout, shared verbatim by the host
 * preview renderer, the target renderer and the target-derived mapping
 * manifest.  It is header-only so the three of them cannot drift.
 *
 * Every neuron owns one 5x5 mask.  The masks are pairwise disjoint, they stay
 * inside the 98-pixel safe circle around (120, 120), and no fixed scaffold
 * stroke or label is allowed to reach inside one.  Magnitude is carried by
 * density alone: 1, 9, 16 and 25 lit pixels.
 */

#define FLY_N64_ATLAS_NEURONS 64u
#define FLY_N64_ATLAS_MASK 5u
#define FLY_N64_ATLAS_CENTER 120
#define FLY_N64_ATLAS_RADIUS 98

enum {
    FLY_N64_POPULATION_SENSORY_RIM = 0u,   /* 0-11  antennal/optic sensory arc */
    FLY_N64_POPULATION_CENTRAL_RING = 1u,  /* 12-23 central-complex ring       */
    FLY_N64_POPULATION_MUSHROOM_BODY = 2u, /* 24-39 paired lateral columns     */
    FLY_N64_POPULATION_MODULATORY = 3u,    /* 40-47 modulatory midline         */
    FLY_N64_POPULATION_IDENTITY = 4u,      /* 48-55 identity core              */
    FLY_N64_POPULATION_ACTION_FAN = 5u     /* 56-63 descending action fan      */
};

typedef struct FlyN64AtlasPoint {
    uint8_t x;
    uint8_t y;
} FlyN64AtlasPoint;

/* Top-left corner of each neuron's 5x5 mask. */
static const FlyN64AtlasPoint fly_n64_atlas_points[FLY_N64_ATLAS_NEURONS] = {
    { 47u, 85u}, { 56u, 71u}, { 66u, 59u}, { 80u, 50u},
    { 94u, 44u}, {110u, 40u}, {126u, 40u}, {142u, 44u},
    {156u, 50u}, {170u, 59u}, {180u, 71u}, {189u, 85u},
    {118u, 72u}, {141u, 78u}, {158u, 95u}, {164u,118u},
    {158u,141u}, {141u,158u}, {118u,164u}, { 95u,158u},
    { 78u,141u}, { 72u,118u}, { 78u, 95u}, { 95u, 78u},
    { 64u, 76u}, { 64u, 88u}, { 64u,100u}, { 64u,112u},
    { 64u,124u}, { 64u,136u}, { 64u,148u}, { 64u,160u},
    {172u, 76u}, {172u, 88u}, {172u,100u}, {172u,112u},
    {172u,124u}, {172u,136u}, {172u,148u}, {172u,160u},
    {118u, 78u}, {118u, 86u}, {118u, 94u}, {118u,102u},
    {118u,132u}, {118u,140u}, {118u,148u}, {118u,156u},
    {106u,110u}, {114u,110u}, {122u,110u}, {130u,110u},
    {106u,126u}, {114u,126u}, {122u,126u}, {130u,126u},
    {164u,157u}, {153u,167u}, {140u,174u}, {125u,178u},
    {111u,178u}, { 96u,174u}, { 83u,167u}, { 72u,157u}
};

/*
 * Row bitmaps of the four activation densities, bit c of row r lighting mask
 * pixel (x + c, y + r): a centre dot, a 3x3 block, a 5x5 outline and a filled
 * 5x5 block, which light 1, 9, 16 and 25 pixels.
 */
static const uint8_t fly_n64_atlas_density[4][FLY_N64_ATLAS_MASK] = {
    {0x00u, 0x00u, 0x04u, 0x00u, 0x00u},
    {0x00u, 0x0eu, 0x0eu, 0x0eu, 0x00u},
    {0x1fu, 0x11u, 0x11u, 0x11u, 0x1fu},
    {0x1fu, 0x1fu, 0x1fu, 0x1fu, 0x1fu}
};

/*
 * Fixed scaffold display list: a broken angular head cutaway with an open
 * inferior edge, two antenna roots, four lateral eye marks and four tracts
 * that run from the identity core out to the central ring.  Each entry is
 * {x, y, direction, pixels} and every direction only ever advances right
 * and/or down, so four directions and one stepping loop replace a general
 * line rasteriser.  No stroke pixel touches a neuron mask.
 */
#define FLY_N64_ATLAS_STROKES 20u

static const uint8_t fly_n64_atlas_stroke[FLY_N64_ATLAS_STROKES][4] = {
    { 84u,  30u, 0u, 25u}, {132u,  30u, 0u, 25u},
    { 84u,  30u, 3u, 45u}, {156u,  30u, 1u, 45u},
    { 40u,  74u, 2u, 31u}, { 40u, 116u, 2u, 35u},
    {200u,  74u, 2u, 31u}, {200u, 116u, 2u, 35u},
    { 40u, 150u, 1u, 31u}, {200u, 150u, 3u, 31u},
    {102u,  24u, 1u,  9u}, {138u,  24u, 3u,  9u},
    { 52u,  76u, 2u, 11u}, { 48u,  74u, 2u,  9u},
    {188u,  76u, 2u, 11u}, {192u,  74u, 2u,  9u},
    { 94u,  98u, 1u, 11u}, {146u,  98u, 3u, 11u},
    {104u, 132u, 3u, 11u}, {136u, 132u, 1u, 11u}
};

/* Per-direction x and y steps for the display list above. */
static const int8_t fly_n64_atlas_step[2][4] = {{1, 1, 0, -1}, {0, 1, 1, 1}};

/*
 * Idle-callout anchors in physical button order (LIGHT, START, BACK, DOWN,
 * UP), placed in the lateral corridors at the height of the key they name.
 */
static const uint8_t fly_n64_atlas_callout[5][2] = {
    { 48u,  96u}, {178u,  96u}, {178u, 148u}, { 46u, 148u}, { 44u, 122u}
};

#define FLY_N64_ATLAS_TITLE_Y 33u
#define FLY_N64_ATLAS_STATE_Y 186u
#define FLY_N64_ATLAS_FOOTER_Y 196u

/*
 * Packed 3x5 scientific-instrument face on a four-pixel pitch: bit
 * (row * 3 + column) of a glyph lights (x + 2 - column, y + row).  Anything
 * the face does not carry, the inter-word space included, renders blank.
 */
#define FLY_N64_ATLAS_GLYPH_PITCH 4u

static const uint16_t fly_n64_atlas_letters[26] = {
    0x5beau, 0x6baeu, 0x3923u, 0x6b6eu, 0x79a7u, 0x49a7u, 0x3b63u,
    0x5bedu, 0x7497u, 0x2a49u, 0x5badu, 0x7924u, 0x5bfdu, 0x5ffdu,
    0x2b6au, 0x49aeu, 0x3f6au, 0x5baeu, 0x62a3u, 0x2497u, 0x7b6du,
    0x2b6du, 0x5fedu, 0x5aadu, 0x24adu, 0x788fu
};

static const uint16_t fly_n64_atlas_digits[10] = {
    0x7b6fu, 0x74b2u, 0x788eu, 0x628eu, 0x13edu,
    0x63a7u, 0x7be3u, 0x248fu, 0x7befu, 0x63efu
};

static inline uint16_t fly_n64_atlas_glyph(char c) {
    if (c >= 'A' && c <= 'Z') return fly_n64_atlas_letters[c - 'A'];
    if (c >= '0' && c <= '9') return fly_n64_atlas_digits[c - '0'];
    if (c == '/') return 0x4889u;
    return 0u;
}

/* Left edge that centres a label of `chars` glyphs on the 240-pixel display. */
static inline unsigned fly_n64_atlas_centre(unsigned chars) {
    return (unsigned)FLY_N64_ATLAS_CENTER - chars * (FLY_N64_ATLAS_GLYPH_PITCH / 2u);
}

static inline FlyN64AtlasPoint fly_n64_atlas_point(unsigned neuron) {
    return fly_n64_atlas_points[neuron & 63u];
}

static inline uint8_t fly_n64_atlas_population(unsigned neuron) {
    neuron &= 63u;
    if (neuron < 12u) return FLY_N64_POPULATION_SENSORY_RIM;
    if (neuron < 24u) return FLY_N64_POPULATION_CENTRAL_RING;
    if (neuron < 40u) return FLY_N64_POPULATION_MUSHROOM_BODY;
    if (neuron < 48u) return FLY_N64_POPULATION_MODULATORY;
    if (neuron < 56u) return FLY_N64_POPULATION_IDENTITY;
    return FLY_N64_POPULATION_ACTION_FAN;
}

/* Density band of one signed Q5.10 activation: 0, 1, 2 or 3. */
static inline uint8_t fly_n64_atlas_level(int16_t activation) {
    uint32_t magnitude = (uint32_t)(activation < 0 ? -(int32_t)activation : activation);

    if (magnitude < 128u) return 0u;
    if (magnitude < 256u) return 1u;
    if (magnitude < 512u) return 2u;
    return 3u;
}

/* Lit-pixel count of a density band: 1, 9, 16 or 25. */
static inline unsigned fly_n64_atlas_density_pixels(unsigned level) {
    unsigned count = 0u;

    for (unsigned row = 0u; row < FLY_N64_ATLAS_MASK; ++row)
        for (unsigned column = 0u; column < FLY_N64_ATLAS_MASK; ++column)
            if ((fly_n64_atlas_density[level & 3u][row] >> column & 1u) != 0u) ++count;
    return count;
}

#endif
