"""Closed-loop streaming benchmark; stdlib only; never stores request/response text."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import statistics
import time
import urllib.request

def percentile(values, q):
    if not values:
        return None
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)

def request_one(base, token, prompt, max_tokens):
    payload = {'model': 'local-instruct', 'prompt': prompt, 'stream': True,
               'stream_options': {'include_usage': True}, 'max_tokens': max_tokens,
               'temperature': 0, 'ignore_eos': True}
    req = urllib.request.Request(base + '/v1/completions', json.dumps(payload).encode(),
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    start, first, usage = time.perf_counter(), None, None
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            for raw in response:
                line = raw.decode().strip()
                if not line.startswith('data: '):
                    continue
                if line == 'data: [DONE]':
                    break
                chunk = json.loads(line[6:])
                if chunk.get('error'):
                    raise ValueError('stream error')
                choices = chunk.get('choices', [])
                if choices and choices[0].get('text') and first is None:
                    first = time.perf_counter()
                if chunk.get('usage'):
                    usage = chunk['usage']
        if first is None or usage is None:
            raise ValueError('missing content or usage')
        return {'ok': True, 'ttft_s': first-start, 'latency_s': time.perf_counter()-start,
                'input_tokens': usage['prompt_tokens'], 'output_tokens': usage['completion_tokens']}
    except Exception:
        return {'ok': False}  # Never save the exception text or response body.

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base-url', default='http://127.0.0.1:8000')
    p.add_argument('--kind', choices=['short', 'long'], required=True)
    p.add_argument('--concurrency', type=int, default=1)
    p.add_argument('--requests', type=int, default=20)
    p.add_argument('--max-tokens', type=int, default=32)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    token = Path('.local/api-token').read_text().strip()
    prompt = 'This is a test sentence. ' * (5 if a.kind == 'short' else 180)
    warm = request_one(a.base_url, token, prompt, a.max_tokens)
    if not warm['ok']:
        raise SystemExit('Warmup failed; check authentication, context limit and readiness.')
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        jobs = [pool.submit(request_one, a.base_url, token, f'{i}: {prompt}', a.max_tokens)
                for i in range(a.requests)]
        rows = [job.result() for job in jobs]
    wall = time.perf_counter() - start
    ok = [r for r in rows if r['ok']]
    result = {'kind': a.kind, 'concurrency': a.concurrency, 'requests': a.requests,
              'successes': len(ok), 'failures': a.requests-len(ok), 'wall_s': wall,
              'mean_input_tokens': statistics.mean(r['input_tokens'] for r in ok) if ok else None,
              'mean_output_tokens': statistics.mean(r['output_tokens'] for r in ok) if ok else None,
              'ttft_p50_s': percentile([r['ttft_s'] for r in ok], .5),
              'ttft_p95_s': percentile([r['ttft_s'] for r in ok], .95),
              'latency_p50_s': percentile([r['latency_s'] for r in ok], .5),
              'latency_p95_s': percentile([r['latency_s'] for r in ok], .95),
              'throughput_req_s': len(ok)/wall,
              'throughput_output_tok_s': sum(r['output_tokens'] for r in ok)/wall,
              'rows': rows}
    target = Path(a.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2))
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}, indent=2))

if __name__ == '__main__':
    main()
