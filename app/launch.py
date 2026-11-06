import json
import re
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
from privacy import sanitize

def relay(stream):
    for line in stream:
        try:
            line = re.sub(
                r"^\(APIServer pid=[0-9]+\)\s*",
                "",
                line,
                count=1,
            )
            data = json.loads(line)
            clean = sanitize(data) if isinstance(data, dict) else None
        except (ValueError, TypeError):
            clean = None

        if clean is not None:
            print(json.dumps(clean), flush=True)

def main():
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    key = Path('/run/secrets/api-token').read_text().strip()
    if not key:
        raise ValueError('empty API token')
    # vLLM reads this environment variable; never put the token in CLI args.
    env['VLLM_API_KEY'] = key
    omp = list(Path('/opt/venv').rglob('libiomp5.so'))
    preload = ['/usr/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4']
    if omp:
        preload.append(str(omp[0]))
    env['LD_PRELOAD'] = ':'.join(p for p in preload if Path(p).exists())
    command = ['/opt/venv/bin/vllm', 'serve',
               '--config', '/config/serve.yaml', '--middleware', 'privacy.AuditMiddleware',
               '--no-enable-log-requests', '--no-enable-log-outputs',
               '--disable-uvicorn-access-log', '--log-config-file', '/app/logging.json']
    child = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding='utf-8', errors='replace', start_new_session=True)
    def stop(signum, frame):
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    workers = [threading.Thread(target=relay, args=(s,), daemon=True) for s in (child.stdout, child.stderr)]
    for worker in workers:
        worker.start()
    code = child.wait()
    for worker in workers:
        worker.join()
    print(json.dumps({'event':'engine_stopped', 'exit_code':code}), flush=True)
    return code

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('{"event":"launcher_failed"}', file=sys.stderr, flush=True)
        sys.exit(1)
