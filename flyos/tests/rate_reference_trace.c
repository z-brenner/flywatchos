/* Native numerical trace. Test-only signed-state injection is never an export. */
#include "sim/rate_reference.h"
#include <stdio.h>
#include <stdlib.h>
#define REQUIRE(c) do { if (!(c)) exit(1); } while(0)
static void vector(void) {
    putchar('[');
    for (unsigned n=0;n<60;++n) printf("%s%.17g",n ? "," : "",fly_rate_state()[n]);
    putchar(']');
}
static void advance(unsigned target) {
    while (fly_rate_epoch()<target) {
        unsigned count=target-fly_rate_epoch();
        REQUIRE(fly_rate_step(count>1000 ? 1000 : count));
    }
}
int main(void) {
    const unsigned samples[]={1,2,10,100,1000,7500,7501,10000,20000,40000};
    fly_rate_reset(); REQUIRE(fly_rate_set_stimulus(90,200,0));
    printf("{\"dt_ms\":%.17g,\"snapshots\":{",fly_rate_dt_ms());
    for (unsigned k=0;k<sizeof(samples)/sizeof(samples[0]);++k) {
        if (samples[k]>7500) REQUIRE(fly_rate_set_stimulus(90,0,0));
        advance(samples[k]); printf("%s\"%u\":",k ? "," : "",samples[k]); vector();
    }
    printf("},\"signed_initial_one_step\":");
    fly_rate_reset();
    for (unsigned n=0;n<60;++n) ((double *)(void *)fly_rate_state())[n]=-.3+(.6/59)*n;
    REQUIRE(fly_rate_set_stimulus(225,80,-30)); REQUIRE(fly_rate_step(1)); vector();
    printf(",\"zero_input_after_40000_updates\":"); fly_rate_reset(); advance(40000); vector();
    printf(",\"turn_probes\":{");
    for (int sign=-1;sign<=1;sign+=2) {
        fly_rate_reset(); REQUIRE(fly_rate_set_stimulus(90,200,0)); advance(7500);
        REQUIRE(fly_rate_set_stimulus(90,0,0)); advance(10000);
        REQUIRE(fly_rate_set_stimulus(90,0,sign*50)); advance(20000);
        REQUIRE(fly_rate_set_stimulus(90,0,0)); advance(40000);
        printf("%s\"%d\":",sign==-1 ? "" : ",",sign*50); vector();
    }
    printf("}}\n"); return 0;
}
