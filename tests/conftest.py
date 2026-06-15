"""
Stub out the heavy store/model imports before api.py is loaded.

api.py initialises QdrantDocumentStore, OpenSearchDocumentStore, and two
SentenceTransformers models at module-level, so they must be patched before
the first import.  This conftest runs automatically for every test session.
"""
from unittest.mock import MagicMock, patch
import sys

# Build lightweight fakes for every symbol api.py imports from haystack
_fake_doc_store = MagicMock()
_fake_pipe = MagicMock()
_fake_pipe.run.return_value = {}

_haystack_mocks = {
    "haystack": MagicMock(),
    "haystack.components.joiners": MagicMock(),
    "haystack.components.embedders": MagicMock(),
    "haystack.components.rankers": MagicMock(),
    "haystack_integrations.document_stores.qdrant": MagicMock(),
    "haystack_integrations.document_stores.opensearch": MagicMock(),
    "haystack_integrations.components.retrievers.qdrant": MagicMock(),
    "haystack_integrations.components.retrievers.opensearch": MagicMock(),
}

# Pipeline() must return our fake pipeline so pipe.run() is controllable
_pipeline_cls = MagicMock(return_value=_fake_pipe)
_haystack_mocks["haystack"].Pipeline = _pipeline_cls

for mod, mock in _haystack_mocks.items():
    sys.modules[mod] = mock

# Patch requests so query_ollama never hits the network
sys.modules.setdefault("requests", MagicMock())
