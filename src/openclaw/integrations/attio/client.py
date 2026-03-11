"""
Attio REST API client.
Thin async wrapper — no third-party SDK required.
"""

from __future__ import annotations

import json
from typing import Any

import aiohttp

BASE_URL = "https://api.attio.com/v2"


class AttioClient:
    """Async HTTP client for the Attio API v2."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._session: aiohttp.ClientSession | None = None

    def _session_or_create(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str, params: dict | None = None) -> Any:
        session = self._session_or_create()
        async with session.get(f"{BASE_URL}{path}", params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _post(self, path: str, body: dict) -> Any:
        session = self._session_or_create()
        async with session.post(f"{BASE_URL}{path}", data=json.dumps(body)) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _patch(self, path: str, body: dict) -> Any:
        session = self._session_or_create()
        async with session.patch(f"{BASE_URL}{path}", data=json.dumps(body)) as resp:
            resp.raise_for_status()
            return await resp.json()

    # ── Records ──────────────────────────────────────────────────────────

    async def search_records(
        self,
        object_type: str,  # e.g. "companies" or "people"
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """Full-text search across an object type."""
        body = {"query": query, "limit": limit}
        resp = await self._post(f"/objects/{object_type}/records/query", body)
        return resp.get("data", [])

    async def get_record(self, object_type: str, record_id: str) -> dict:
        resp = await self._get(f"/objects/{object_type}/records/{record_id}")
        return resp.get("data", {})

    async def upsert_record(
        self,
        object_type: str,
        matching_attribute: str,
        values: dict,
    ) -> dict:
        body = {
            "data": {
                "values": values,
            }
        }
        resp = await self._put_upsert(object_type, matching_attribute, body)
        return resp.get("data", {})

    async def _put_upsert(self, object_type: str, matching_attribute: str, body: dict) -> Any:
        session = self._session_or_create()
        url = f"{BASE_URL}/objects/{object_type}/records?matching_attribute={matching_attribute}"
        async with session.put(url, data=json.dumps(body)) as resp:
            resp.raise_for_status()
            return await resp.json()

    # ── Notes ────────────────────────────────────────────────────────────

    async def create_note(
        self,
        parent_object: str,
        parent_record_id: str,
        title: str,
        content: str,
    ) -> dict:
        body = {
            "data": {
                "parent_object": parent_object,
                "parent_record_id": parent_record_id,
                "title": title,
                "format": "plaintext",
                "content": content,
            }
        }
        resp = await self._post("/notes", body)
        return resp.get("data", {})

    # ── Tasks ────────────────────────────────────────────────────────────

    async def create_task(
        self,
        content: str,
        linked_object: str | None = None,
        linked_record_id: str | None = None,
        deadline_at: str | None = None,
    ) -> dict:
        data: dict = {"content": content, "is_completed": False}
        if linked_object and linked_record_id:
            data["linked_records"] = [
                {"target_object": linked_object, "target_record_id": linked_record_id}
            ]
        if deadline_at:
            data["deadline_at"] = deadline_at
        resp = await self._post("/tasks", {"data": data})
        return resp.get("data", {})

    async def list_tasks(self, is_completed: bool = False, limit: int = 10) -> list[dict]:
        resp = await self._post(
            "/tasks/query",
            {"filter": {"is_completed": is_completed}, "limit": limit},
        )
        return resp.get("data", [])

    # ── Lists ────────────────────────────────────────────────────────────

    async def list_lists(self) -> list[dict]:
        resp = await self._get("/lists")
        return resp.get("data", [])
