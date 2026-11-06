import json
from pathlib import Path

paths=sorted(Path('results').glob('*-c*-r*.json'))
if not paths:
    raise SystemExit('No benchmark results')
head=['Run','Input tokens','C','N','TTFT p50 s','TTFT p95 s',
      'Latency p50 s','Latency p95 s','req/s','output tok/s','Errors']
lines=['| '+' | '.join(head)+' |', '| '+' | '.join(['---']*len(head))+' |']
def fmt(value):
    return '-' if value is None else f'{value:.3f}'
for path in paths:
    r=json.loads(path.read_text())
    row=[path.stem,fmt(r['mean_input_tokens']),str(r['concurrency']),
         str(r['requests']),fmt(r['ttft_p50_s']),fmt(r['ttft_p95_s']),
         fmt(r['latency_p50_s']),fmt(r['latency_p95_s']),
         fmt(r['throughput_req_s']),fmt(r['throughput_output_tok_s']),
         str(r['failures'])]
    lines.append('| '+' | '.join(row)+' |')
Path('results/table.md').write_text('\n'.join(lines)+'\n')
print('Saved results/table.md')
