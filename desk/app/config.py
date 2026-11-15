"""Runtime config from environment. No secrets are hard-coded."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    role: str
    public_base: str
    did: str
    key_path: str
    did_doc_path: str
    redis_url: str
    database_url: str
    market_url: str
    trust_proxy: bool
    quote_ttl_seconds: int
    signature_ttl_seconds: int
    haiku_model: str
    nova_model: str
    nova_fallback: str
    bedrock_region: str


def load_settings() -> Settings:
    role = os.environ.get("DESK_ROLE", "buyer").strip().lower()
    public_base = os.environ.get("PUBLIC_BASE", f"https://{role}.test").rstrip("/")
    return Settings(
        role=role,
        public_base=public_base,
        did=os.environ.get("AGENT_DID", f"did:wba:{role}.test:agent"),
        key_path=os.environ.get("KEY_PATH", f"/keys/{role}/private.pem"),
        did_doc_path=os.environ.get("DID_DOC_PATH", f"/keys/{role}/did.json"),
        redis_url=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        database_url=os.environ.get(
            "DATABASE_URL", f"postgresql://desk:desk@postgres:5432/{role}"
        ),
        market_url=os.environ.get("MARKET_URL", "https://market.test").rstrip("/"),
        trust_proxy=os.environ.get("TRUST_PROXY", "1") == "1",
        quote_ttl_seconds=int(os.environ.get("QUOTE_TTL_SECONDS", "900")),
        signature_ttl_seconds=int(os.environ.get("SIGNATURE_TTL_SECONDS", "300")),
        haiku_model=os.environ.get("HAIKU_MODEL", "us.anthropic.claude-haiku-5-5"),
        nova_model=os.environ.get("NOVA_MODEL", "us.amazon.nova-2-lite-v1:0"),
        nova_fallback=os.environ.get("NOVA_FALLBACK", "us.amazon.nova-lite-v1:0"),
        bedrock_region=os.environ.get("AWS_REGION", "us-east-1"),
    )
