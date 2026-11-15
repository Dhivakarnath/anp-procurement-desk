#!/usr/bin/env python3
"""Generate Ed25519 keys and DID documents for buyer, market, s1, s2, s3."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]

AGENTS = [
    ("buyer", "did:wba:buyer.test:agent", "https://buyer.test"),
    ("market", "did:wba:market.test:agent", "https://market.test"),
    ("s1", "did:wba:s1.test:agent", "https://s1.test"),
    ("s2", "did:wba:s2.test:agent", "https://s2.test"),
    ("s3", "did:wba:s3.test:agent", "https://s3.test"),
]


def public_jwk(private_key: Ed25519PrivateKey) -> dict[str, str]:
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


def build_did_document(did: str, public_base: str, private_key: Ed25519PrivateKey) -> dict:
    jwk = public_jwk(private_key)
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


def main() -> None:
    out = Path(os.environ.get("KEYS_DIR", ROOT / "keys"))
    out.mkdir(parents=True, exist_ok=True)
    for name, did, base in AGENTS:
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        pem_path = d / "private.pem"
        did_path = d / "did.json"
        if pem_path.exists():
            print(f"keep {pem_path}")
            key = serialization.load_pem_private_key(pem_path.read_bytes(), password=None)
            assert isinstance(key, Ed25519PrivateKey)
        else:
            key = Ed25519PrivateKey.generate()
            pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            pem_path.write_bytes(pem)
            os.chmod(pem_path, 0o600)
            print(f"wrote {pem_path}")
        doc = build_did_document(did, base, key)
        did_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        os.chmod(did_path, 0o644)
        print(f"wrote {did_path}")


if __name__ == "__main__":
    main()
