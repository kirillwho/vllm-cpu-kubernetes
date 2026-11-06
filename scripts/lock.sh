#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f base-image.txt ]]; then
  docker pull --platform linux/amd64 python:3.12-slim-bookworm
  docker image inspect python:3.12-slim-bookworm --format '{{index .RepoDigests 0}}' > base-image.txt
fi
PYTHON_BASE="$(cat base-image.txt)"
[[ "$PYTHON_BASE" == *@sha256:* ]]
docker build --platform linux/amd64 --build-arg PYTHON_BASE="$PYTHON_BASE" -f Dockerfile.lock -t vllm-lock:local .
for name in requirements requirements-download; do
  docker run --rm --platform linux/amd64 --user "$(id -u):$(id -g)" \
    -e HOME=/tmp -e PIP_CACHE_DIR=/tmp/pip-cache \
    -v "$PWD:/work" vllm-lock:local --cache-dir /tmp/piptools \
    --verbose --output-file "$name.txt" "$name.in"
done
echo 'Lock files generated. Commit both .txt files and base-image.txt.'
