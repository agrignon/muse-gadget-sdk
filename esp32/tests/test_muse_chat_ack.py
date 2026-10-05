"""Exercise the production session ACK handler with actual cJSON on the host."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TypedAckTest(unittest.TestCase):
    def test_only_identified_typed_receipts_reach_console(self):
        source = (ROOT / 'components/muse/muse_chat_session.cpp').read_text()
        start = source.index('static void on_chat_ack(stream_t *s)')
        end = source.index('/* ---- Turn: speech ---- */', start)
        handler = source[start:end]
        cjson = ROOT / 'managed_components/espressif__cjson/cJSON'
        self.assertTrue((cjson / 'cJSON.c').exists(), 'Run the firmware build first')
        harness = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include "cJSON.h"
struct stream_t {char line[512]; size_t len;};
static struct {char user_ids[2][96]; bool text, acked;} s_turn;
static int receipts, events, marks;
#define M_ACK 1
#define MUSE_HATCH_EV_SENT 1
#define ESP_LOGI(...) ((void)0)
static void mark(int) {marks++;}
static void emit(int, const char *) {events++;}
static void muse_hatch_console(const char *type, const char *text, const char *fields) {
    assert(!strcmp(type,"ack") && !text && !fields); receipts++;
}
static size_t copy_string(char *to, const char *from, size_t cap) {
    snprintf(to,cap,"%s",from); return strlen(from);
}
#define strlcpy copy_string
''' + handler + r'''
static void run(const char *json, bool typed, int expected) {
    memset(&s_turn,0,sizeof(s_turn)); s_turn.text=typed;
    receipts=events=marks=0;
    stream_t s={}; snprintf(s.line,sizeof(s.line),"%s",json); s.len=strlen(s.line);
    on_chat_ack(&s);
    assert(receipts==expected && events==1 && marks==1 && s_turn.acked);
}
int main() {
    run("{\"result\":{\"message_id\":\"user-1\"}}",true,1);
    run("{\"message_id\":\"user-2\"}",true,1);
    run("{\"result\":{\"message_id\":\"voice-1\"}}",false,0);
    run("{}",true,0);
    run("not json",true,0);
    run("{\"message_id\":\"\"}",true,0);
    run("{\"message_id\":42}",true,0);
    run("{\"reply_to_message_id\":\"parent-only\"}",true,0);
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / 'test.cpp').write_text(harness)
            subprocess.run([os.environ.get('CC', 'cc'), '-I'+str(cjson), '-c',
                            str(cjson / 'cJSON.c'), '-o', str(path / 'cjson.o')], check=True)
            subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall',
                            '-Wextra', '-Werror', '-I'+str(cjson), str(path / 'test.cpp'),
                            str(path / 'cjson.o'), '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True)
