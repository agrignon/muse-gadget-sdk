"""Exercise production side-chat routing helpers with actual cJSON."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SideChatTest(unittest.TestCase):
    def test_request_validation_and_reply_isolation(self):
        cjson = ROOT / 'managed_components/espressif__cjson/cJSON'
        harness = r'''
#include <cassert>
#include "muse_chat_route.h"
static void check(const char *json, bool known, bool expected) {
    cJSON *line=cJSON_Parse(json);
    assert(muse_chat_route_accept(line,cJSON_GetObjectItem(line,"payload"),"side-1",known)==expected);
    cJSON_Delete(line);
}
int main() {
    cJSON *body=cJSON_CreateObject();
    assert(!muse_chat_add_session(body,""));
    assert(!muse_chat_add_session(body,"../other"));
    assert(!muse_chat_add_session(body,"side_1"));
    char long_id[66];memset(long_id,'a',65);long_id[65]=0;
    assert(!muse_chat_add_session(body,long_id));
    assert(muse_chat_add_session(body,"side-1"));
    assert(!strcmp(cJSON_GetStringValue(cJSON_GetObjectItem(body,"session_id")),"side-1"));
    cJSON_Delete(body);
    check("{}",false,false);             // no guessed subscription scope
    check("{}",true,true);               // known message/parent can correlate
    check("{\"session_id\":\"side-1\"}",false,true); // before ACK with session
    check("{\"payload\":{\"session_id\":\"side-1\"}}",false,true);
    check("{\"session_id\":\"main\"}",true,false);
    check("{\"session_id\":\"side-1\",\"payload\":{\"session_id\":\"main\"}}",true,false);
    check("{\"session_id\":null}",true,false);
    check("{\"payload\":{\"session_id\":42}}",true,false);
    check("{\"payload\":{\"session_id\":\"\"}}",true,false);
}
'''
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p / 'test.cpp').write_text(harness)
            subprocess.run([os.environ.get('CC', 'cc'), '-I'+str(cjson), '-c',
                            str(cjson / 'cJSON.c'), '-o', str(p / 'cjson.o')], check=True)
            subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I'+str(cjson), '-I'+str(ROOT / 'components/muse'),
                            str(p / 'test.cpp'), str(p / 'cjson.o'), '-o', str(p / 'test')], check=True)
            subprocess.run([str(p / 'test')], check=True)
