import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, health, voice
from app.config import settings
from app.db.connection import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    await init_db(app)
    yield
    await close_db(app)


app = FastAPI(
    title="Taliu Resume Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(voice.router, prefix="/ws")
