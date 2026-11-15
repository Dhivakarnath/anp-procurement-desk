"""Redis helpers: nonce replay protection and buyer session storage."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from .models import SessionState


class NonceStore:
    def __init__(self, client: redis.Redis, prefix: str = "nonce") -> None:
        self.client = client
        self.prefix = prefix

    async def claim(self, sender_did: str, nonce: str, ttl_seconds: int) -> bool:
        key = f"{self.prefix}:{sender_did}:{nonce}"
        # SET NX — first claim wins; later claims are replays.
        ok = await self.client.set(key, "1", nx=True, ex=max(ttl_seconds, 60))
        return bool(ok)


class SessionStore:
    def __init__(self, client: redis.Redis, prefix: str = "session") -> None:
        self.client = client
        self.prefix = prefix

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}:{session_id}"

    async def save(self, state: SessionState, ttl_seconds: int = 3600) -> None:
        payload = state.model_dump(mode="json")
        await self.client.set(
            self._key(state.session_id),
            json.dumps(payload),
            ex=ttl_seconds,
        )

    async def get(self, session_id: str) -> SessionState | None:
        raw = await self.client.get(self._key(session_id))
        if not raw:
            return None
        data = json.loads(raw)
        return SessionState.model_validate(data)

    async def update(self, state: SessionState, ttl_seconds: int = 3600) -> SessionState:
        await self.save(state, ttl_seconds=ttl_seconds)
        return state


def create_redis(url: str) -> redis.Redis:
    return redis.from_url(url, decode_responses=True)


async def ping_redis(client: redis.Redis) -> bool:
    try:
        return bool(await client.ping())
    except Exception:  # noqa: BLE001
        return False


class Ledger:
    """Recent messages one party handled, newest first. Read by that party's own view."""

    def __init__(self, client: redis.Redis, role: str, keep: int = 200) -> None:
        self.client = client
        self.key = f"ledger:{role}"
        self.keep = keep

    async def append(self, entry: dict[str, Any]) -> None:
        await self.client.lpush(self.key, json.dumps(entry))
        await self.client.ltrim(self.key, 0, self.keep - 1)

    async def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        raw = await self.client.lrange(self.key, 0, limit - 1)
        return [json.loads(r) for r in raw]


# Optional small KV for supplier quote archives
class QuoteArchive:
    def __init__(self, client: redis.Redis, prefix: str) -> None:
        self.client = client
        self.prefix = prefix

    async def put(self, quote_hash: str, body: dict[str, Any], ttl: int = 3600) -> None:
        await self.client.set(
            f"{self.prefix}:quote:{quote_hash}",
            json.dumps(body),
            ex=ttl,
        )

    async def get(self, quote_hash: str) -> dict[str, Any] | None:
        raw = await self.client.get(f"{self.prefix}:quote:{quote_hash}")
        return json.loads(raw) if raw else None
