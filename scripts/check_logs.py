import json
from pathlib import Path

text=Path('.local/pod.log').read_text()
for name in ['api-token', 'privacy-marker', 'privacy-answer',
             'stream-answer', 'cancel-answer']:
    value=Path('.local', name).read_text().strip()
    if value:
        assert value not in text, 'Private data leaked: '+name
rows=[json.loads(s) for s in text.splitlines() if s.strip()]
assert any(r.get('event') == 'request_started' for r in rows)
assert any(r.get('event') == 'request_finished' for r in rows)
allowed={'event','request_id','endpoint','status','duration_ms','level','exit_code'}
assert all(set(r) <= allowed for r in rows)
print('Log privacy checks passed')
