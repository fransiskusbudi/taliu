"""Ingestion script: parse resume, embed chunks, load into Qdrant."""

import sys
from pathlib import Path

from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

# Add project root to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import settings
from app.ingestion.chunking import parse_resume

RESUME_PATH = Path(__file__).parent / "data" / "resume.md"


def run_ingestion():
    print("Starting ingestion...")

    # 1. Parse resume into chunks
    chunks = parse_resume(str(RESUME_PATH))
    print(f"Parsed {len(chunks)} chunks from resume")

    for chunk in chunks:
        section = chunk.metadata.get("section", "unknown")
        company = chunk.metadata.get("company", "")
        label = f"{section}: {company}" if company else section
        print(f"  - {label}")

    # 2. Convert to LlamaIndex Documents
    documents = [
        Document(text=chunk.text, metadata=chunk.metadata) for chunk in chunks
    ]

    # 3. Configure LlamaIndex settings
    Settings.embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=settings.openai_api_key,
    )

    # Use a splitter that won't break our already-chunked sections too aggressively
    # Each resume section is small enough to be a single node
    Settings.node_parser = SentenceSplitter(chunk_size=1024, chunk_overlap=50)

    # 4. Connect to Qdrant
    qdrant_client = QdrantClient(
        host=settings.qdrant_host, port=settings.qdrant_port
    )

    vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=settings.qdrant_collection,
    )

    # 5. Build index (embeds documents and stores in Qdrant)
    print("Embedding and storing in Qdrant...")
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
    )

    print(f"Ingestion complete. {len(documents)} chunks stored in '{settings.qdrant_collection}'.")


if __name__ == "__main__":
    run_ingestion()
