"""Run the production probe bridge with a fake asynchronous control transport."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProbeBridgeTest(unittest.TestCase):
    def test_response_lifetime_and_send_failures(self):
        source = (ROOT / 'components/muse/muse_chat_session.cpp').read_text()
        bridge = source.split('static void probe_response(', 1)[1].split('#endif', 1)[0]
        poll = source.split('static void poll_probe(', 1)[1].split('#endif', 1)[0]
        harness = r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include "muse_chat_probe_rx.h"
#define CHAT_PART 16384
#define portMAX_DELAY 0
using SemaphoreHandle_t = int;
static SemaphoreHandle_t s_probe_lock = 1;
static muse_chat_probe_rx s_probe_rx;
static int64_t s_probe_id;
static void xSemaphoreTake(int, int) {}
static void xSemaphoreGive(int) {}
static unsigned esp_random() { return 1; }
static bool registered = true, open_ok = true, send_ok = true;
static bool inline_failure = false;
static int ack_count, errors, cancels;
using callback = void (*)(void *, int, const uint8_t *, size_t, bool);
static callback cb;
static void *context;
static const char *noise_ctrl_registered_device_id() { return registered ? "board-1" : nullptr; }
static void noise_ctrl_req_cancel(int64_t) { ++cancels; }
static int64_t noise_ctrl_req_open(const char *verb, const char *path, const char *const *headers,
                                   bool end, callback fn, void *ctx) {
    assert(!strcmp(verb,"POST") && !strcmp(path,"/chat/stream") && !end);
    assert(!strcmp(headers[2],"x-app-id") && !strcmp(headers[3],"musegadget"));
    if (!open_ok) return 0;
    cb = fn; context = ctx;
    if (inline_failure) cb(ctx, -1, nullptr, 0, true);
    return 17;
}
static bool noise_ctrl_req_send(int64_t id, const void *data, size_t len, bool end, int) {
    assert(id == 17 && len == 2 && !memcmp(data,"{}",2) && end);
    return send_ok;
}
struct stream_t { char *line; size_t len; };
static void on_chat_ack(stream_t *s) { assert(std::string(s->line,s->len)=="{}" ); ++ack_count; }
static void turn_fail(const char *) { ++errors; }
'''
        harness += 'static void probe_response(' + bridge + '\nstatic void poll_probe(' + poll
        harness += r'''
int main() {
    registered = false;
    assert(!send_probe("{}"));
    registered = true; open_ok = false;
    assert(!send_probe("{}"));
    open_ok = true;
    assert(send_probe("{}"));
    void *old_context = context;
    cb(context,200,(const uint8_t *)"{",1,false);
    poll_probe(); assert(ack_count==0);
    cb(context,0,(const uint8_t *)"}",1,true);
    poll_probe(); assert(ack_count==1 && !s_probe_id);
    poll_probe(); assert(ack_count==1);
    assert(send_probe("{}"));
    cb(old_context,200,(const uint8_t *)"{}",2,true);
    poll_probe(); assert(ack_count==1 && s_probe_id);
    cancel_probe(); assert(!s_probe_id && cancels==1);
    cb(context,200,(const uint8_t *)"{}",2,true);
    poll_probe(); assert(ack_count==1);
    assert(send_probe("{}"));
    cb(context,403,(const uint8_t *)"{}",2,true);
    poll_probe(); assert(errors==1 && ack_count==1);
    assert(send_probe("{}"));
    cb(context,-1,nullptr,0,true);
    poll_probe(); assert(errors==2);
    assert(send_probe("{}"));
    std::string large(16384,'x');
    cb(context,200,(const uint8_t *)large.data(),large.size(),true);
    poll_probe(); assert(errors==3);
    send_ok=false;
    assert(!send_probe("{}") && !s_probe_id && cancels==2);
    send_ok=true; inline_failure=true;
    assert(send_probe("{}"));
    poll_probe(); assert(errors==4); // callback may arrive before open returns
    assert(ack_count==1);
}
'''
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p / 'test.cpp').write_text(harness)
            subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I'+str(ROOT / 'components/muse'), str(p / 'test.cpp'),
                            '-o', str(p / 'test')], check=True)
            subprocess.run([str(p / 'test')], check=True)
