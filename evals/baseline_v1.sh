#!/usr/bin/env bash
# Reproduce the v1 baseline: check out tag v1 next to this repo, start its
# stores, ingest the bundled manuals with v1's own script, and generate answers.
#
# Needs: git, uv, Docker with Compose, an Ollama server with command-r7b.
# Env:   OPENSEARCH_PASS (any strong password; security is disabled in compose)
#        OLLAMA_URL      (default http://localhost:11434)
#        REPEATS         (default 3; v1 samples at Ollama's default temperature)
# Then score with: python evals/run_eval.py score <raw> --out evals/results/v1.json
set -euo pipefail

REPO="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
V1="${V1_DIR:-$REPO/../LLM-chatbot-v1}"
REPEATS="${REPEATS:-3}"
: "${OPENSEARCH_PASS:?set OPENSEARCH_PASS}"
export OPENSEARCH_PASS OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"

[ -d "$V1" ] || git -C "$REPO" worktree add --detach "$V1" v1
mkdir -p "$V1/frontend/public/manuals"
cp "$REPO"/manuals/*.pdf "$V1/frontend/public/manuals/"

(cd "$V1" && uv sync --frozen)
docker compose -f "$V1/docker-compose.yaml" up -d opensearch qdrant
for url in http://localhost:9200 http://localhost:6333/healthz; do
  until curl -sf -o /dev/null "$url"; do sleep 5; done
done

(cd "$V1" && uv run python backend/ingest_manuals.py)

for system in v1 v1-strict; do
  (cd "$V1" && uv run python "$REPO/evals/run_eval.py" generate --system "$system" \
    --app-dir "$V1" --repeats "$REPEATS" --out "$REPO/evals/results/raw/$system.json")
done
