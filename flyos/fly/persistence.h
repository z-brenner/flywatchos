#ifndef FLYOS_FLY_PERSISTENCE_H
#define FLYOS_FLY_PERSISTENCE_H

#include "fly/network.h"

#include <stdint.h>

#define FLY_PERSIST_OK 0
#define FLY_PERSIST_NOT_FOUND 1
#define FLY_PERSIST_IO_ERROR 2
#define FLY_PERSIST_INVALID 3

enum {
    FLY_LIFECYCLE_CONTINUE = 0,
    FLY_LIFECYCLE_NEW_IDENTITY_AFTER_POWER_LOSS = 1
};

typedef struct {
    uint32_t identity_seed;
    uint32_t birth_time_seconds;
    uint32_t accumulated_age_seconds;
    uint32_t sequence;
    FlyNetwork network;
    uint8_t lifecycle_policy;
    uint8_t reserved[15];
} FlyPersistentState;

void fly_persistent_state_init(FlyPersistentState *state, uint32_t identity_seed);
int fly_persistence_save(const char *base_path, FlyPersistentState *state);
int fly_persistence_load(const char *base_path, FlyPersistentState *state);
void fly_persistence_remove(const char *base_path);

/* Test helper for proving recovery from a torn/corrupt newest write. */
int fly_persistence_corrupt_newest_for_test(const char *base_path);

#endif
