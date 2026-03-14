from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

PLACEHOLDER_VALUES = {"YOUR_CHAT_MODEL", "YOUR_EMBED_MODEL", "CHANGE_ME", "TODO"}

_VALID_LOG_LEVELS = frozenset({"debug", "info", "warning", "error"})
_VALID_PROVIDERS   = frozenset({"openrouter", "openai", "xai", "none"})


class AppConfig(BaseModel):
    env: str = Field(default="development")
    log_level: str = Field(default="info")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        vv = v.strip().lower()
        if vv not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"app.log_level must be one of {sorted(_VALID_LOG_LEVELS)}, got: {v!r}"
            )
        return vv


class LLMConfig(BaseModel):
    provider: str = Field(default="none")
    chat_model: str = Field(..., min_length=1)
    embedding_model: Optional[str] = Field(default=None)
    base_url: Optional[str] = Field(default=None)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        vv = v.strip().lower()
        if vv not in _VALID_PROVIDERS:
            raise ValueError(
                f"llm.provider must be one of {sorted(_VALID_PROVIDERS)}, got: {v!r}"
            )
        return vv

    @field_validator("chat_model")
    @classmethod
    def validate_chat_model(cls, v: str) -> str:
        vv = v.strip()
        if not vv:
            raise ValueError("llm.chat_model cannot be empty")
        if vv.upper() in PLACEHOLDER_VALUES:
            raise ValueError("llm.chat_model is still a placeholder. Set YOUR_CHAT_MODEL.")
        return vv

    @field_validator("embedding_model")
    @classmethod
    def validate_embedding_model(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        vv = v.strip()
        if not vv:
            return None
        if vv.upper() in PLACEHOLDER_VALUES:
            raise ValueError(
                "llm.embedding_model is still a placeholder. Set YOUR_EMBED_MODEL or leave it blank."
            )
        return vv

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        vv = v.strip()
        return vv if vv else None


class MemoryConfig(BaseModel):
    enabled: bool = Field(default=False)
    vector_store: str = Field(default="local")
    vector_store_path: str = Field(default=".data/vector_store")

    @field_validator("vector_store")
    @classmethod
    def validate_vector_store(cls, v: str) -> str:
        vv = v.strip()
        if not vv:
            raise ValueError("memory.vector_store cannot be empty")
        return vv

    @field_validator("vector_store_path")
    @classmethod
    def validate_vector_store_path(cls, v: str) -> str:
        vv = v.strip()
        if not vv:
            raise ValueError("memory.vector_store_path cannot be empty")
        return vv


class ConnectorsConfig(BaseModel):
    cli: bool = Field(default=True)
    telegram: bool = Field(default=False)
    voice: bool = Field(default=False)


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    connectors: ConnectorsConfig = Field(default_factory=ConnectorsConfig)

    @model_validator(mode="after")
    def cross_field_gates(self) -> "Settings":
        if self.memory.enabled:
            if not self.llm.embedding_model:
                raise ValueError(
                    "Memory is enabled but llm.embedding_model is not set. "
                    "Set YOUR_EMBED_MODEL (example: text-embedding-3-small) or disable memory."
                )
        return self
