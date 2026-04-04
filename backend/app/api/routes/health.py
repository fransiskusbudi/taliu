from fastapi import APIRouter
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    qdrant_status = "connected"
    try:
        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        client.get_collections()
    except (UnexpectedResponse, Exception):
        qdrant_status = "disconnected"

    return {
        "status": "healthy",
        "qdrant": qdrant_status,
        "version": "0.1.0",
    }
