from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/cognosos",
        alias="DATABASE_URL",
    )

    embedding_provider: str = Field(default="sentence_transformers", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="BAAI/bge-m3", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=1024, alias="EMBEDDING_DIM")
    embedding_normalize: bool = Field(default=True, alias="EMBEDDING_NORMALIZE")

    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    allow_remote_llm: bool = Field(default=False, alias="ALLOW_REMOTE_LLM")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_llm_model: str = Field(default="gemini-3.5-flash", alias="GEMINI_LLM_MODEL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_llm_model: str = Field(default="gpt-4o-mini", alias="OPENAI_LLM_MODEL")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_llm_model: str = Field(default="claude-opus-4-8", alias="ANTHROPIC_LLM_MODEL")

    trigger_high_similarity: float = Field(default=0.78, alias="TRIGGER_HIGH_SIMILARITY")
    trigger_medium_similarity: float = Field(default=0.72, alias="TRIGGER_MEDIUM_SIMILARITY")
    trigger_short_window_days: int = Field(default=14, alias="TRIGGER_SHORT_WINDOW_DAYS")
    trigger_medium_window_days: int = Field(default=30, alias="TRIGGER_MEDIUM_WINDOW_DAYS")
    trigger_long_window_days: int = Field(default=90, alias="TRIGGER_LONG_WINDOW_DAYS")

    app_timezone: str = Field(default="UTC", alias="APP_TIMEZONE")
    obsidian_vault_path: str = Field(
        default="./obsidian-vault-demo",
        validation_alias=AliasChoices("COGNOSOS_VAULT_PATH", "MARKDOWN_VAULT_PATH", "OBSIDIAN_VAULT_PATH"),
    )
    obsidian_daily_folder: str = Field(
        default="Calendar",
        validation_alias=AliasChoices("COGNOSOS_DAILY_FOLDER", "MARKDOWN_DAILY_FOLDER", "OBSIDIAN_DAILY_FOLDER"),
    )

    @property
    def markdown_vault_path(self) -> str:
        return self.obsidian_vault_path

    @property
    def markdown_daily_folder(self) -> str:
        return self.obsidian_daily_folder


@lru_cache
def get_settings() -> Settings:
    return Settings()
