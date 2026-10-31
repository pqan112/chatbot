from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    cors_origin: str = "http://localhost:5173"
    neon_database_url: str = ""
    embed_model: str = "nomic-embed-text"


settings = Settings()
