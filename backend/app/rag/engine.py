"""RAG engine: wires Qdrant retrieval + OpenAI LLM via LlamaIndex."""

from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient

from app.config import settings
from app.rag.prompt import SYSTEM_PROMPT


def build_chat_engine() -> CondensePlusContextChatEngine:
    """Build a LlamaIndex chat engine backed by Qdrant retrieval."""

    # Configure embedding model
    Settings.embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=settings.openai_api_key,
    )

    # Configure LLM (model is configurable via OPENAI_MODEL env var)
    llm = OpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,
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

    # Build index from existing Qdrant collection
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

    # Build chat engine with conversation memory
    retriever = index.as_retriever(similarity_top_k=5)
    memory = ChatMemoryBuffer.from_defaults(token_limit=3000)

    chat_engine = CondensePlusContextChatEngine.from_defaults(
        retriever=retriever,
        llm=llm,
        memory=memory,
        system_prompt=SYSTEM_PROMPT,
        verbose=False,
    )

    return chat_engine
