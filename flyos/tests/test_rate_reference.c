/* Contract tests for the separate host-only source drift reference. */
#include "sim/rate_reference.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(c) do { if (!(c)) { fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#c); exit(1); } } while (0)
static void close_to(double actual, double expected) { CHECK(fabs(actual-expected) <= 1e-12); }
static void test_zero_and_first_step(void) {
    fly_rate_reset();
    CHECK(fly_rate_unit_count()==60 && fly_rate_epoch()==0);
    CHECK(fly_rate_time_ms()==0 && fly_rate_dt_ms()==0.1);
    CHECK(fly_rate_step(1000)==1);
    for (int i=0;i<60;++i) CHECK(fly_rate_state()[i]==0 && fly_rate_transfer(i)==0);
    fly_rate_reset();
    CHECK(fly_rate_set_stimulus(90,200,0)==1 && fly_rate_step(1)==1);
    for (int i=0;i<60;++i) {
        double expected=0;
        if (i>=34 && i<52) {
            int sector=(i-34)%9;
            if (sector==2) expected=.03;
            if (sector==1 || sector==3) expected=.015;
        }
        close_to(fly_rate_state()[i],expected);
        close_to(fly_rate_transfer(i),tanh(expected));
    }
    CHECK(fly_rate_epoch()==1); close_to(fly_rate_time_ms(),.1);
}
static void test_turn_targets(void) {
    for (int sign=-1;sign<=1;sign+=2) {
        fly_rate_reset(); CHECK(fly_rate_set_stimulus(0,0,sign*200)==1);
        CHECK(fly_rate_step(1)==1);
        for (int i=0;i<60;++i) close_to(fly_rate_state()[i],
            ((sign==1 && i<8) || (sign==-1 && i>=8 && i<16)) ? .03 : 0);
    }
}
static void test_rejection_is_atomic(void) {
    double saved[60]; const double bad[]={NAN,INFINITY,-INFINITY,-1,360,1.5};
    fly_rate_reset(); CHECK(fly_rate_set_stimulus(90,123,-45)==1); CHECK(fly_rate_step(40)==1);
    memcpy(saved,fly_rate_state(),sizeof(saved));
    for (unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);++i) CHECK(fly_rate_set_stimulus(bad[i],0,0)==0);
    const double invalid_rates[]={NAN,INFINITY,-INFINITY,-.01,200.01};
    for (unsigned i=0;i<sizeof(invalid_rates)/sizeof(invalid_rates[0]);++i) CHECK(fly_rate_set_stimulus(0,invalid_rates[i],0)==0);
    CHECK(fly_rate_set_stimulus(0,0,200.01)==0 && fly_rate_set_stimulus(0,0,-200.01)==0);
    CHECK(fly_rate_set_stimulus(0,0,NAN)==0 && fly_rate_set_stimulus(0,0,INFINITY)==0);
    const double invalid_steps[]={NAN,INFINITY,-INFINITY,-1,0,.5,1001,1e30};
    for (unsigned i=0;i<sizeof(invalid_steps)/sizeof(invalid_steps[0]);++i) CHECK(fly_rate_step(invalid_steps[i])==0);
    CHECK(memcmp(saved,fly_rate_state(),sizeof(saved))==0 && fly_rate_epoch()==40);
    CHECK(fly_rate_stimulus_angle()==90 && fly_rate_stimulus_cue()==123 && fly_rate_stimulus_turn()==-45);
    CHECK(fly_rate_transfer(-1)==0 && fly_rate_transfer(60)==0);
    /* Hostile callers can write Wasm memory. Reject a corrupt state before committing. */
    ((double *)(void *)fly_rate_state())[59]=NAN;
    CHECK(fly_rate_step(10)==0 && fly_rate_epoch()==40);
    for (int i=0;i<59;++i) CHECK(fly_rate_state()[i]==saved[i]);
    fly_rate_reset(); CHECK(fly_rate_epoch()==0 && fly_rate_stimulus_cue()==0 && fly_rate_stimulus_turn()==0);
}
static void test_signed_bounded_reproducible_and_chunk_independent(void) {
    double saved[60]; int negative=0;
    fly_rate_reset(); CHECK(fly_rate_set_stimulus(90,200,0)==1);
    for (int i=0;i<8;++i) CHECK(fly_rate_step(1000)==1);
    memcpy(saved,fly_rate_state(),sizeof(saved));
    for (int i=0;i<60;++i) { CHECK(isfinite(saved[i]) && fabs(saved[i])<=33.061); if (saved[i]<0) negative=1; }
    CHECK(negative);
    fly_rate_reset(); CHECK(fly_rate_set_stimulus(90,200,0)==1);
    for (int i=0;i<8000;++i) CHECK(fly_rate_step(1)==1);
    CHECK(memcmp(saved,fly_rate_state(),sizeof(saved))==0);
    for (int i=0;i<40;++i) {
        CHECK(fly_rate_set_stimulus((i*91)%360,200,i%2 ? -200:200)==1);
        CHECK(fly_rate_step(1000)==1);
        for(int j=0;j<60;++j) CHECK(isfinite(fly_rate_state()[j]) && fabs(fly_rate_state()[j])<=33.061);
    }
}
static void test_total_epoch_cap_is_atomic(void) {
    fly_rate_reset();
    for (unsigned i=0;i<FLY_RATE_MAX_EPOCH/1000-1;++i) CHECK(fly_rate_step(1000)==1);
    CHECK(fly_rate_step(999)==1 && fly_rate_epoch()==FLY_RATE_MAX_EPOCH-1);
    CHECK(fly_rate_step(2)==0 && fly_rate_epoch()==FLY_RATE_MAX_EPOCH-1);
    CHECK(fly_rate_step(1)==1 && fly_rate_epoch()==FLY_RATE_MAX_EPOCH);
    CHECK(fly_rate_step(1)==0 && fly_rate_epoch()==FLY_RATE_MAX_EPOCH);
    for (int i=0;i<60;++i) CHECK(fly_rate_state()[i]==0);
    fly_rate_reset(); CHECK(fly_rate_step(1)==1);
}
int main(void) {
    test_zero_and_first_step(); test_turn_targets(); test_rejection_is_atomic();
    test_signed_bounded_reproducible_and_chunk_independent();
    test_total_epoch_cap_is_atomic();
    puts("Rate reference: source-step, signed state, atomic finite rejection, bounds and deterministic chunks passed");
    return 0;
}
