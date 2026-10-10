#include "sim/view_classifier.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(condition)                                                       \
    do {                                                                       \
        if (!(condition)) {                                                    \
            fprintf(stderr, "check failed: %s (%s:%d)\n", #condition,          \
                    __FILE__, __LINE__);                                       \
            exit(EXIT_FAILURE);                                                \
        }                                                                      \
    } while (0)

#define FIXTURE_CAPACITY 10u
#define FIXTURE_BASE UINT32_C(0x1FFD0000)
#define FIXTURE_STRIDE UINT32_C(0x100)

typedef struct {
    uint32_t address;
    uint32_t prev;
    uint32_t next;
    uint32_t identity;
    uint32_t flags;
} SyntheticNode;

typedef struct SyntheticMemory SyntheticMemory;
typedef void (*ReadMutation)(SyntheticMemory *memory, uint32_t address);

struct SyntheticMemory {
    uint32_t root;
    SyntheticNode nodes[FIXTURE_CAPACITY];
    unsigned node_count;
    unsigned reads;
    unsigned fail_read;
    unsigned mutation_count;
    ReadMutation before_read;
    uint32_t read_addresses[FLY_SIM_VIEW_MAX_READS];
};

static SyntheticMemory make_list(unsigned count) {
    SyntheticMemory memory = {0};
    CHECK(count <= FIXTURE_CAPACITY);
    memory.node_count = count;
    memory.root = count == 0u ? 0u : FIXTURE_BASE;
    for (unsigned i = 0u; i < count; ++i) {
        memory.nodes[i].address = FIXTURE_BASE + i * FIXTURE_STRIDE;
        memory.nodes[i].prev = i == 0u ? 0u :
            FIXTURE_BASE + (i - 1u) * FIXTURE_STRIDE;
        memory.nodes[i].next = i + 1u == count ? 0u :
            FIXTURE_BASE + (i + 1u) * FIXTURE_STRIDE;
        memory.nodes[i].identity = FLY_SIM_VIEW_HOME_IDENTITY;
    }
    return memory;
}

static bool synthetic_read32(void *context, uint32_t address, uint32_t *value) {
    SyntheticMemory *memory = context;
    ++memory->reads;
    CHECK(memory->reads <= FLY_SIM_VIEW_MAX_READS);
    memory->read_addresses[memory->reads - 1u] = address;
    if (memory->before_read != NULL) {
        memory->before_read(memory, address);
    }
    if (memory->reads == memory->fail_read) {
        /* A failed reader must not make this plausible HOME value trusted. */
        *value = FLY_SIM_VIEW_HOME_IDENTITY;
        return false;
    }
    if (address == FLY_SIM_VIEW_ROOT_ADDRESS) {
        *value = memory->root;
        return true;
    }
    for (unsigned i = 0u; i < memory->node_count; ++i) {
        const SyntheticNode *node = &memory->nodes[i];
        if (address == node->address + FLY_SIM_VIEW_PREV_OFFSET) {
            *value = node->prev;
            return true;
        }
        if (address == node->address + FLY_SIM_VIEW_NEXT_OFFSET) {
            *value = node->next;
            return true;
        }
        if (address == node->address + FLY_SIM_VIEW_IDENTITY_OFFSET) {
            *value = node->identity;
            return true;
        }
        if (address == node->address + FLY_SIM_VIEW_FLAGS_OFFSET) {
            *value = node->flags;
            return true;
        }
    }
    return false;
}

static void test_home_requires_two_complete_captures(void) {
    SyntheticMemory memory = make_list(1u);
    const FlySimViewResult result = fly_sim_classify_view(synthetic_read32,
                                                         &memory);
    CHECK(result.classification == FLY_SIM_CLASS_HOME);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_STABLE);
    CHECK(result.node_count == 1u);
    CHECK(result.first_visible_identity == FLY_SIM_VIEW_HOME_IDENTITY);
    CHECK(result.read_count == 12u);
    CHECK(result.read_count == memory.reads);
}

static FlySimViewResult classify(SyntheticMemory *memory) {
    const FlySimViewResult result = fly_sim_classify_view(synthetic_read32,
                                                         memory);
    CHECK(result.read_count == memory->reads);
    CHECK(result.read_count <= FLY_SIM_VIEW_MAX_READS);
    if (result.classification == FLY_SIM_CLASS_INVALID) {
        CHECK(result.node_count == 0u);
        CHECK(result.first_visible_identity == 0u);
    }
    return result;
}

static void test_synthetic_update_identity_is_non_home(void) {
    SyntheticMemory memory = make_list(2u);
    /* SYNTHETIC ONLY: not a captured historical Install Now/Later fixture. */
    memory.nodes[0].identity = UINT32_C(0x046AA84D);
    const FlySimViewResult result = classify(&memory);
    CHECK(result.classification == FLY_SIM_CLASS_NON_HOME);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_STABLE);
    CHECK(result.first_visible_identity == UINT32_C(0x046AA84D));
    CHECK(result.node_count == 2u);
    CHECK(result.read_count == 20u);
}

static void test_hidden_first_node_does_not_mask_first_visible(void) {
    for (unsigned home = 0u; home < 2u; ++home) {
        SyntheticMemory memory = make_list(3u);
        memory.nodes[0].flags = FLY_SIM_VIEW_HIDDEN_BIT;
        memory.nodes[0].identity = home != 0u ? UINT32_C(0x12345679) :
            FLY_SIM_VIEW_HOME_IDENTITY;
        memory.nodes[1].identity = home != 0u ? FLY_SIM_VIEW_HOME_IDENTITY :
            UINT32_C(0x12345679);
        const FlySimViewResult result = classify(&memory);
        CHECK(result.classification == (home != 0u ? FLY_SIM_CLASS_HOME :
                                                     FLY_SIM_CLASS_NON_HOME));
        CHECK(result.first_visible_identity == memory.nodes[1].identity);
        CHECK(result.read_count == 28u);
    }
}

static void test_zero_identity_is_non_home_not_unknown_home(void) {
    SyntheticMemory memory = make_list(1u);
    memory.nodes[0].identity = 0u;
    const FlySimViewResult result = classify(&memory);
    CHECK(result.classification == FLY_SIM_CLASS_NON_HOME);
    CHECK(result.first_visible_identity == 0u);
}

static void test_empty_and_all_hidden_fail_safe(void) {
    for (unsigned count = 0u; count <= FLY_SIM_VIEW_MAX_NODES; ++count) {
        SyntheticMemory memory = make_list(count);
        for (unsigned i = 0u; i < count; ++i) {
            memory.nodes[i].flags = FLY_SIM_VIEW_HIDDEN_BIT;
        }
        const FlySimViewResult result = classify(&memory);
        CHECK(result.classification == FLY_SIM_CLASS_INVALID);
        CHECK(result.reason == FLY_SIM_VIEW_REASON_NO_VISIBLE_IDENTITY);
    }
}

static void test_flags_use_only_documented_hidden_bit(void) {
    static const uint32_t visible_flags[] = {
        0u, 1u, 4u, UINT32_C(0x80000000), UINT32_C(0xFFFFFFFD)
    };
    for (unsigned i = 0u;
         i < sizeof(visible_flags) / sizeof(visible_flags[0]); ++i) {
        SyntheticMemory memory = make_list(1u);
        memory.nodes[0].flags = visible_flags[i];
        CHECK(classify(&memory).classification == FLY_SIM_CLASS_HOME);
        memory.reads = 0u;
        memory.nodes[0].flags |= FLY_SIM_VIEW_HIDDEN_BIT;
        const FlySimViewResult hidden = classify(&memory);
        CHECK(hidden.classification == FLY_SIM_CLASS_INVALID);
        CHECK(hidden.reason == FLY_SIM_VIEW_REASON_NO_VISIBLE_IDENTITY);
    }
}

static void test_missing_reader_fails_without_reads(void) {
    const FlySimViewResult result = fly_sim_classify_view(NULL, NULL);
    CHECK(result.classification == FLY_SIM_CLASS_INVALID);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_NO_READER);
    CHECK(result.read_count == 0u);
    CHECK(result.node_count == 0u);
    CHECK(result.first_visible_identity == 0u);
}

static bool contextless_empty_reader(void *context, uint32_t address,
                                     uint32_t *value) {
    CHECK(context == NULL);
    CHECK(address == FLY_SIM_VIEW_ROOT_ADDRESS);
    *value = 0u;
    return true;
}

static void test_null_context_is_reader_defined(void) {
    const FlySimViewResult result = fly_sim_classify_view(
        contextless_empty_reader, NULL);
    CHECK(result.classification == FLY_SIM_CLASS_INVALID);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_NO_VISIBLE_IDENTITY);
    CHECK(result.read_count == 4u);
}

static void test_reader_failure_at_every_read_fails_closed(void) {
    for (unsigned failure = 1u; failure <= FLY_SIM_VIEW_MAX_READS; ++failure) {
        SyntheticMemory memory = make_list(FLY_SIM_VIEW_MAX_NODES);
        memory.fail_read = failure;
        const FlySimViewResult result = classify(&memory);
        CHECK(result.classification == FLY_SIM_CLASS_INVALID);
        CHECK(result.reason == FLY_SIM_VIEW_REASON_UNREADABLE);
        CHECK(result.read_count == failure);
    }
}

static void test_unmapped_node_is_unreadable(void) {
    SyntheticMemory memory = make_list(1u);
    memory.nodes[0].next = FIXTURE_BASE + FIXTURE_STRIDE;
    const FlySimViewResult result = classify(&memory);
    CHECK(result.classification == FLY_SIM_CLASS_INVALID);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_UNREADABLE);
    CHECK(result.read_count == 6u);
}

static void test_boundary_addresses_and_alignment(void) {
    static const uint32_t allowed[] = {
        FLY_SIM_VIEW_NODE_MIN, FLY_SIM_VIEW_NODE_MIN + 4u,
        FLY_SIM_VIEW_NODE_MAX - 4u, FLY_SIM_VIEW_NODE_MAX
    };
    for (unsigned i = 0u; i < sizeof(allowed) / sizeof(allowed[0]); ++i) {
        SyntheticMemory memory = make_list(1u);
        memory.root = allowed[i];
        memory.nodes[0].address = allowed[i];
        CHECK(classify(&memory).classification == FLY_SIM_CLASS_HOME);
        CHECK(memory.read_addresses[4] == allowed[i] +
                                               FLY_SIM_VIEW_FLAGS_OFFSET);
    }
    static const uint32_t outside[] = {
        4u, FLY_SIM_VIEW_NODE_MIN - 4u, FLY_SIM_VIEW_NODE_MAX + 4u,
        UINT32_C(0xFFFFFFFC)
    };
    for (unsigned i = 0u; i < sizeof(outside) / sizeof(outside[0]); ++i) {
        SyntheticMemory memory = make_list(1u);
        memory.root = outside[i];
        const FlySimViewResult result = classify(&memory);
        CHECK(result.classification == FLY_SIM_CLASS_INVALID);
        CHECK(result.reason == FLY_SIM_VIEW_REASON_NODE_RANGE);
        CHECK(result.read_count == 1u);
    }
    for (unsigned offset = 1u; offset <= 3u; ++offset) {
        SyntheticMemory memory = make_list(1u);
        memory.root += offset;
        const FlySimViewResult result = classify(&memory);
        CHECK(result.classification == FLY_SIM_CLASS_INVALID);
        CHECK(result.reason == FLY_SIM_VIEW_REASON_NODE_ALIGNMENT);
        CHECK(result.read_count == 1u);
    }
}

static void test_bad_successors_are_never_read(void) {
    static const uint32_t bad_next[] = {
        FLY_SIM_VIEW_NODE_MIN - 4u, FLY_SIM_VIEW_NODE_MAX + 4u,
        UINT32_MAX, FIXTURE_BASE + 1u
    };
    for (unsigned i = 0u; i < sizeof(bad_next) / sizeof(bad_next[0]); ++i) {
        SyntheticMemory memory = make_list(1u);
        memory.nodes[0].next = bad_next[i];
        const FlySimViewResult result = classify(&memory);
        CHECK(result.classification == FLY_SIM_CLASS_INVALID);
        CHECK(result.reason == ((bad_next[i] & 3u) != 0u ?
              FLY_SIM_VIEW_REASON_NODE_ALIGNMENT : FLY_SIM_VIEW_REASON_NODE_RANGE));
        CHECK(result.read_count == 5u);
    }
}

static void test_reverse_links_must_match_forward_traversal(void) {
    static const uint32_t wrong_prev[] = {
        0u, FIXTURE_BASE + FIXTURE_STRIDE, FLY_SIM_VIEW_NODE_MIN - 4u,
        FIXTURE_BASE + 1u, UINT32_MAX
    };
    for (unsigned i = 0u; i < sizeof(wrong_prev) / sizeof(wrong_prev[0]); ++i) {
        SyntheticMemory memory = make_list(2u);
        memory.nodes[1].prev = wrong_prev[i];
        const FlySimViewResult result = classify(&memory);
        CHECK(result.classification == FLY_SIM_CLASS_INVALID);
        CHECK(result.reason == FLY_SIM_VIEW_REASON_REVERSE_LINK);
    }
    SyntheticMemory head = make_list(1u);
    head.nodes[0].prev = head.nodes[0].address;
    const FlySimViewResult result = classify(&head);
    CHECK(result.classification == FLY_SIM_CLASS_INVALID);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_REVERSE_LINK);
}

static void test_all_cycles_fail_before_any_node_is_reread(void) {
    for (unsigned count = 1u; count <= FLY_SIM_VIEW_MAX_NODES; ++count) {
        for (unsigned entry = 0u; entry < count; ++entry) {
            SyntheticMemory memory = make_list(count);
            memory.nodes[count - 1u].next = memory.nodes[entry].address;
            const FlySimViewResult result = classify(&memory);
            CHECK(result.classification == FLY_SIM_CLASS_INVALID);
            CHECK(result.reason == FLY_SIM_VIEW_REASON_CYCLE);
            CHECK(result.read_count == 1u + 4u * count);
        }
    }
}

static void test_eight_nodes_are_read_fully_and_ninth_is_not(void) {
    SyntheticMemory eight = make_list(FLY_SIM_VIEW_MAX_NODES);
    const FlySimViewResult accepted = classify(&eight);
    CHECK(accepted.classification == FLY_SIM_CLASS_HOME);
    CHECK(accepted.node_count == FLY_SIM_VIEW_MAX_NODES);
    CHECK(accepted.read_count == FLY_SIM_VIEW_MAX_READS);
    SyntheticMemory nine = make_list(FLY_SIM_VIEW_MAX_NODES + 1u);
    const FlySimViewResult rejected = classify(&nine);
    CHECK(rejected.classification == FLY_SIM_CLASS_INVALID);
    CHECK(rejected.reason == FLY_SIM_VIEW_REASON_NODE_LIMIT);
    CHECK(rejected.read_count == 33u);
    for (unsigned i = 0u; i < rejected.read_count; ++i) {
        CHECK(nine.read_addresses[i] == FLY_SIM_VIEW_ROOT_ADDRESS ||
              nine.read_addresses[i] < nine.nodes[8].address);
    }
}

static void change_root_within_first_capture(SyntheticMemory *memory,
                                            uint32_t address) {
    (void)address;
    if (memory->reads == 6u) {
        memory->root = 0u;
        ++memory->mutation_count;
    }
}

static void change_root_within_second_capture(SyntheticMemory *memory,
                                             uint32_t address) {
    (void)address;
    if (memory->reads == 12u) {
        memory->root = 0u;
        ++memory->mutation_count;
    }
}

static void change_root_between_captures(SyntheticMemory *memory,
                                        uint32_t address) {
    (void)address;
    if (memory->reads == 7u) {
        memory->root = 0u;
        ++memory->mutation_count;
    }
}

static void test_root_changes_within_either_capture_are_invalid(void) {
    static const ReadMutation mutations[] = {
        change_root_within_first_capture, change_root_within_second_capture
    };
    for (unsigned i = 0u; i < sizeof(mutations) / sizeof(mutations[0]); ++i) {
        SyntheticMemory memory = make_list(1u);
        memory.before_read = mutations[i];
        const FlySimViewResult result = classify(&memory);
        CHECK(result.classification == FLY_SIM_CLASS_INVALID);
        CHECK(result.reason == FLY_SIM_VIEW_REASON_ROOT_CHANGED);
        CHECK(memory.mutation_count == 1u);
    }
}

static void test_root_change_between_captures_is_invalid(void) {
    SyntheticMemory memory = make_list(1u);
    memory.before_read = change_root_between_captures;
    const FlySimViewResult result = classify(&memory);
    CHECK(result.classification == FLY_SIM_CLASS_INVALID);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_SNAPSHOT_CHANGED);
    CHECK(memory.mutation_count == 1u);
}

static void mutate_identity_after_first_read(SyntheticMemory *memory,
                                            uint32_t address) {
    (void)address;
    if (memory->reads == 5u) {
        memory->nodes[0].identity = UINT32_C(0x12345679);
        ++memory->mutation_count;
    }
}

static void test_persistent_change_between_field_reads_is_invalid(void) {
    SyntheticMemory memory = make_list(1u);
    memory.before_read = mutate_identity_after_first_read;
    const FlySimViewResult result = classify(&memory);
    CHECK(result.classification == FLY_SIM_CLASS_INVALID);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_SNAPSHOT_CHANGED);
    CHECK(memory.mutation_count == 1u);
}

static void mutate_opaque_flag_between_captures(SyntheticMemory *memory,
                                              uint32_t address) {
    (void)address;
    if (memory->reads == 7u) {
        memory->nodes[0].flags = UINT32_C(0x80000000);
        ++memory->mutation_count;
    }
}

static void test_opaque_flag_changes_invalidate_snapshot(void) {
    SyntheticMemory memory = make_list(1u);
    memory.before_read = mutate_opaque_flag_between_captures;
    const FlySimViewResult result = classify(&memory);
    CHECK(result.classification == FLY_SIM_CLASS_INVALID);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_SNAPSHOT_CHANGED);
    CHECK(memory.mutation_count == 1u);
}

static void mutate_hidden_tail_identity(SyntheticMemory *memory,
                                       uint32_t address) {
    (void)address;
    if (memory->reads == 11u) {
        memory->nodes[1].identity = UINT32_C(0x12345679);
        ++memory->mutation_count;
    }
}

static void test_complete_captures_include_hidden_tail(void) {
    SyntheticMemory memory = make_list(2u);
    memory.nodes[1].flags = FLY_SIM_VIEW_HIDDEN_BIT;
    memory.before_read = mutate_hidden_tail_identity;
    const FlySimViewResult result = classify(&memory);
    CHECK(result.classification == FLY_SIM_CLASS_INVALID);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_SNAPSHOT_CHANGED);
    CHECK(memory.mutation_count == 1u);
}

static void remove_tail_between_captures(SyntheticMemory *memory,
                                        uint32_t address) {
    (void)address;
    if (memory->reads == 11u) {
        memory->nodes[0].next = 0u;
        ++memory->mutation_count;
    }
}

static void test_list_length_change_is_invalid(void) {
    SyntheticMemory memory = make_list(2u);
    memory.before_read = remove_tail_between_captures;
    const FlySimViewResult result = classify(&memory);
    CHECK(result.classification == FLY_SIM_CLASS_INVALID);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_SNAPSHOT_CHANGED);
    CHECK(memory.mutation_count == 1u);
}

static void replace_tail_between_captures(SyntheticMemory *memory,
                                         uint32_t address) {
    (void)address;
    if (memory->reads == 11u) {
        memory->nodes[1].address += FIXTURE_STRIDE;
        memory->nodes[0].next = memory->nodes[1].address;
        ++memory->mutation_count;
    }
}

static void test_equivalent_values_at_different_nodes_are_not_same_snapshot(void) {
    SyntheticMemory memory = make_list(2u);
    memory.before_read = replace_tail_between_captures;
    const FlySimViewResult result = classify(&memory);
    CHECK(result.classification == FLY_SIM_CLASS_INVALID);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_SNAPSHOT_CHANGED);
    CHECK(memory.mutation_count == 1u);
}

static void complete_aba_between_reads(SyntheticMemory *memory,
                                      uint32_t address) {
    (void)address;
    if (memory->reads == 5u) {
        /* No callback samples these intervening values: a complete ABA. */
        memory->nodes[0].identity = UINT32_C(0x12345679);
        memory->root = 0u;
        ++memory->mutation_count;
        memory->nodes[0].identity = FLY_SIM_VIEW_HOME_IDENTITY;
        memory->root = FIXTURE_BASE;
        ++memory->mutation_count;
    }
}

static void test_complete_aba_is_explicitly_unobservable(void) {
    SyntheticMemory memory = make_list(1u);
    memory.before_read = complete_aba_between_reads;
    const FlySimViewResult result = classify(&memory);
    CHECK(memory.mutation_count == 2u);
    /* This passing HOME result demonstrates a limitation, not ABA safety. */
    CHECK(result.classification == FLY_SIM_CLASS_HOME);
    CHECK(result.reason == FLY_SIM_VIEW_REASON_STABLE);
    CHECK(result.read_count == 12u);
}

static void test_diagnostic_names(void) {
    static const char *const reasons[] = {
        "stable", "no-reader", "unreadable", "node-alignment", "node-range",
        "cycle", "node-limit", "reverse-link", "root-changed",
        "snapshot-changed", "no-visible-identity"
    };
    for (unsigned i = 0u; i < sizeof(reasons) / sizeof(reasons[0]); ++i) {
        CHECK(strcmp(fly_sim_view_reason_name((FlySimViewReason)i),
                     reasons[i]) == 0);
    }
    CHECK(strcmp(fly_sim_view_reason_name((FlySimViewReason)-1), "unknown") == 0);
    CHECK(strcmp(fly_sim_view_reason_name((FlySimViewReason)99), "unknown") == 0);
    CHECK(strcmp(fly_sim_view_class_name(FLY_SIM_CLASS_INVALID), "INVALID") == 0);
    CHECK(strcmp(fly_sim_view_class_name(FLY_SIM_CLASS_HOME), "HOME") == 0);
    CHECK(strcmp(fly_sim_view_class_name(FLY_SIM_CLASS_NON_HOME), "NON_HOME") == 0);
    CHECK(strcmp(fly_sim_view_class_name((FlySimViewClass)-1), "unknown") == 0);
    CHECK(strcmp(fly_sim_view_class_name((FlySimViewClass)99), "unknown") == 0);
}

typedef struct {
    const char *name;
    void (*run)(void);
} TestCase;

int main(int argc, char **argv) {
    static const TestCase tests[] = {
        {"home", test_home_requires_two_complete_captures},
        {"synthetic-update", test_synthetic_update_identity_is_non_home},
        {"hidden-first", test_hidden_first_node_does_not_mask_first_visible},
        {"zero-identity", test_zero_identity_is_non_home_not_unknown_home},
        {"no-visible", test_empty_and_all_hidden_fail_safe},
        {"opaque-flags", test_flags_use_only_documented_hidden_bit},
        {"no-reader", test_missing_reader_fails_without_reads},
        {"null-context", test_null_context_is_reader_defined},
        {"reader-failure", test_reader_failure_at_every_read_fails_closed},
        {"unmapped-node", test_unmapped_node_is_unreadable},
        {"boundaries", test_boundary_addresses_and_alignment},
        {"bad-successor", test_bad_successors_are_never_read},
        {"reverse-link", test_reverse_links_must_match_forward_traversal},
        {"cycles", test_all_cycles_fail_before_any_node_is_reread},
        {"node-bound", test_eight_nodes_are_read_fully_and_ninth_is_not},
        {"root-within", test_root_changes_within_either_capture_are_invalid},
        {"root-between", test_root_change_between_captures_is_invalid},
        {"field-mutation", test_persistent_change_between_field_reads_is_invalid},
        {"flag-mutation", test_opaque_flag_changes_invalidate_snapshot},
        {"hidden-tail-mutation", test_complete_captures_include_hidden_tail},
        {"length-mutation", test_list_length_change_is_invalid},
        {"address-mutation",
         test_equivalent_values_at_different_nodes_are_not_same_snapshot},
        {"complete-aba", test_complete_aba_is_explicitly_unobservable},
        {"diagnostics", test_diagnostic_names}
    };
    unsigned run_count = 0u;
    CHECK(argc <= 2);
    for (unsigned i = 0u; i < sizeof(tests) / sizeof(tests[0]); ++i) {
        if (argc == 1 || strcmp(argv[1], tests[i].name) == 0) {
            tests[i].run();
            ++run_count;
        }
    }
    CHECK(run_count != 0u);
    puts("view classifier tests passed");
    return EXIT_SUCCESS;
}
