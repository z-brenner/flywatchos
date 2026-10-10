#include "sim/rate_reference.h"
#ifndef FLY_NEURAL_SPECIMEN_HOST_PREVIEW
#error "rate_reference is host-only and must never be linked into watch firmware"
#endif
#include <math.h>

typedef struct { uint8_t source, target; double weight; } FlyRateEdge;
#include "sim/rate_reference_connectivity.inc"
static double state[FLY_RATE_UNITS];
static double cue_angle, cue_rate, turn_rate;
static uint32_t epoch;

/* Exact deterministic drift algebra from pinned flyLI2.m:
 * u=100*(V-V0), C=2e-8 F, R=1e6 ohm, inCurrent=3e-10 A.
 * tau=20ms; u'=(-u + .03*sum(W*tanh(u)) + .03*input)/tau.
 * Source Gaussian noise is OFF; direct chosen triangular forcing does NOT
 * reproduce the source centered spike smoothing/global normalization.
 * Signed u and tanh(u) are never rectified or clipped. */
void fly_rate_reset(void) {
    for (unsigned n=0;n<FLY_RATE_UNITS;++n) state[n]=0;
    cue_angle=cue_rate=turn_rate=0;
    epoch=0;
}
int fly_rate_set_stimulus(double angle,double cue,double turn) {
    if (!isfinite(angle) || !isfinite(cue) || !isfinite(turn) ||
        angle<0 || angle>359 || floor(angle)!=angle ||
        cue<0 || cue>200 || turn< -200 || turn>200) return 0;
    cue_angle=angle; cue_rate=cue; turn_rate=turn;
    return 1;
}
static double input_for(unsigned n) {
    if (n>=34u && n<52u) {
        double distance=fabs((double)(((n-34u)%9u)%8u)*45-cue_angle);
        if (distance>180) distance=360-distance;
        return distance<90 ? cue_rate*(1-distance/90) : 0;
    }
    if (n<8u && turn_rate>0) return turn_rate;
    if (n>=8u && n<16u && turn_rate<0) return -turn_rate;
    return 0;
}
int fly_rate_step(double updates) {
    double next[FLY_RATE_UNITS], input[FLY_RATE_UNITS];
    if (!isfinite(updates) || updates<1 || updates>FLY_RATE_MAX_UPDATES_PER_CALL ||
        floor(updates)!=updates || epoch>FLY_RATE_MAX_EPOCH || updates>FLY_RATE_MAX_EPOCH-epoch) return 0;
    for (unsigned n=0;n<FLY_RATE_UNITS;++n) {
        if (!isfinite(state[n])) return 0;
        next[n]=state[n]; input[n]=input_for(n);
        if (!isfinite(input[n])) return 0;
    }
    for (uint32_t k=0;k<(uint32_t)updates;++k) {
        double transfer[FLY_RATE_UNITS], recurrent[FLY_RATE_UNITS]={0};
        for (unsigned n=0;n<FLY_RATE_UNITS;++n) transfer[n]=tanh(next[n]);
        for (unsigned e=0;e<sizeof(rate_edges)/sizeof(rate_edges[0]);++e) {
            const FlyRateEdge *edge=&rate_edges[e];
            recurrent[edge->target]+=edge->weight*transfer[edge->source];
        }
        for (unsigned n=0;n<FLY_RATE_UNITS;++n) {
            next[n]+=0.005*(-next[n]+0.03*recurrent[n]+0.03*input[n]);
            if (!isfinite(next[n])) return 0;
        }
    }
    /* Commit only after every update succeeds. No failed call partially steps. */
    for (unsigned n=0;n<FLY_RATE_UNITS;++n) state[n]=next[n];
    epoch+=(uint32_t)updates;
    return 1;
}
const double *fly_rate_state(void) { return state; }
double fly_rate_transfer(int index) { return index>=0 && index<(int)FLY_RATE_UNITS ? tanh(state[index]) : 0; }
uint32_t fly_rate_unit_count(void) { return FLY_RATE_UNITS; }
uint32_t fly_rate_epoch(void) { return epoch; }
double fly_rate_time_ms(void) { return (double)epoch*0.1; }
double fly_rate_dt_ms(void) { return 0.1; }
double fly_rate_stimulus_angle(void) { return cue_angle; }
double fly_rate_stimulus_cue(void) { return cue_rate; }
double fly_rate_stimulus_turn(void) { return turn_rate; }
