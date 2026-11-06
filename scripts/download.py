import hashlib
import json
import os
from pathlib import Path
import re
import sys

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def run():
    repo, revision = os.environ['MODEL_ID'], os.environ['MODEL_REVISION']
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('revision must be a commit SHA')
    target = Path(os.environ.get('MODEL_DIR', '/models/model'))
    marker = target / '.complete.json'
    if marker.exists():
        data = json.loads(marker.read_text())
        if (data['repo'], data['revision']) != (repo, revision):
            raise ValueError('cache revision mismatch')
        for name, sha in data['files'].items():
            path = target / name
            if not path.is_file() or digest(path) != sha:
                raise ValueError('cache integrity check failed')
        print('{"event":"model_cache_hit","network_used":false}', flush=True)
        return
    if os.environ.get('CACHE_ONLY') == '1':
        raise ValueError('complete cache required')
    # Import and all Hub calls are deliberately below the offline branch.
    from huggingface_hub import snapshot_download
    token_path = Path('/run/secrets/hf-token')
    token = token_path.read_text().strip() if token_path.exists() else ''
    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=repo, revision=revision, local_dir=target,
                      token=token or False,
                      allow_patterns=['*.json', '*.safetensors', '*.model', '*.txt', '*.tiktoken'])
    weights = list(target.glob('*.safetensors'))
    if not weights or not (target / 'config.json').exists():
        raise ValueError('model files missing')
    manifest = {str(p.relative_to(target)): digest(p)
                for p in target.rglob('*')
                if p.is_file() and '.cache' not in p.relative_to(target).parts
                and p.name not in ('.complete.json', '.complete.tmp')}
    data = {'repo': repo, 'revision': revision, 'files': manifest}
    temporary = target / '.complete.tmp'
    temporary.write_text(json.dumps(data))
    temporary.replace(marker)
    print('{"event":"model_download_complete"}', flush=True)

if __name__ == '__main__':
    try:
        run()
    except Exception:
        print('{"event":"model_init_failed"}', file=sys.stderr, flush=True)
        sys.exit(1)
