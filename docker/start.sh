#!/bin/sh
# Container entry point. MODE=replay serves the recorded answers with what the image holds.
# MODE=live (the default) installs the locked dependencies into /deps on its first start
# (PyTorch with CUDA, or the CPU build when DEVICE=cpu), builds the index, then answers.
set -e
cd /app
SERVE="--host 0.0.0.0 --port 8000 --static interface --ingest /data/ingest"

if [ "${MODE:-live}" = replay ]; then
  exec python -m manualqa.server $SERVE --replay docs/demo/replay.jsonl --no-record
fi

if [ -z "$GEN_BASE_URL" ] || [ -z "$GEN_MODEL" ]; then
  echo "Set GEN_BASE_URL and GEN_MODEL in .env (see .env.example): the chat endpoint that writes answers." >&2
  exit 1
fi

DEVICE="${DEVICE:-gpu}"
STAMP="/deps/installed-$DEVICE-$(sha256sum uv.lock | cut -c1-16)"
if [ ! -f "$STAMP" ]; then
  if [ "$DEVICE" = cpu ]; then
    echo "First start: installing dependencies with PyTorch for the processor (about 1 GB)."
    SKIP=$(grep -o '^name = "\(nvidia-[^"]*\|triton\|torch\)"' uv.lock | cut -d'"' -f2 | sed 's/^/--no-install-package /')
    uv sync --frozen --no-dev --no-install-project --inexact --no-cache $SKIP
    TORCH=$(grep -A1 '^name = "torch"' uv.lock | sed -n 's/^version = "\(.*\)"/\1/p')
    uv pip install --python /deps/venv/bin/python --no-cache "torch==$TORCH" \
      --index-url https://download.pytorch.org/whl/cpu
  else
    echo "First start: installing dependencies with PyTorch for NVIDIA GPUs (about 3 GB to download)."
    uv sync --frozen --no-dev --no-install-project --no-cache
  fi
  rm -f /deps/installed-*
  touch "$STAMP"
fi
PY=/deps/venv/bin/python

EMBEDDER="${EMBEDDER:-st:Qwen/Qwen3-Embedding-0.6B}"
RERANKER="${RERANKER:-qwen:Qwen/Qwen3-Reranker-4B}"

if [ ! -f /data/ingest/summary.json ]; then
  echo "First start: building the index from the bundled parses (minutes on a GPU, longer without)."
  $PY -m manualqa.ingest --raw manuals/paddle-parses.jsonl.gz --out /data/ingest --embedder "$EMBEDDER"
fi

RECORD=""
[ "${RECORD_ANSWERS:-1}" = 1 ] || RECORD="--no-record"
echo "Loading models; open http://localhost:8000 (or the PORT set in .env) once Uvicorn says it is running."
exec $PY -m manualqa.server $SERVE --recordings /data/recordings \
  --embedder "$EMBEDDER" --reranker "$RERANKER" $RECORD
