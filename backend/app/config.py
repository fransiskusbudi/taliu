from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "resume_chunks"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "info"
    database_url: str = "postgresql://taliu:taliu@postgres:5432/taliu"
    message_limit: int = 10
    deepgram_api_key: str = ""
    gemini_api_key: str = ""
    gemini_tts_model: str = "gemini-3.1-flash-tts-preview"
    gemini_tts_voice: str = "Kore"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
