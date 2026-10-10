#include "sim/view_classifier.h"

#include <stddef.h>

typedef struct {
    uint32_t address;
    uint32_t prev;
    uint32_t next;
    uint32_t identity;
    uint32_t flags;
} ViewNode;

typedef struct {
    uint32_t root;
    unsigned count;
    ViewNode nodes[FLY_SIM_VIEW_MAX_NODES];
} ViewSnapshot;

static bool read_word(FlySimViewRead32 read32, void *context, uint32_t address,
                      uint32_t *value, FlySimViewResult *result) {
    ++result->read_count;
    return read32(context, address, value);
}

static FlySimViewReason capture(FlySimViewRead32 read32, void *context,
                                ViewSnapshot *snapshot,
                                FlySimViewResult *result) {
    uint32_t previous = 0u;
    uint32_t final_root = 0u;
    if (!read_word(read32, context, FLY_SIM_VIEW_ROOT_ADDRESS,
                   &snapshot->root, result)) {
        return FLY_SIM_VIEW_REASON_UNREADABLE;
    }
    uint32_t address = snapshot->root;
    while (address != 0u) {
        if ((address & UINT32_C(3)) != 0u) {
            return FLY_SIM_VIEW_REASON_NODE_ALIGNMENT;
        }
        if (address < FLY_SIM_VIEW_NODE_MIN || address > FLY_SIM_VIEW_NODE_MAX) {
            return FLY_SIM_VIEW_REASON_NODE_RANGE;
        }
        for (unsigned i = 0u; i < snapshot->count; ++i) {
            if (snapshot->nodes[i].address == address) {
                return FLY_SIM_VIEW_REASON_CYCLE;
            }
        }
        if (snapshot->count == FLY_SIM_VIEW_MAX_NODES) {
            return FLY_SIM_VIEW_REASON_NODE_LIMIT;
        }
        ViewNode *node = &snapshot->nodes[snapshot->count];
        node->address = address;
        /* Range checking the base makes every offset addition non-overflowing. */
        if (!read_word(read32, context, address + FLY_SIM_VIEW_PREV_OFFSET,
                       &node->prev, result) ||
            !read_word(read32, context, address + FLY_SIM_VIEW_NEXT_OFFSET,
                       &node->next, result) ||
            !read_word(read32, context, address + FLY_SIM_VIEW_IDENTITY_OFFSET,
                       &node->identity, result) ||
            !read_word(read32, context, address + FLY_SIM_VIEW_FLAGS_OFFSET,
                       &node->flags, result)) {
            return FLY_SIM_VIEW_REASON_UNREADABLE;
        }
        /* The forward edge selected this node; require its reciprocal edge. */
        if (node->prev != previous) {
            return FLY_SIM_VIEW_REASON_REVERSE_LINK;
        }
        ++snapshot->count;
        previous = address;
        address = node->next;
    }
    if (!read_word(read32, context, FLY_SIM_VIEW_ROOT_ADDRESS,
                   &final_root, result)) {
        return FLY_SIM_VIEW_REASON_UNREADABLE;
    }
    if (snapshot->root != final_root) {
        return FLY_SIM_VIEW_REASON_ROOT_CHANGED;
    }
    return FLY_SIM_VIEW_REASON_STABLE;
}

static bool snapshots_match(const ViewSnapshot *left,
                             const ViewSnapshot *right) {
    if (left->root != right->root || left->count != right->count) {
        return false;
    }
    for (unsigned i = 0u; i < left->count; ++i) {
        const ViewNode *a = &left->nodes[i];
        const ViewNode *b = &right->nodes[i];
        /* Compare fields, not object padding. Opaque flags still participate. */
        if (a->address != b->address || a->prev != b->prev ||
            a->next != b->next || a->identity != b->identity ||
            a->flags != b->flags) {
            return false;
        }
    }
    return true;
}

FlySimViewResult fly_sim_classify_view(FlySimViewRead32 read32, void *context) {
    FlySimViewResult result = {0};
    ViewSnapshot snapshots[2] = {0};
    if (read32 == NULL) {
        result.reason = FLY_SIM_VIEW_REASON_NO_READER;
        return result;
    }
    for (unsigned i = 0u; i < 2u; ++i) {
        result.reason = capture(read32, context, &snapshots[i], &result);
        if (result.reason != FLY_SIM_VIEW_REASON_STABLE) {
            return result;
        }
    }
    if (!snapshots_match(&snapshots[0], &snapshots[1])) {
        result.reason = FLY_SIM_VIEW_REASON_SNAPSHOT_CHANGED;
        return result;
    }
    for (unsigned i = 0u; i < snapshots[0].count; ++i) {
        const ViewNode *node = &snapshots[0].nodes[i];
        if ((node->flags & FLY_SIM_VIEW_HIDDEN_BIT) == 0u) {
            result.node_count = snapshots[0].count;
            result.first_visible_identity = node->identity;
            result.classification = node->identity == FLY_SIM_VIEW_HOME_IDENTITY
                ? FLY_SIM_CLASS_HOME : FLY_SIM_CLASS_NON_HOME;
            return result;
        }
    }
    result.reason = FLY_SIM_VIEW_REASON_NO_VISIBLE_IDENTITY;
    return result;
}

const char *fly_sim_view_reason_name(FlySimViewReason reason) {
    switch (reason) {
        case FLY_SIM_VIEW_REASON_STABLE: return "stable";
        case FLY_SIM_VIEW_REASON_NO_READER: return "no-reader";
        case FLY_SIM_VIEW_REASON_UNREADABLE: return "unreadable";
        case FLY_SIM_VIEW_REASON_NODE_ALIGNMENT: return "node-alignment";
        case FLY_SIM_VIEW_REASON_NODE_RANGE: return "node-range";
        case FLY_SIM_VIEW_REASON_CYCLE: return "cycle";
        case FLY_SIM_VIEW_REASON_NODE_LIMIT: return "node-limit";
        case FLY_SIM_VIEW_REASON_REVERSE_LINK: return "reverse-link";
        case FLY_SIM_VIEW_REASON_ROOT_CHANGED: return "root-changed";
        case FLY_SIM_VIEW_REASON_SNAPSHOT_CHANGED: return "snapshot-changed";
        case FLY_SIM_VIEW_REASON_NO_VISIBLE_IDENTITY: return "no-visible-identity";
    }
    return "unknown";
}

const char *fly_sim_view_class_name(FlySimViewClass classification) {
    switch (classification) {
        case FLY_SIM_CLASS_INVALID: return "INVALID";
        case FLY_SIM_CLASS_HOME: return "HOME";
        case FLY_SIM_CLASS_NON_HOME: return "NON_HOME";
    }
    return "unknown";
}
