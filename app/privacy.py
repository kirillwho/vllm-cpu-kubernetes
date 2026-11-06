import json
import logging
import re
import time
import uuid

EVENTS = {'request_started', 'request_finished', 'runtime_log'}
ENDPOINTS = {'chat', 'completion', 'other'}

def sanitize(data):
    event = data.get('event')
    if event == 'runtime_log':
        level = data.get('level')
        return {'event': event, 'level': level if level in {'DEBUG','INFO','WARNING','ERROR','CRITICAL'} else 'INFO'}
    if event not in {'request_started', 'request_finished'}:
        return None
    rid = data.get('request_id', '')
    if not isinstance(rid, str) or not re.fullmatch(r'[a-f0-9]{32}', rid):
        return None
    endpoint = data.get('endpoint')
    if endpoint not in ENDPOINTS:
        return None
    out = {'event': event, 'request_id': rid, 'endpoint': endpoint}
    if event == 'request_finished':
        status = data.get('status')
        duration = data.get('duration_ms')
        if type(status) is not int or not 0 <= status <= 599:
            return None
        if type(duration) is not int or not 0 <= duration <= 604800000:
            return None
        out.update(status=status, duration_ms=duration)
    return out

class SafeFormatter(logging.Formatter):
    def format(self, record):
        # record.msg, args, exc_info and stack_info are never interpolated.
        if record.name == 'safe.audit':
            clean = sanitize(getattr(record, 'safe_data', {}))
            if clean:
                return json.dumps(clean)
        return json.dumps({'event': 'runtime_log', 'level': record.levelname})

class AuditMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') in {'/health', '/metrics', '/ping'}:
            return await self.app(scope, receive, send)
        endpoint = {'/v1/chat/completions': 'chat', '/v1/completions': 'completion'}.get(scope.get('path'), 'other')
        rid, start, status = uuid.uuid4().hex, time.perf_counter(), 0
        logger = logging.getLogger('safe.audit')
        base = {'request_id': rid, 'endpoint': endpoint}
        logger.info('', extra={'safe_data': dict(base, event='request_started')})
        async def wrapped_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
            await send(message)
        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            logger.info('', extra={'safe_data': dict(base, event='request_finished', status=status,
                        duration_ms=int((time.perf_counter() - start) * 1000))})
