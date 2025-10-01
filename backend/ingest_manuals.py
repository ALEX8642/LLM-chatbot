"""Manual ingestion script for the chatbot.

# © 2025 Alexander Feht
# Licensed under the MIT License
# This project was created independently and is not affiliated with any employer.

This script automatically processes PDF manuals and ingests them into the vector stores:
1. Scans the manuals directory for PDF files
2. Automatically extracts metadata from filenames
3. Splits documents into chunks
4. Generates embeddings
5. Stores in Qdrant (dense) and OpenSearch (sparse/hybrid)

No manual configuration needed - just place PDFs in the manuals directory and run.
Optionally, you can override metadata by creating a manual_metadata.json file.
"""

import os
import json
from pathlib import Path
import fitz  # PyMuPDF
from haystack import Document, Pipeline
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack.components.writers import DocumentWriter
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from haystack_integrations.document_stores.opensearch import OpenSearchDocumentStore

# --- Paths
PROJ_ROOT = Path(__file__).resolve().parent.parent
MANUALS_DIR = PROJ_ROOT / "frontend" / "public" / "manuals"
MANUALS_JSON = MANUALS_DIR / "manuals.json"

# --- Utilities for automatic metadata extraction
import re
from typing import Dict, Any

def clean_filename(filename: str) -> str:
    """Remove common PDF naming patterns and clean up the name."""
    # Remove file extension
    name = filename.replace('.pdf', '')
    
    # Remove common patterns like version numbers (e.g., v1.0, r2.1)
    name = re.sub(r'[vr]\d+\.\d+', '', name, flags=re.IGNORECASE)
    
    # Remove common document numbers (e.g., 123-456-789)
    name = re.sub(r'\d+-\d+-\d+[-_]', '', name)
    
    # Replace underscores and hyphens with spaces
    name = name.replace('_', ' ').replace('-', ' ')
    
    # Clean up multiple spaces
    name = ' '.join(name.split())
    
    return name

def extract_manual_metadata(filename: str) -> Dict[str, Any]:
    """Extract metadata from filename and optionally PDF content."""
    clean_name = clean_filename(filename)
    
    # Create a URL-friendly ID
    manual_id = re.sub(r'[^a-z0-9]+', '-', clean_name.lower()).strip('-')
    
    # Try to extract a product family from the first word
    product_family = clean_name.split()[0]
    
    return {
        "id": manual_id,
        "label": clean_name,
        "product_id": product_family
    }

def get_manual_metadata(filename: str) -> Dict[str, Any]:
    """Get metadata for a manual, with option for manual override."""
    # First, try automatic extraction
    metadata = extract_manual_metadata(filename)
    
    # Optional: Look for manual override in a config file
    # This allows users to customize metadata if needed
    # config_path = PROJ_ROOT / "manual_metadata.json"
    # if config_path.exists():
    #     with open(config_path) as f:
    #         overrides = json.load(f)
    #         if filename in overrides:
    #             metadata.update(overrides[filename])
    
    return metadata

def pdf_to_docs(pdf_path: str, manual_id: str, product_id: str):
    """Convert PDF pages into Haystack Documents with metadata."""
    doc = fitz.open(pdf_path)
    documents = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        if text.strip():
            documents.append(
                Document(
                    content=text,
                    meta={"page": page_num, "manual_id": manual_id, "product_id": product_id}
                )
            )
    return documents

print("🔄 Resetting vector stores (Qdrant + OpenSearch)...")

# --- Reset stores
qdrant = QdrantDocumentStore(
    url="http://localhost:6333", index="manuals", embedding_dim=384, recreate_index=True
)
opensearch = OpenSearchDocumentStore(
    hosts="http://localhost:9200", username="admin", password="admin", index="manuals", recreate_index=True
)

# --- Ingestion pipeline
splitter = DocumentSplitter(split_by="word", split_length=250, split_overlap=50)
embedder = SentenceTransformersDocumentEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
writer_qdrant = DocumentWriter(document_store=qdrant, policy="upsert")
writer_os = DocumentWriter(document_store=opensearch, policy="upsert")

ingest = Pipeline()
ingest.add_component("splitter", splitter)
ingest.add_component("embedder", embedder)
ingest.add_component("writer_qdrant", writer_qdrant)
ingest.add_component("writer_os", writer_os)

ingest.connect("splitter.documents", "embedder.documents")
ingest.connect("embedder.documents", "writer_qdrant.documents")
ingest.connect("splitter.documents", "writer_os.documents")

# --- Run ingestion for all manuals
manuals_list = []
total_qdrant, total_os = 0, 0

# Find all PDFs in the manuals directory
pdf_files = [f for f in os.listdir(MANUALS_DIR) if f.lower().endswith('.pdf')]

for filename in pdf_files:
    pdf_path = os.path.join(MANUALS_DIR, filename)
    if not os.path.exists(pdf_path):
        print(f"⚠️  Skipping {filename} (not found)")
        continue
        
    # Automatically extract metadata
    meta = get_manual_metadata(filename)

    print(f"📄 Ingesting {filename}...")
    docs = pdf_to_docs(pdf_path, meta["id"], meta["product_id"])
    res = ingest.run({"splitter": {"documents": docs}})
    qd_count = res["writer_qdrant"]["documents_written"]
    os_count = res["writer_os"]["documents_written"]
    total_qdrant += qd_count
    total_os += os_count

    print(f"   ✅ {qd_count} → Qdrant, {os_count} → OpenSearch")

    manuals_list.append({
        "id": meta["id"],
        "label": meta["label"],
        "pdf_url": f"/manuals/{filename}",
    })

# --- Save manuals.json
if manuals_list:
    with open(MANUALS_JSON, "w") as f:
        json.dump(manuals_list, f, indent=2)
    print(f"\n🎉 Ingested {len(manuals_list)} manuals.")
    print(f"   Total chunks: {total_qdrant} → Qdrant, {total_os} → OpenSearch")
    print(f"   📂 manuals.json written to {MANUALS_JSON}")
else:
    print("\n❌ No manuals ingested! Check MANUALS_DIR or filenames.")
