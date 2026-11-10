# A small image: the interface, the server, the manuals and their parses, and what replay needs.
# The live system's dependencies (PyTorch with CUDA, about 7 GB installed) are installed on its
# first start into the deps volume, and the models into the models volume, so a pull stays small.

FROM node:22-slim AS interface
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/deps/venv \
    HF_HOME=/models PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock README.md ./
COPY docker/replay.in docker/replay.in
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/lock.txt \
    && uv pip install --system --no-cache -r docker/replay.in -c /tmp/lock.txt \
    && rm /tmp/lock.txt
COPY manualqa manualqa
COPY manuals manuals
COPY docs/demo/replay.jsonl docs/demo/replay.jsonl
COPY docker/start.sh /usr/local/bin/start
COPY --from=interface /app/frontend/dist interface
RUN useradd --create-home --uid 1000 app && mkdir -p /data /models /deps && chown app /data /models /deps
USER app
EXPOSE 8000
ENTRYPOINT ["start"]
