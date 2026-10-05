/* Receipt-probe response accumulator. Caller serializes access across tasks. */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

struct muse_chat_probe_rx {
    uintptr_t generation = 0;
    int status = 0;
    bool done = false, overflow = false;
    size_t len = 0;
    char body[16384] = {};

    uintptr_t reset() {
        if (!++generation) ++generation;
        status = 0;
        done = overflow = false;
        len = 0;
        return generation;
    }
    void feed(uintptr_t gen, int code, const uint8_t *data, size_t size, bool end) {
        if (gen != generation || done) return;
        if (code) status = code;
        if (size > sizeof(body) - 1 - len) overflow = true;
        if (!overflow && size) {
            memcpy(body + len, data, size);
            len += size;
        }
        body[len] = 0;
        done = end || code < 0;
    }
    bool ok() const { return done && !overflow && status >= 200 && status < 300; }
};
