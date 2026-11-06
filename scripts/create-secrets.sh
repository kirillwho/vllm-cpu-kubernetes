#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .local
chmod 700 .local
umask 077
if [[ ! -s .local/api-token ]]; then
  python3 -c 'import secrets; print(secrets.token_hex(32), end="")' > .local/api-token
fi
read -rsp 'HF read token (Enter for public model): ' HF_READ_TOKEN
echo
printf '%s' "$HF_READ_TOKEN" > .local/hf-token
unset HF_READ_TOKEN
kubectl create namespace llm-lab --dry-run=client -o yaml | kubectl apply -f -
kubectl -n llm-lab create secret generic llm-secrets \
  --from-file=api-token=.local/api-token --from-file=hf-token=.local/hf-token \
  --dry-run=client -o yaml | kubectl apply -f -
