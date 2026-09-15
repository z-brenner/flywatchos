#include "fly/persistence.h"

#include <stddef.h>
#include <stdio.h>
#include <string.h>

#define FLY_PERSIST_MAGIC 0x464c5931u
#define FLY_PERSIST_VERSION 1u

typedef struct {
    uint32_t magic;
    uint16_t version;
    uint16_t payload_size;
    FlyPersistentState payload;
    uint32_t crc32;
    uint32_t commit_marker;
} PersistenceRecord;

static uint32_t crc32_bytes(const unsigned char *data, size_t size) {
    uint32_t crc = 0xffffffffu;
    for (size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; ++bit) {
            uint32_t mask = 0u - (crc & 1u);
            crc = (crc >> 1) ^ (0xedb88320u & mask);
        }
    }
    return ~crc;
}

static void slot_path(char *out, size_t out_size, const char *base, char slot) {
    snprintf(out, out_size, "%s.%c", base, slot);
}

static int read_record(const char *path, PersistenceRecord *record) {
    FILE *file = fopen(path, "rb");
    if (!file) return FLY_PERSIST_NOT_FOUND;
    size_t count = fread(record, 1, sizeof(*record), file);
    int trailing = fgetc(file);
    fclose(file);
    if (count != sizeof(*record) || trailing != EOF) return FLY_PERSIST_INVALID;
    if (record->magic != FLY_PERSIST_MAGIC || record->version != FLY_PERSIST_VERSION ||
        record->payload_size != sizeof(record->payload) ||
        record->commit_marker != ~FLY_PERSIST_MAGIC) return FLY_PERSIST_INVALID;
    uint32_t expected = crc32_bytes((const unsigned char *)record,
                                    offsetof(PersistenceRecord, crc32));
    return expected == record->crc32 ? FLY_PERSIST_OK : FLY_PERSIST_INVALID;
}

void fly_persistent_state_init(FlyPersistentState *state, uint32_t identity_seed) {
    memset(state, 0, sizeof(*state));
    state->identity_seed = identity_seed;
    state->lifecycle_policy = FLY_LIFECYCLE_CONTINUE;
    fly_network_init(&state->network, identity_seed);
}

int fly_persistence_save(const char *base_path, FlyPersistentState *state) {
    char path_a[512], path_b[512], destination[512], temporary[520];
    slot_path(path_a, sizeof(path_a), base_path, 'a');
    slot_path(path_b, sizeof(path_b), base_path, 'b');
    PersistenceRecord a, b;
    int valid_a = read_record(path_a, &a) == FLY_PERSIST_OK;
    int valid_b = read_record(path_b, &b) == FLY_PERSIST_OK;
    char target = (!valid_a || (valid_b && a.payload.sequence <= b.payload.sequence)) ? 'a' : 'b';
    slot_path(destination, sizeof(destination), base_path, target);
    snprintf(temporary, sizeof(temporary), "%s.tmp", destination);

    uint32_t newest = 0;
    if (valid_a && a.payload.sequence > newest) newest = a.payload.sequence;
    if (valid_b && b.payload.sequence > newest) newest = b.payload.sequence;
    state->sequence = newest + 1u;

    PersistenceRecord record;
    memset(&record, 0, sizeof(record));
    record.magic = FLY_PERSIST_MAGIC;
    record.version = FLY_PERSIST_VERSION;
    record.payload_size = (uint16_t)sizeof(record.payload);
    record.payload = *state;
    record.crc32 = crc32_bytes((const unsigned char *)&record,
                               offsetof(PersistenceRecord, crc32));
    record.commit_marker = ~FLY_PERSIST_MAGIC;

    FILE *file = fopen(temporary, "wb");
    if (!file) return FLY_PERSIST_IO_ERROR;
    size_t count = fwrite(&record, 1, sizeof(record), file);
    int close_result = fclose(file);
    if (count != sizeof(record) || close_result != 0) {
        remove(temporary);
        return FLY_PERSIST_IO_ERROR;
    }
    remove(destination);
    if (rename(temporary, destination) != 0) {
        remove(temporary);
        return FLY_PERSIST_IO_ERROR;
    }
    return FLY_PERSIST_OK;
}

int fly_persistence_load(const char *base_path, FlyPersistentState *state) {
    char path_a[512], path_b[512];
    slot_path(path_a, sizeof(path_a), base_path, 'a');
    slot_path(path_b, sizeof(path_b), base_path, 'b');
    PersistenceRecord a, b;
    int valid_a = read_record(path_a, &a) == FLY_PERSIST_OK;
    int valid_b = read_record(path_b, &b) == FLY_PERSIST_OK;
    if (!valid_a && !valid_b) return FLY_PERSIST_NOT_FOUND;
    *state = (valid_a && (!valid_b || a.payload.sequence >= b.payload.sequence))
                 ? a.payload
                 : b.payload;
    return FLY_PERSIST_OK;
}

void fly_persistence_remove(const char *base_path) {
    char path[520];
    for (char slot = 'a'; slot <= 'b'; ++slot) {
        slot_path(path, sizeof(path), base_path, slot);
        remove(path);
        size_t length = strlen(path);
        if (length + 4u < sizeof(path)) {
            memcpy(path + length, ".tmp", 5u);
            remove(path);
        }
    }
}

int fly_persistence_corrupt_newest_for_test(const char *base_path) {
    char path_a[512], path_b[512];
    slot_path(path_a, sizeof(path_a), base_path, 'a');
    slot_path(path_b, sizeof(path_b), base_path, 'b');
    PersistenceRecord a, b;
    int valid_a = read_record(path_a, &a) == FLY_PERSIST_OK;
    int valid_b = read_record(path_b, &b) == FLY_PERSIST_OK;
    if (!valid_a && !valid_b) return FLY_PERSIST_NOT_FOUND;
    const char *path = (valid_a && (!valid_b || a.payload.sequence >= b.payload.sequence))
                           ? path_a
                           : path_b;
    FILE *file = fopen(path, "r+b");
    if (!file) return FLY_PERSIST_IO_ERROR;
    int value = fgetc(file);
    if (value == EOF || fseek(file, 0, SEEK_SET) != 0 || fputc(value ^ 0xff, file) == EOF) {
        fclose(file);
        return FLY_PERSIST_IO_ERROR;
    }
    return fclose(file) == 0 ? FLY_PERSIST_OK : FLY_PERSIST_IO_ERROR;
}
