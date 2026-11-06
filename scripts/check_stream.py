import json
from pathlib import Path
import urllib.request

token = Path('.local/api-token').read_text().strip()
marker = Path('.local/privacy-marker').read_text()
payload = {'model':'local-instruct', 'stream':True,
           'messages':[{'role':'user','content':'Repeat exactly: '+marker}],
           'max_tokens':64, 'temperature':0}

def run(cancel):
    req=urllib.request.Request('http://127.0.0.1:8000/v1/chat/completions',
        json.dumps(payload).encode(), headers={
            'Content-Type':'application/json', 'Authorization':'Bearer '+token})
    parts=[]
    with urllib.request.urlopen(req, timeout=600) as response:
        for raw in response:
            line=raw.decode().strip()
            if not line.startswith('data: ') or line == 'data: [DONE]':
                continue
            data=json.loads(line[6:])
            for choice in data.get('choices',[]):
                text=choice.get('delta',{}).get('content')
                if text:
                    parts.append(text)
            if cancel and parts:
                break
    if not parts:
        raise AssertionError('No content received')
    return ''.join(parts)

Path('.local/stream-answer').write_text(run(False))
Path('.local/cancel-answer').write_text(run(True))
print('Streaming and client cancellation checks completed')
