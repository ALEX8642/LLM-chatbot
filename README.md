# LLM-Chatbot

[![CI](https://github.com/ALEX8642/LLM-chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/ALEX8642/LLM-chatbot/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.112%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Haystack](https://img.shields.io/badge/Haystack-2.x-brightgreen)](https://haystack.deepset.ai)

A Haystack 2.x and Ollama based chatbot for user assistance interpreting manuals and documentation. Drop in your PDF manuals, and the system will automatically process them for intelligent question answering.

The default model is **Cohere Command R7B** (`command-r7b`) served locally by Ollama; set `OLLAMA_MODEL` to use another.

## Features

- FastAPI backend with Haystack 2.x for document processing and QA
- Hybrid retrieval: Qdrant dense vectors + OpenSearch BM25, fused and reranked (see [Retrieval pipeline](#retrieval-pipeline))
- Local LLM support via Ollama
- React/TypeScript frontend
- Document ingestion pipeline for manuals and documentation

## Project Structure

```
llm-chatbot/
├── backend/           # FastAPI server and API
│   ├── .env          # Backend environment variables
│   └── ingest_manuals.py  # Document ingestion script
├── frontend/         # React/TypeScript frontend
├── scripts/          # Utility scripts
│   └── launch.py     # Service launch and health check script
├── manuals/          # Place manuals and docs here for ingestion
├── docker-compose.yaml  # Docker services configuration
└── pyproject.toml    # Python dependencies and project metadata
```

## Requirements

- Python 3.10 or higher
- Node.js 18 or higher
- Docker and Docker Compose
- Ollama (for local LLM support)

## Working with Manuals

### Adding New Manuals

1. Place your PDF manuals in the `manuals/` directory
2. Run the ingestion script:
   ```bash
   python backend/ingest_manuals.py
   ```

The system will automatically:
- Extract metadata from filenames
- Generate unique IDs and readable labels
- Split documents into chunks
- Create embeddings and store them

For example:
```
Input filename: XYZ-123-456_Product_Manual_v2.1.pdf
↓
Automatic metadata:
{
    "id": "product-manual",
    "label": "Product Manual",
    "product_id": "XYZ"
}
```

### Custom Metadata (Optional)

If you need to override the automatic metadata, create a `manual_metadata.json` file:

```json
{
    "example.pdf": {
        "id": "custom-id",
        "label": "Custom Label",
        "product_id": "CustomProduct"
    }
}
```

## Setup

1. Install Python dependencies using uv:
   ```bash
   python -m pip install uv
   uv venv
   source .venv/bin/activate  # or .venv/Scripts/activate on Windows
   uv pip install -e .
   ```

   For development:
   ```bash
   uv pip install -e ".[dev]"
   ```

2. Configure environment variables:
   ```bash
   cp frontend/.env.example frontend/.env
   cp backend/.env.example backend/.env
   # Edit .env files as needed
   ```

3. Start required services:
   ```bash
   python scripts/launch.py
   ```

4. Set up the frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Development

### Backend Development

The backend uses FastAPI and Haystack 2.x:

1. Start the development server:
   ```bash
   uvicorn api:app --reload
   ```

2. Access the API docs at: http://localhost:8000/docs

### Frontend Development

The frontend is a React application with TypeScript:

1. Start the development server:
   ```bash
   cd frontend
   npm run dev
   ```

2. Access the UI at: http://localhost:5173

### Adding Documents

Place your documents in the `manuals/` directory and run:
```bash
python backend/ingest_manuals.py
```

## Architecture

- **FastAPI Backend**: Handles API requests, document processing, and LLM interactions
- **Qdrant**: Vector database for semantic search
- **OpenSearch**: Text search and document storage
- **Ollama**: Local LLM integration
- **Haystack**: Document processing and QA pipeline
- **React Frontend**: User interface and chat interactions

## Retrieval pipeline

Each question runs a Haystack pipeline that retrieves broadly for recall, then narrows for precision:

1. **Dense retrieval:** the query is embedded with `sentence-transformers/all-MiniLM-L6-v2` and searched in Qdrant.
2. **Sparse retrieval:** the same query runs as BM25 keyword search in OpenSearch, which catches part numbers and exact terms that embeddings miss.
3. **Fusion:** both result lists (top 30 each by default) are merged with reciprocal rank fusion (`DocumentJoiner`).
4. **Reranking:** a transformer cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) rescores the fused candidates against the question.
5. **Diversity:** maximum-marginal-relevance selection drops near-duplicate chunks, so the answer cites distinct passages.
6. **Grounding gate:** with guardrails on, chunks below a minimum relevance score are dropped. If none remain, the model receives no excerpts and is instructed to say the manual does not cover the question. With guardrails off, the top chunk is always passed through.

Retrieval is filtered to the selected manual. Answers carry citations back to the source pages. Every stage is configurable through environment variables (`RAG_RETRIEVE_TOP_K`, `RAG_MAX_CONTEXT_CHUNKS`, `RAG_JOIN_MODE`, `RAG_RERANK_MODEL`, `RAG_DIVERSITY_MODEL`, `RAG_MMR_LAMBDA`, `RAG_MIN_DOC_SCORE`).

## Docker Services

- **Qdrant**: Vector search (port 6333)
- **OpenSearch**: BM25 text search and document storage (port 9200). Set `OPENSEARCH_PASS` in the environment or a root `.env` before `docker compose up`; there is no default password
- **OpenSearch Dashboards**: Search visualization (port 5601)

Data is persisted in Docker volumes:
- `opensearch_data`: OpenSearch data
- `qdrant_data`: Qdrant vectors and metadata

This project is independently developed by Alexander Feht during personal time using personal hardware. It is not affiliated with or commissioned by any employer, and was licensed under MIT prior to any discussions with external parties.
