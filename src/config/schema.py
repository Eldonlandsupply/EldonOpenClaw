"""
src/config/schema.py
Single source of truth for all config fields and validation rules.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


_PLACEHOLDERS = {"YOUR_CHAT_MODEL", "YOUR_EMBED_MODEL", "CHANGE_ME", ""}


class AppConfig(BaseModel):
    env: str = Field(default="development")
    log_level: str = Field(default="info")

    @field_validator("log_level")
    @classmethod
    def valid_log_level(cls, v: str) -> str:
        allowed = {"debug", "info", "warning", "error", "critical"}
        if v.lower() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got {v!r}")
        return v.lower()


class LLMConfig(BaseModel):
    chat_model: str = Field(..., min_length=1)
    embedding_model: Optional[str] = Field(default=None)
    base_url: Optional[str] = Field(default=None)

    @field_validator("chat_model")
    @classmethod
    def chat_model_not_placeholder(cls, v: str) -> str:
        if v.strip().upper() in {p.upper() for p in _PLACEHOLDERS if p}:
            raise ValueError(
                f"llm.chat_model is still a placeholder ({v!r}). "
                "Set OPENCLAW_CHAT_MODEL in your .env file."
            )
        return v

    @field_validator("embedding_model")
    @classmethod
    def embed_model_not_placeholder(cls, v: Optional[str]) -> Optional[str]:
        if v and v.strip().upper() in {p.upper() for p in _PLACEHOLDERS if p}:
            raise ValueError(
                f"llm.embedding_model is still a placeholder ({v!r}). "
                "Set OPENCLAW_EMBED_MODEL or leave it blank to disable embeddings."
            )
        return v or None

    @field_validator("base_url")
    @classmethod
    def base_url_strip(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v and v.strip() else None


class ConnectorsConfig(BaseModel):
    cli: bool = Field(default=True)
    telegram: bool = Field(default=False)
    voice: bool = Field(default=False)


class MemoryConfig(BaseModel):
    enabled: bool = Field(default=False)
    vector_store: str = Field(default="local")
    vector_store_path: str = Field(default=".data/vector_store")

    @field_validator("vector_store_path")
    @classmethod
    def path_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("memory.vector_store_path cannot be empty")
        return v


class ActionsConfig(BaseModel):
    require_confirmation: bool = Field(default=True)


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig
    connectors: ConnectorsConfig = Field(default_factory=ConnectorsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    actions: ActionsConfig = Field(default_factory=ActionsConfig)

    @model_validator(mode="after")
    def cross_field_gates(self) -> "Settings":
        # Memory enabled → embedding model required
        if self.memory.enabled:
            if not self.llm.embedding_model:
                raise ValueError(
                    "memory.enabled=true requires llm.embedding_model to be set. "
                    "Set OPENCLAW_EMBED_MODEL (e.g., text-embedding-3-small) "
                    "or set OPENCLAW_MEMORY_ENABLED=false."
                )
        # Telegram enabled → bot token must exist in env (checked at connector init)
        return self
