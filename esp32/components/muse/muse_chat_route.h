/* Triggr opt-in chat-routing probe. No subscription scope is assumed. */
#pragma once
#include <string.h>
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

static inline const char *muse_chat_event_kind(cJSON *line)
{
    const char *event = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(line, "event"));
    if (!event) return "missing";
    const char *known[] = {"agent.status", "task.status", "delta.message_start",
        "delta.text_append", "delta.message_done", "message.assistant", "message.user"};
    for (const char *name : known) if (!strcmp(name, event)) return name;
    return "other";
}
