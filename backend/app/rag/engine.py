"""RAG engine: wires Qdrant retrieval + BM25 + OpenAI LLM via LlamaIndex."""

from pathlib import Path
from typing import Tuple

from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.chat_engine import CondensePlusContextChatEngine, ContextChatEngine
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


def _build_retriever() -> Tuple[QueryFusionRetriever, OpenAI]:
    """Shared setup: embedding model, LLM, Qdrant + BM25 retriever."""
    Settings.embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=settings.openai_api_key,
    )
    llm = OpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,
    )
    Settings.llm = llm

    qdrant_client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    async_qdrant_client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    vector_store = QdrantVectorStore(
        client=qdrant_client,
        aclient=async_qdrant_client,
        collection_name=settings.qdrant_collection,
    )
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
    vector_retriever = index.as_retriever(similarity_top_k=10)

    chunks = parse_resume(str(RESUME_PATH))
    nodes = [TextNode(text=chunk.text, metadata=chunk.metadata) for chunk in chunks]
    bm25_retriever = BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=10)

    retriever = QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        similarity_top_k=10,
        num_queries=1,
        mode="reciprocal_rerank",
        use_async=True,
    )
    return retriever, llm


def build_chat_engine() -> CondensePlusContextChatEngine:
    """Text chat engine — condenses multi-turn questions before retrieval."""
    retriever, llm = _build_retriever()
    memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
    return CondensePlusContextChatEngine.from_defaults(
        retriever=retriever,
        llm=llm,
        memory=memory,
        system_prompt=SYSTEM_PROMPT,
        verbose=False,
    )


def build_voice_chat_engine() -> ContextChatEngine:
    """Voice chat engine — skips condense step for lower latency."""
    retriever, llm = _build_retriever()
    memory = ChatMemoryBuffer.from_defaults(token_limit=2000)
    return ContextChatEngine.from_defaults(
        retriever=retriever,
        llm=llm,
        memory=memory,
        system_prompt=SYSTEM_PROMPT,
        verbose=False,
    )
