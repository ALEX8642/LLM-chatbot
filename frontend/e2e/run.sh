#!/bin/bash
# Replay end-to-end check: writes a recording with the real answer path over the fixture
# ingest, serves it in replay mode (no models), serves the built frontend, drives it.
# Usage: frontend/e2e/run.sh [screenshot dir]   (needs uv, node on PATH, Playwright)
set -e
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SHOTS=$(mkdir -p "${1:-$ROOT/frontend/e2e/out}" && cd "${1:-$ROOT/frontend/e2e/out}" && pwd)
WORK=$(mktemp -d)
PY="uv run -q --isolated --no-project --python 3.12 --with pytest --with pymupdf==1.26.4 --with pillow --with rapidfuzz --with qdrant-client --with fastapi --with httpx --with uvicorn"
for port in 8000 4173; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then echo "port $port is in use"; exit 1; fi
done
cd "$ROOT"
MANUALQA_E2E_OUT=$WORK $PY -- python -m pytest -p no:cacheprovider -q -W ignore::DeprecationWarning \
  tests/manualqa/test_e2e_recording.py >/dev/null
PYTHONPATH=. $PY -- python -m manualqa.server --replay "$WORK/recording.jsonl" --ingest "$WORK" --port 8000 \
  >"$WORK/server.log" 2>&1 &
SERVER=$!
cd frontend && npm run -s build >/dev/null && npx vite preview --host 127.0.0.1 --port 4173 --strictPort >"$WORK/preview.log" 2>&1 &
PREVIEW=$!
trap 'kill $SERVER $PREVIEW 2>/dev/null; pkill -f "vite[ ]preview --host 127.0.0.1 --port 4173" 2>/dev/null; rm -rf "$WORK"' EXIT
for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:4173/api/manuals >/dev/null && break
  sleep 1
done
curl -sf http://127.0.0.1:4173/api/manuals >/dev/null || { echo "servers not up"; cat "$WORK/server.log" "$WORK/preview.log"; exit 1; }
cd "$ROOT/frontend" && node e2e/replay.mjs http://127.0.0.1:4173 "$SHOTS"
