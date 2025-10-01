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

# --- Manual mapping (filename → id/label/product_id)
MANUALS = {
    "03-032-20256-04_Linea_ML_8k_16k_Color_Camera.pdf": {
        "id": "linea-ml-16k-color",
        "label": "Linea ML 8k/16k Color Camera",
        "product_id": "LineaML",
    },
    "03-032-20295-07_Falcon4-CLHS_Series_User.pdf": {
        "id": "falcon4-clhs-series",
        "label": "Falcon4 CLHS Series Camera",
        "product_id": "Falcon4",
    },
    "03-032-25022-09_AxCIS_User_Manual.pdf": {
        "id": "axcis-user",
        "label": "AxCIS User Manual",
        "product_id": "AxCIS",
    },
    "03-032-25036-05_Linea_HS2_Series_User_Manual.pdf": {
        "id": "linea-hs2-series",
        "label": "Linea HS2 Series Camera",
        "product_id": "LineaHS2",
    },
}

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

for filename, meta in MANUALS.items():
    pdf_path = os.path.join(MANUALS_DIR, filename)
    if not os.path.exists(pdf_path):
        print(f"⚠️  Skipping {filename} (not found)")
        continue

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
