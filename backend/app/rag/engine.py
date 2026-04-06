"""RAG engine: wires Qdrant retrieval + BM25 + OpenAI LLM via LlamaIndex."""

from pathlib import Path

from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.schema import TextNode
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient

from app.config import settings
from app.ingestion.chunking import parse_resume
from app.rag.prompt import SYSTEM_PROMPT

RESUME_PATH = Path(__file__).parents[1] / "ingestion" / "data" / "resume.md"


def build_chat_engine() -> CondensePlusContextChatEngine:
    """Build a LlamaIndex chat engine backed by hybrid (BM25 + semantic) retrieval."""

    # Configure embedding model
    Settings.embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=settings.openai_api_key,
    )

    # Configure LLM
    llm = OpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,
        additional_kwargs={"stream_options": {"include_usage": True}},
    )
    Settings.llm = llm

    # Connect to Qdrant (both sync and async clients for streaming support)
    qdrant_client = QdrantClient(
        host=settings.qdrant_host, port=settings.qdrant_port
    )
    async_qdrant_client = AsyncQdrantClient(
        host=settings.qdrant_host, port=settings.qdrant_port
    )
    vector_store = QdrantVectorStore(
        client=qdrant_client,
        aclient=async_qdrant_client,
        collection_name=settings.qdrant_collection,
    )

    # Semantic retriever — Qdrant vector search
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
    vector_retriever = index.as_retriever(similarity_top_k=10)

    # BM25 retriever — built from resume chunks loaded at startup
    chunks = parse_resume(str(RESUME_PATH))
    nodes = [
        TextNode(text=chunk.text, metadata=chunk.metadata)
        for chunk in chunks
    ]
    bm25_retriever = BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=10)

    # Fusion retriever — RRF merges and deduplicates both result sets
    retriever = QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        similarity_top_k=10,
        num_queries=1,
        mode="reciprocal_rerank",
        use_async=True,
    )

    # Build chat engine with conversation memory
    memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
    chat_engine = CondensePlusContextChatEngine.from_defaults(
        retriever=retriever,
        llm=llm,
        memory=memory,
        system_prompt=SYSTEM_PROMPT,
        verbose=False,
    )

    return chat_engine
