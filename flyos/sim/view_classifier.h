#ifndef FLYOS_SIM_VIEW_CLASSIFIER_H
#define FLYOS_SIM_VIEW_CLASSIFIER_H

/*
 * HOST-ONLY synthetic executable specification. Never link into firmware.
 * Addresses below are integer keys for an injected synthetic reader; this
 * module never casts them to pointers, accesses a watch, or calls native code.
 * This new model does not reproduce an inaccessible private proof or close
 * any target storage, concurrency, update-prompt, or hardware feasibility gate.
 */
#include <stdbool.h>
#include <stdint.h>

#define FLY_SIM_VIEW_ROOT_ADDRESS UINT32_C(0x20003E84)
#define FLY_SIM_VIEW_NODE_MIN UINT32_C(0x1FFC0000)
/* Inclusive last aligned node base; its final word is at 0x2003FFFC. */
#define FLY_SIM_VIEW_NODE_MAX UINT32_C(0x2003FFAC)
#define FLY_SIM_VIEW_PREV_OFFSET UINT32_C(0x00)
#define FLY_SIM_VIEW_NEXT_OFFSET UINT32_C(0x04)
#define FLY_SIM_VIEW_IDENTITY_OFFSET UINT32_C(0x08)
#define FLY_SIM_VIEW_FLAGS_OFFSET UINT32_C(0x50)
#define FLY_SIM_VIEW_HIDDEN_BIT UINT32_C(0x2)
#define FLY_SIM_VIEW_HOME_IDENTITY UINT32_C(0x0005ADF5)
#define FLY_SIM_VIEW_MAX_NODES 8u
#define FLY_SIM_VIEW_MAX_READS (2u * (2u + 4u * FLY_SIM_VIEW_MAX_NODES))

typedef enum {
    FLY_SIM_CLASS_INVALID = 0,
    FLY_SIM_CLASS_HOME,
    FLY_SIM_CLASS_NON_HOME
} FlySimViewClass;

typedef enum {
    FLY_SIM_VIEW_REASON_STABLE = 0,
    FLY_SIM_VIEW_REASON_NO_READER,
    FLY_SIM_VIEW_REASON_UNREADABLE,
    FLY_SIM_VIEW_REASON_NODE_ALIGNMENT,
    FLY_SIM_VIEW_REASON_NODE_RANGE,
    FLY_SIM_VIEW_REASON_CYCLE,
    FLY_SIM_VIEW_REASON_NODE_LIMIT,
    FLY_SIM_VIEW_REASON_REVERSE_LINK,
    FLY_SIM_VIEW_REASON_ROOT_CHANGED,
    FLY_SIM_VIEW_REASON_SNAPSHOT_CHANGED,
    FLY_SIM_VIEW_REASON_NO_VISIBLE_IDENTITY
} FlySimViewReason;

/*
 * Return true only for a known, complete, logical uint32_t value. Return false
 * for unreadable, unknown, partial, or malformed synthetic data, even if value
 * was written. No target reader is provided or authorized. Endian decoding, if
 * a fixture uses bytes, belongs to that fixture. A NULL context is allowed.
 */
typedef bool (*FlySimViewRead32)(void *context, uint32_t address,
                               uint32_t *value);

typedef struct {
    FlySimViewClass classification;
    FlySimViewReason reason;
    /* Includes failed callback calls; never exceeds FLY_SIM_VIEW_MAX_READS. */
    unsigned read_count;
    /* Populated only for HOME/NON_HOME; INVALID leaves these zero. */
    unsigned node_count;
    uint32_t first_visible_identity;
} FlySimViewResult;

/*
 * Capture all four documented fields of every reachable node twice, requiring
 * a stable root before/after each capture and identical full captures. A null
 * root is an empty list. The head's predecessor and tail's successor must be
 * zero. Every other predecessor must match the preceding node; cycles and a
 * ninth node fail closed. Invalid node addresses are never given to read32.
 *
 * Only bit 0x2 means hidden. Other flag bits are opaque, accepted as specified,
 * and compared in full between snapshots. No undocumented reserved-bit rule
 * is invented. Every stable visible identity other than HOME is NON_HOME.
 * Empty/all-hidden lists are INVALID: no first-visible identity is inferred.
 *
 * Matching sampled values are not an atomicity proof. A complete ABA change
 * restored between reads is unobservable, as are changes after the last read.
 * Even repeated matching torn observations are possible with an adversarial
 * reader. These limitations require a separate target concurrency argument;
 * the model alone cannot authorize input capture on a watch.
 */
FlySimViewResult fly_sim_classify_view(FlySimViewRead32 read32, void *context);

/* Stable human-readable diagnostics; unknown enum values return "unknown". */
const char *fly_sim_view_reason_name(FlySimViewReason reason);
const char *fly_sim_view_class_name(FlySimViewClass classification);

#endif
