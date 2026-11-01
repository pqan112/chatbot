from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    llm_model: str = "gpt-6-luna"
    vector_store_id: str = ""
    cors_origin: str = "http://localhost:5173"


settings = Settings()
