#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker run --rm --entrypoint python model-download:local -c \
  'from huggingface_hub import HfApi; print(HfApi().model_info("Qwen/Qwen2.5-0.5B-Instruct").sha)' > model-revision.txt
python3 - <<'PY'
from pathlib import Path
import re
sha = Path('model-revision.txt').read_text().strip()
assert re.fullmatch(r'[0-9a-f]{40}', sha), 'Expected a full model commit SHA'
p = Path('k8s/configmap.yaml')
p.write_text(re.sub(r'(?m)^  MODEL_REVISION: .+$',
                   '  MODEL_REVISION: ' + sha, p.read_text()))
print('Model revision fixed in ConfigMap. Commit both files.')
PY
