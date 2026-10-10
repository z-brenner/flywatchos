#include "sim/cx_circuit.h"
#ifndef FLY_NEURAL_SPECIMEN_HOST_PREVIEW
#error "cx_circuit is host-only; it must never be linked into watch firmware"
#endif

typedef struct { double magnitude; int16_t coefficient_q; } FlyCxWeight;
typedef struct { uint8_t source, target, kind; } FlyCxEdge;
#include "sim/cx_connectivity.inc"

/* Deliberately new deterministic rate-relaxation dynamics, NOT the paper's
 * spiking or tanh-current simulator. Exact published topology is retained;
 * strengths are globally scaled by 1/100 then rounded to signed Q10.
 * r_next = floor((3*r + clamp(drive + trunc(sum(q*r)/1024),0,16383))/4).
 * All neurons update synchronously. Time is one abstract step, not ms or Hz.
 * Largest accumulator < 60*16383*1024, safely inside signed int32.
 * No RNG, allocation, floating-point dynamics, hardware, or external input.
 */
static int cue_angle(unsigned neuron) { return (int)(((neuron - 34u) % 9u) % 8u) * 45; }
static int32_t stimulus(unsigned neuron, const FlyCxInputs *inputs) {
    if (neuron >= 34u && neuron < 52u) {
        int distance = cue_angle(neuron) - inputs->cue_degrees;
        if (distance < 0) distance = -distance;
        if (distance > 180) distance = 360 - distance;
        /* Chosen triangular cue (half-width 90deg), not measured tuning. */
        return distance < 90 ? (90 - distance) * inputs->cue_strength * 8 / 90 : 0;
    }
    /* A/B avoids contradictory hemisphere labels in the source comments.
     * Positive means drive A, negative means drive B, NOT verified yaw sign. */
    if (neuron < 8u && inputs->turn_drive > 0) return inputs->turn_drive * 4;
    if (neuron >= 8u && neuron < 16u && inputs->turn_drive < 0) return -inputs->turn_drive * 4;
    return 0;
}
void fly_cx_reset(FlyCxCircuit *circuit) { *circuit = (FlyCxCircuit){0}; }
void fly_cx_step(FlyCxCircuit *circuit, const FlyCxInputs *inputs) {
    int32_t recurrent[FLY_CX_UNITS] = {0};
    for (unsigned e = 0; e < sizeof(cx_edges) / sizeof(cx_edges[0]); ++e) {
        const FlyCxEdge *edge = &cx_edges[e];
        recurrent[edge->target] += (int32_t)circuit->activation[edge->source] *
                                  cx_weights[edge->kind].coefficient_q;
    }
    for (unsigned n = 0; n < FLY_CX_UNITS; ++n) {
        int32_t target = stimulus(n, inputs) + recurrent[n] / FLY_CX_SCALE;
        if (target < 0) target = 0;
        if (target > FLY_CX_MAXIMUM) target = FLY_CX_MAXIMUM;
        circuit->activation[n] = (int16_t)((3 * (int32_t)circuit->activation[n] + target) / 4);
    }
    for (unsigned n = FLY_CX_UNITS; n < FLY_CX_SLOTS; ++n) circuit->activation[n] = 0;
    ++circuit->epoch;
}
static int peak_sector(const FlyCxCircuit *circuit, int *strength) {
    int32_t sums[8] = {0};
    for (unsigned n = 34; n < 52; ++n) sums[cue_angle(n) / 45] += circuit->activation[n];
    int best = -1;
    *strength = 0;
    for (unsigned sector = 0; sector < 8; ++sector) {
        int average = (int)(sums[sector] / (sector ? 2 : 4));
        if (average > *strength) { best = (int)sector; *strength = average; }
    }
    return best;
}
int fly_cx_heading(const FlyCxCircuit *circuit) {
    int strength;
    int sector = peak_sector(circuit, &strength);
    return sector < 0 ? -1 : sector * 45;
}
int fly_cx_strength(const FlyCxCircuit *circuit) {
    int strength;
    (void)peak_sector(circuit, &strength);
    return strength;
}
/* An abstract, unlabeled 8x8 activity projection. It intentionally avoids the
 * baseline renderer's invented body regions and behavioral state names. */
void fly_cx_render(uint8_t *pixels, const FlyCxCircuit *circuit) {
    for (unsigned n = 0; n < 240u * 240u; ++n) pixels[n] = 0u;
    for (unsigned n = 0; n < FLY_CX_UNITS; ++n) {
        unsigned x = 16u + (n % 8u) * 27u, y = 16u + (n / 8u) * 27u;
        for (unsigned k = 0; k < 20u; ++k) {
            pixels[y * 240u + x + k] = 1u;
            pixels[(y + 19u) * 240u + x + k] = 1u;
            pixels[(y + k) * 240u + x] = 1u;
            pixels[(y + k) * 240u + x + 19u] = 1u;
        }
        unsigned size = (unsigned)circuit->activation[n] * 16u / 8192u;
        if (size > 16u) size = 16u;
        unsigned offset = (20u - size) / 2u;
        uint8_t role = circuit->activation[n] >= 8192 ? 5u : 3u;
        for (unsigned py = 0; py < size; ++py)
            for (unsigned px = 0; px < size; ++px)
                pixels[(y + offset + py) * 240u + x + offset + px] = role;
    }
}
uint32_t fly_cx_edge_count(void) { return (uint32_t)(sizeof(cx_edges) / sizeof(cx_edges[0])); }
static const FlyCxEdge *edge_at(int edge) {
    return edge < 0 || (uint32_t)edge >= fly_cx_edge_count() ? 0 : &cx_edges[edge];
}
int fly_cx_edge_source(int edge) { const FlyCxEdge *e = edge_at(edge); return e ? e->source : -1; }
int fly_cx_edge_target(int edge) { const FlyCxEdge *e = edge_at(edge); return e ? e->target : -1; }
double fly_cx_edge_raw_weight(int edge) { const FlyCxEdge *e = edge_at(edge); return e ? cx_weights[e->kind].magnitude : 0.0; }
int fly_cx_edge_sign(int edge) { const FlyCxEdge *e = edge_at(edge); return e ? (cx_weights[e->kind].coefficient_q > 0 ? 1 : -1) : 0; }
int fly_cx_edge_weight_q(int edge) { const FlyCxEdge *e = edge_at(edge); return e ? cx_weights[e->kind].coefficient_q : 0; }
