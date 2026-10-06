"""Exercise the actual subscription request in normal and experimental builds."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SubscriptionTest(unittest.TestCase):
    def test_normal_probe_invalid_and_failed_open(self):
        source = (ROOT / 'components/muse/muse_chat_session.cpp').read_text()
        function = source.split('static bool open_subscription(void)', 1)[1].split('static bool connect_once', 1)[0]
        harness = r'''
#include <cassert>
#include <string>
#include "muse_chat_route.h"
#define ESP_LOGI(...) ((void)0)
static long s_last_seq;
struct { long sub_id; } s_conn;
static const char *session_id;
#define CONFIG_TRIGGR_SIDE_CHAT_SESSION_ID session_id
static int calls;
static bool fail_open;
static std::string sent;
enum {K_SUB};
static long open_stream(int kind, const char *verb, const char *path, const char *content,
                        const char *accept, const char *body, bool end) {
    ++calls;
    assert(kind==K_SUB && !strcmp(verb,"POST") && !strcmp(path,"/chat/subscribe"));
    assert(!strcmp(content,"application/json") && !strcmp(accept,"application/x-ndjson") && end);
    sent=body;
    return fail_open ? 0 : 7;
}
'''
        harness += 'static bool open_subscription(void)' + function
        harness += r'''
int main() {
    session_id="stable-side-1";
    s_last_seq=42;
    assert(open_subscription() && s_conn.sub_id==7 && s_last_seq==0 && calls==1);
#if CONFIG_TRIGGR_SIDE_CHAT_PROBE
    cJSON *body=cJSON_Parse(sent.c_str());
    assert(cJSON_GetArraySize(body)==1);
    assert(!strcmp(cJSON_GetStringValue(cJSON_GetObjectItem(body,"session_id")),session_id));
    cJSON_Delete(body);
    session_id="";
    assert(!open_subscription() && calls==1); // no main-chat fallback
    session_id="../invalid";
    assert(!open_subscription() && calls==1);
    session_id="stable-side-1";
#else
    assert(sent=="{}");
#endif
    fail_open=true;
    assert(!open_subscription() && s_conn.sub_id==0 && calls==2);
}
'''
        cjson = ROOT / 'managed_components/espressif__cjson/cJSON'
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p / 'test.cpp').write_text(harness)
            subprocess.run([os.environ.get('CC', 'cc'), '-I'+str(cjson), '-c',
                            str(cjson / 'cJSON.c'), '-o', str(p / 'cjson.o')], check=True)
            for enabled in (0, 1):
                subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                '-DCONFIG_TRIGGR_SIDE_CHAT_PROBE='+str(enabled), '-I'+str(cjson),
                                '-I'+str(ROOT / 'components/muse'), str(p / 'test.cpp'),
                                str(p / 'cjson.o'), '-o', str(p / 'test')], check=True)
                subprocess.run([str(p / 'test')], check=True)
