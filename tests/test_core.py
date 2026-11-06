import asyncio
import contextlib
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'app'))
from privacy import SafeFormatter, sanitize, AuditMiddleware
from launch import relay
spec = importlib.util.spec_from_file_location('download', ROOT/'scripts/download.py')
download = importlib.util.module_from_spec(spec)
spec.loader.exec_module(download)

class CoreTests(unittest.TestCase):
    def test_formatter_drops_messages_and_exceptions(self):
        record = logging.LogRecord('vllm', logging.ERROR, '', 0, 'PRIVATE_PROMPT %s', ('PRIVATE_RESPONSE',), None)
        try:
            raise ValueError('PRIVATE_EXCEPTION')
        except ValueError:
            record.exc_info = sys.exc_info()
        self.assertEqual(json.loads(SafeFormatter().format(record)), {'event':'runtime_log','level':'ERROR'})

    def test_relay_rejects_raw_output_and_extra_fields(self):
        source = io.StringIO('PRIVATE_TRACEBACK\n'+json.dumps({'event':'runtime_log','level':'INFO','body':'PRIVATE'})+'\n')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            relay(source)
        self.assertNotIn('PRIVATE', output.getvalue())
        self.assertIsNone(sanitize({'event':'request_started','request_id':'PRIVATE','endpoint':'chat'}))

    def test_audit_handles_stream_completion_without_reading_body(self):
        async def app(scope, receive, send):
            await send({'type':'http.response.start','status':200})
            await send({'type':'http.response.body','body':b'PRIVATE_RESPONSE', 'more_body':False})
        async def receive():
            raise AssertionError('Middleware must not read the request body')
        received=[]
        async def send(m):
            received.append(m)
        with self.assertLogs('safe.audit', level='INFO') as logs:
            asyncio.run(AuditMiddleware(app)({'type':'http','path':'/v1/chat/completions'}, receive, send))
        data=[r.safe_data for r in logs.records]
        self.assertEqual([r['event'] for r in data], ['request_started','request_finished'])
        self.assertEqual(data[-1]['status'], 200)
        self.assertNotIn('PRIVATE', json.dumps(data))
        self.assertEqual(received[-1]['body'], b'PRIVATE_RESPONSE')

    def test_complete_cache_uses_no_hub_import(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            (path/'config.json').write_text('{}')
            marker={'repo':'test/repo','revision':'a'*40,'files':{'config.json':download.digest(path/'config.json')}}
            (path/'.complete.json').write_text(json.dumps(marker))
            env={'MODEL_ID':'test/repo','MODEL_REVISION':'a'*40,'MODEL_DIR':d,'CACHE_ONLY':'1'}
            with patch.dict(os.environ,env), patch.dict(sys.modules,{'huggingface_hub':None}):
                with contextlib.redirect_stdout(io.StringIO()):
                    download.run()
                (path/'config.json').write_text('tampered')
                with self.assertRaises(ValueError):
                    download.run()

    def test_incomplete_cache_offline_fails_without_hub(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ,{'MODEL_ID':'test/repo','MODEL_REVISION':'a'*40,'MODEL_DIR':d,'CACHE_ONLY':'1'}):
                with self.assertRaises(ValueError):
                    download.run()

if __name__ == '__main__':
    unittest.main()
