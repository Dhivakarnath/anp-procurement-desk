"""Single FastAPI entry. Role selected by DESK_ROLE."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import load_settings
from .db import init_schema
from .identity import build_did_document, load_did_document, load_private_key
from .redis_store import Ledger, NonceStore, QuoteArchive, SessionStore, create_redis
from .roles.buyer import build_buyer_app
from .roles.market import build_market_app
from .roles.supplier import build_supplier_app, seed_supplier_data

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
# Never log authorization headers, signatures, or tokens.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("desk")


class RedactingFilter(logging.Filter):
    BLOCK = ("signature", "authorization", "token", "private", "secret", "api_key")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage().lower()
        return not any(b in msg for b in self.BLOCK)


logger.addFilter(RedactingFilter())


def create_app() -> FastAPI:
    settings = load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        redis = create_redis(settings.redis_url)
        app.state.redis = redis
        app.state.nonce_store = NonceStore(redis, prefix=f"nonce:{settings.role}")
        app.state.sessions = SessionStore(redis, prefix="buyer:session")
        app.state.quote_archive = QuoteArchive(redis, prefix=f"quotes:{settings.role}")
        app.state.ledger = Ledger(redis, settings.role)
        app.state.settings = settings

        key_path = Path(settings.key_path)
        if key_path.exists():
            app.state.private_key = load_private_key(str(key_path))
        else:
            # Dev fallback: generate ephemeral key (Docker mounts real keys).
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            logger.warning("KEY_PATH missing; using ephemeral key for %s", settings.role)
            app.state.private_key = Ed25519PrivateKey.generate()

        did_path = Path(settings.did_doc_path)
        if did_path.exists():
            app.state.did_document = load_did_document(str(did_path))
        else:
            app.state.did_document = build_did_document(
                settings.did, settings.public_base, app.state.private_key
            )

        # httpx client that talks to sibling https hosts (Caddy).
        # verify uses system CA + mounted local CA when provided.
        ca_bundle = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
        verify: Any = ca_bundle if ca_bundle and Path(ca_bundle).exists() else True
        if os.environ.get("SSL_INSECURE", "0") == "1":
            verify = False
        app.state.http = httpx.AsyncClient(verify=verify, follow_redirects=True)

        init_schema(settings.database_url, settings.role)
        seed_supplier_data(settings)
        logger.info("started role=%s did=%s", settings.role, settings.did)
        yield
        await app.state.http.aclose()
        await redis.aclose()

    app = FastAPI(title=f"ANP desk ({settings.role})", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://app.test",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def trust_proxy(request: Request, call_next):
        # Trust X-Forwarded-* only when behind Caddy (TRUST_PROXY=1).
        if settings.trust_proxy:
            proto = request.headers.get("x-forwarded-proto")
            host = request.headers.get("x-forwarded-host")
            if proto or host:
                # Stash for handlers that need public URL reconstruction.
                request.state.forwarded_proto = proto or "https"
                request.state.forwarded_host = host
        response: Response = await call_next(request)
        return response

    if settings.role == "market":
        app.include_router(build_market_app(settings))
    elif settings.role == "buyer":
        app.include_router(build_buyer_app(settings))
    elif settings.role in {"s1", "s2", "s3"}:
        app.include_router(build_supplier_app(settings))
    else:
        raise RuntimeError(f"Unknown DESK_ROLE={settings.role}")

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"role": settings.role, "did": settings.did}

    return app


app = create_app()
