# One image for the live system and the replay demo: the interface, the server, the manuals
# and their parses. Models and the index are built or downloaded into volumes on first start.

FROM node:22-slim AS interface
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PATH=/app/.venv/bin:$PATH HF_HOME=/models PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-cache
COPY manualqa manualqa
COPY manuals manuals
COPY docs/demo/replay.jsonl docs/demo/replay.jsonl
COPY docker/start.sh /usr/local/bin/start
COPY --from=interface /app/frontend/dist interface
RUN useradd --create-home --uid 1000 app && mkdir -p /data /models && chown app /data /models
USER app
EXPOSE 8000
ENTRYPOINT ["start"]
