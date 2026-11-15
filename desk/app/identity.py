"""DID documents, Ed25519 signing, and verification."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import canonicaljson
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .models import SignedEnvelope


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def load_private_key(path: str) -> Ed25519PrivateKey:
    data = Path(path).read_bytes()
    key = serialization.load_pem_private_key(data, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"Expected Ed25519 private key at {path}")
    return key


def load_did_document(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def public_jwk_from_private(private_key: Ed25519PrivateKey) -> dict[str, str]:
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "x": base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode("ascii"),
        "kid": "key-1",
    }


def build_did_document(
    did: str,
    public_base: str,
    private_key: Ed25519PrivateKey,
) -> dict[str, Any]:
    jwk = public_jwk_from_private(private_key)
    key_id = f"{did}#key-1"
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/jws-2020/v1",
        ],
        "id": did,
        "verificationMethod": [
            {
                "id": key_id,
                "type": "JsonWebKey2020",
                "controller": did,
                "publicKeyJwk": jwk,
            }
        ],
        "authentication": [key_id],
        "assertionMethod": [key_id],
        "service": [
            {
                "id": f"{did}#agent",
                "type": "AgentDescription",
                "serviceEndpoint": f"{public_base}/ad.json",
            }
        ],
    }


def canonical_bytes(obj: Any) -> bytes:
    return canonicaljson.encode_canonical_json(obj)


def body_digest(body: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_bytes(body)).digest()
    return "sha-256=" + base64.b64encode(digest).decode("ascii")


def quote_hash(quote_body: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_bytes(quote_body)).hexdigest()
    return "sha256:" + digest


def signing_string(method: str, url: str, timestamp: str, nonce: str, digest: str) -> bytes:
    # Sign the public https URL the peer will verify against.
    return f"{method.upper()}\n{url}\n{timestamp}\n{nonce}\n{digest}".encode("utf-8")


def sign_request(
    *,
    private_key: Ed25519PrivateKey,
    sender_did: str,
    method: str,
    url: str,
    body: dict[str, Any],
    key_id: str | None = None,
) -> SignedEnvelope:
    timestamp = utc_now_iso()
    nonce = secrets.token_urlsafe(16)
    digest = body_digest(body)
    message = signing_string(method, url, timestamp, nonce, digest)
    signature = base64.b64encode(private_key.sign(message)).decode("ascii")
    return SignedEnvelope(
        sender_did=sender_did,
        method=method.upper(),
        url=url,
        timestamp=timestamp,
        nonce=nonce,
        body=body,
        body_digest=digest,
        signature=signature,
        key_id=key_id or f"{sender_did}#key-1",
    )


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def public_key_from_did_doc(did_doc: dict[str, Any], key_id: str) -> Ed25519PublicKey:
    methods = did_doc.get("verificationMethod") or []
    match = None
    for method in methods:
        if method.get("id") == key_id or method.get("id", "").endswith("#key-1"):
            match = method
            break
    if match is None and methods:
        match = methods[0]
    if match is None:
        raise ValueError("DID document has no verificationMethod")
    jwk = match.get("publicKeyJwk") or {}
    if jwk.get("crv") != "Ed25519":
        raise ValueError("Only Ed25519 keys are supported")
    raw = _b64url_decode(jwk["x"])
    return Ed25519PublicKey.from_public_bytes(raw)


def did_document_url(did: str) -> str:
    # did:wba:buyer.test:agent -> https://buyer.test/.well-known/did.json
    parts = did.split(":")
    if len(parts) < 3 or parts[0] != "did" or parts[1] != "wba":
        raise ValueError(f"Unsupported DID: {did}")
    host = parts[2]
    return f"https://{host}/.well-known/did.json"


async def fetch_did_document(did: str, client: httpx.AsyncClient) -> dict[str, Any]:
    url = did_document_url(did)
    response = await client.get(url, timeout=10.0)
    response.raise_for_status()
    return response.json()


def parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


async def verify_envelope(
    envelope: SignedEnvelope,
    *,
    expected_url: str,
    expected_method: str,
    max_age_seconds: int,
    client: httpx.AsyncClient,
    nonce_store: Any,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Return (ok, reason, did_doc)."""
    if envelope.method.upper() != expected_method.upper():
        return False, "method mismatch", None
    if envelope.url.rstrip("/") != expected_url.rstrip("/"):
        return False, "url mismatch", None
    try:
        ts = parse_timestamp(envelope.timestamp)
    except ValueError:
        return False, "bad timestamp", None
    age = abs((utc_now() - ts).total_seconds())
    if age > max_age_seconds:
        return False, "signature expired", None
    if body_digest(envelope.body) != envelope.body_digest:
        return False, "body digest mismatch", None
    claimed = await nonce_store.claim(envelope.sender_did, envelope.nonce, max_age_seconds + 60)
    if not claimed:
        return False, "replayed nonce", None
    try:
        did_doc = await fetch_did_document(envelope.sender_did, client)
        public_key = public_key_from_did_doc(did_doc, envelope.key_id)
        message = signing_string(
            envelope.method,
            envelope.url,
            envelope.timestamp,
            envelope.nonce,
            envelope.body_digest,
        )
        public_key.verify(base64.b64decode(envelope.signature), message)
    except Exception as exc:  # noqa: BLE001 — map crypto/network to reason
        return False, f"signature check failed: {exc}", None
    return True, "signature verified", did_doc


def host_from_url(url: str) -> str:
    return urlparse(url).hostname or ""
