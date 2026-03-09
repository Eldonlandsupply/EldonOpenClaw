"""
src/openclaw/chat/client.py

Async LLM chat client supporting OpenRouter and OpenAI.
Uses the OpenAI-compatible /v1/chat/completions endpoint.
Authorization is Bearer token (API key — often called "oauth" in OpenRouter docs).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from openclaw.config import AppConfig

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are OpenClaw, a helpful AI agent running on a Raspberry Pi at Eldon Land Supply. "
    "Answer clearly and concisely."
)

_PROVIDER_URLS: dict[str, str] = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",  # note: different schema
}


class ChatClient:
    """
    Stateful async chat client with in-memory message history.

    Usage:
        client = ChatClient(cfg)
        reply = await client.chat("Hello!")
    """

    MAX_HISTORY = 40  # messages (user+assistant pairs)

    def __init__(self, cfg: AppConfig) -> None:
        self._provider = cfg.llm.provider
        self._model = cfg.llm.chat_model

        if self._provider == "openrouter":
            self._base_url = _PROVIDER_URLS["openrouter"]
            self._api_key = cfg.secrets.openrouter_api_key or ""
        elif self._provider == "openai":
            self._base_url = cfg.llm.base_url or _PROVIDER_URLS["openai"]
            self._api_key = cfg.secrets.openai_api_key or ""
        else:
            self._base_url = ""
            self._api_key = ""

        self._history: list[dict] = []
        logger.info(
            "ChatClient init: provider=%s model=%s",
            self._provider,
            self._model,
        )

    # ── public ────────────────────────────────────────────────────────────

    async def chat(self, user_message: str) -> str:
        """Send a message and return the assistant reply."""
        if self._provider == "none" or not self._api_key:
            return f"[no LLM configured] echo: {user_message}"

        self._history.append({"role": "user", "content": user_message})
        self._trim_history()

        try:
            reply = await self._call_api()
        except Exception as exc:
            logger.error("ChatClient error: %s", exc)
            self._history.pop()  # remove failed user message
            return f"[LLM error] {exc}"

        self._history.append({"role": "assistant", "content": reply})
        return reply

    def reset(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    # ── private ───────────────────────────────────────────────────────────

    async def _call_api(self) -> str:
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}] + self._history

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/Eldonlandsupply/EldonOpenClaw"
            headers["X-Title"] = "OpenClaw"

        payload = {
            "model": self._model,
            "messages": messages,
        }

        url = f"{self._base_url}/chat/completions"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"HTTP {resp.status}: {body[:200]}")
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()

    def _trim_history(self) -> None:
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]
