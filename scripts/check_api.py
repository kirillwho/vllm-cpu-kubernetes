import json
from pathlib import Path
import urllib.request
import urllib.error
import uuid

base = 'http://127.0.0.1:8000/v1/chat/completions'
token = Path('.local/api-token').read_text().strip()
marker = 'PRIVATE_' + uuid.uuid4().hex
Path('.local/privacy-marker').write_text(marker)
payload = {'model': 'local-instruct', 'messages': [{'role': 'user', 'content': 'Repeat exactly: '+marker}],
           'max_tokens': 64, 'temperature': 0}
for key, expected in [(None, 401), ('invalid-key', 401), (token, 200)]:
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer '+key
    req = urllib.request.Request(base, json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            status = response.status
            if status == 200:
                answer = json.load(response)['choices'][0]['message']['content']
                Path('.local/privacy-answer').write_text(answer)
    except urllib.error.HTTPError as exc:
        status = exc.code
    assert status == expected, (status, expected)
    print('HTTP', status, 'OK')
# Deliberately malformed JSON may expose a body in ordinary validation logs.
req = urllib.request.Request(base, ('{"messages": ["'+marker+'"], BROKEN').encode(),
        headers={'Authorization':'Bearer '+token, 'Content-Type':'application/json'})
try:
    urllib.request.urlopen(req, timeout=60)
    raise AssertionError('Expected 4xx')
except urllib.error.HTTPError as exc:
    assert 400 <= exc.code < 500
    print('Malformed request rejected OK')

oversized = dict(payload)
oversized['messages'] = [{'role':'user', 'content': marker + (' hello' * 10000)}]
req = urllib.request.Request(base, json.dumps(oversized).encode(),
    headers={'Authorization':'Bearer '+token, 'Content-Type':'application/json'})
try:
    urllib.request.urlopen(req, timeout=120)
    raise AssertionError('Expected a context limit error')
except urllib.error.HTTPError as exc:
    assert 400 <= exc.code < 500
    print('Context overflow rejected OK')
