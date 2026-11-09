#!/bin/sh
# Container entry point. MODE=replay serves the recorded answers with no model; MODE=live
# (the default) builds the index on first start, then answers questions.
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

EMBEDDER="${EMBEDDER:-st:Qwen/Qwen3-Embedding-0.6B}"
RERANKER="${RERANKER:-qwen:Qwen/Qwen3-Reranker-4B}"

if [ ! -f /data/ingest/summary.json ]; then
  echo "First start: building the index from the bundled parses (minutes on a GPU, longer without)."
  python -m manualqa.ingest --raw manuals/paddle-parses.jsonl.gz --out /data/ingest --embedder "$EMBEDDER"
fi

RECORD=""
[ "${RECORD_ANSWERS:-1}" = 1 ] || RECORD="--no-record"
echo "Loading models; open http://localhost:8000 (or the PORT set in .env) once Uvicorn says it is running."
exec python -m manualqa.server $SERVE --recordings /data/recordings \
  --embedder "$EMBEDDER" --reranker "$RERANKER" $RECORD
