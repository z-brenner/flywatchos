#ifndef FLYOS_SIM_RATE_REFERENCE_H
#define FLYOS_SIM_RATE_REFERENCE_H
/* HOST-ONLY deterministic source-drift reference. No target ABI. */
#include <stdint.h>
#define FLY_RATE_UNITS 60u
#define FLY_RATE_MAX_UPDATES_PER_CALL 1000u
#define FLY_RATE_MAX_EPOCH 10000000u
/* Zero initial signed state and zero input; the source RNG is disabled. */
void fly_rate_reset(void);
/* Atomic control: integer angle 0..359, cue 0..200, turn -200..200, all finite.
 * Inputs are normalized rate-equivalent current, NOT Hz or angular velocity. */
int fly_rate_set_stimulus(double angle, double cue, double turn);
/* Fixed 0.1 ms synchronous Euler. Accept integer 1..1000 updates only, up to
 * max epoch. Failure returns 0 without changing state, inputs or elapsed time. */
int fly_rate_step(double updates);
/* Read-only 60 doubles: u=100*(V-V0), signed and unclipped. Stable address. */
const double *fly_rate_state(void);
/* Signed tanh(u), not spike rate; invalid indices return0. */
double fly_rate_transfer(int index);
uint32_t fly_rate_unit_count(void);
uint32_t fly_rate_epoch(void);
double fly_rate_time_ms(void);
double fly_rate_dt_ms(void);
double fly_rate_stimulus_angle(void);
double fly_rate_stimulus_cue(void);
double fly_rate_stimulus_turn(void);
#endif
