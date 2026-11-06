#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -s requirements.txt
test -s requirements-download.txt
PYTHON_BASE="$(cat base-image.txt)"
docker build --platform linux/amd64 --build-arg PYTHON_BASE="$PYTHON_BASE" -t vllm-cpu:local -f Dockerfile .
docker build --platform linux/amd64 --build-arg PYTHON_BASE="$PYTHON_BASE" -t model-download:local -f Dockerfile.download .
docker run --rm --entrypoint python vllm-cpu:local -c \
  'import vllm, torch; print(vllm.__version__); print("torch CUDA build:", torch.version.cuda); assert vllm.__version__.split("+")[0] == "0.27.0"; assert torch.version.cuda is None'
