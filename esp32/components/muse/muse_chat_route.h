/* Triggr opt-in chat-routing probe. No subscription scope is assumed. */
#pragma once
#include <string.h>
#include <stdio.h>
#include "cJSON.h"

static inline bool muse_chat_session_valid(const char *id)
{
    if (!id || !id[0] || strlen(id) > 64) return false;
    for (const char *p = id; *p; ++p) {
        if (!((*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') ||
              (*p >= '0' && *p <= '9') || *p == '-')) return false;
    }
    return true;
}

/* Missing or unfamiliar metadata is not evidence of chat membership. If either
 * envelope explicitly names a different/malformed session, reject it. */
static inline bool muse_chat_route_accept(cJSON *line, cJSON *payload,
                                         const char *wanted, bool known_parent)
{
    bool matched = false;
    cJSON *objects[] = {line, payload};
    for (auto *object : objects) {
        cJSON *field = cJSON_GetObjectItemCaseSensitive(object, "session_id");
        if (!field) continue;
        const char *id = cJSON_GetStringValue(field);
        if (!id || strcmp(id, wanted)) return false;
        matched = true;
    }
    return matched || known_parent;
}

static inline bool muse_chat_add_session(cJSON *body, const char *id)
{
    return muse_chat_session_valid(id) && cJSON_AddStringToObject(body, "session_id", id);
}

/* Diagnostic labels are fixed strings: never log arbitrary payload values. */
static inline const char *muse_chat_session_state(cJSON *object, const char *wanted)
{
    cJSON *field = cJSON_GetObjectItemCaseSensitive(object, "session_id");
    if (!field) return "missing";
    if (cJSON_IsNull(field)) return "null";
    const char *id = cJSON_GetStringValue(field);
    if (!id) return "invalid";
    if (!id[0]) return "empty";
    return !strcmp(id, wanted) ? "match" : "other";
}

/* Bounded protocol identifiers only; reject control characters and free text. */
static inline bool muse_chat_metadata_name(const char *name)
{
    if (!name || !name[0] || strlen(name) > 64) return false;
    for (const char *p = name; *p; ++p) {
        if (!((*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') ||
              (*p >= '0' && *p <= '9') || *p == '.' || *p == '_' || *p == '-')) return false;
    }
    return true;
}

static inline const char *muse_chat_event_kind(cJSON *line)
{
    const char *event = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(line, "event"));
    if (!event) return "missing";
    return muse_chat_metadata_name(event) ? event : "invalid-name";
}

/* Keys and JSON types only, including one nested object level. Never values or
 * array contents. Both iteration and output are bounded even on huge events. */
static inline void muse_chat_schema(cJSON *object, char *out, size_t cap, unsigned depth = 1)
{
    if (!cap) return;
    out[0] = 0;
    if (!cJSON_IsObject(object)) {
        snprintf(out, cap, "non-object");
        return;
    }
    unsigned count = 0;
    for (cJSON *field = object->child; field && count < 12; field = field->next, ++count) {
        size_t used = strlen(out);
        if (used + 1 >= cap) break;
        const char *kind = cJSON_IsString(field) ? "string" : cJSON_IsObject(field) ? "object" :
            cJSON_IsArray(field) ? "array" : cJSON_IsNumber(field) ? "number" :
            cJSON_IsNull(field) ? "null" : cJSON_IsBool(field) ? "bool" : "unknown";
        const char *name = muse_chat_metadata_name(field->string) ? field->string : "invalid-key";
        char nested[256] = {};
        if (depth && cJSON_IsObject(field)) muse_chat_schema(field, nested, sizeof(nested), depth - 1);
        snprintf(out + used, cap - used, "%s%s:%s%s%s%s", count ? "," : "", name, kind,
                 nested[0] ? "(" : "", nested, nested[0] ? ")" : "");
    }
}
