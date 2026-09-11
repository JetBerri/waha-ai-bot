from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from the environment and the .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    port: int = 8000
    business_name: str = "Innovacar"

    # Fallback only, the bot mirrors whatever language the user writes in.
    fallback_language: str = "Spanish"

    # Waha, waha_url must be reachable from this process
    waha_url: str = "http://localhost:3000"
    waha_api_key: str = ""
    waha_session: str = "default"

    # Shared secret used to verify the hmac signature of incoming webhooks
    webhook_secret: str = ""

    # Seconds to buffer consecutive messages before answering
    debounce_seconds: float = 6.0

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-5.6-terra"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_transcription_model: str = "whisper-1"
    # None leaves it unset, some newer models reject the parameter outright.
    openai_temperature: float | None = None

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_knowledge_collection: str = "knowledge"
    qdrant_memory_collection: str = "memory"
    sparse_embedding_model: str = "Qdrant/bm25"

    # Retrieval tuning
    knowledge_top_k: int = 6
    memory_top_k: int = 6
    memory_recent_turns: int = 10


settings = Settings()
