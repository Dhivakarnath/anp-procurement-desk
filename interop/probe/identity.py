"""The probe's own did:wba identity and the private TLS authority that serves it.

Generated on first start into the probe's data volume; never written to the repository.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass
from pathlib import Path

from anp.authentication import create_did_wba_document
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

DID_HOST = os.environ.get("DID_HOST", "desk.interop.test")
DID_PATH = ["agents", "procurement-desk"]


@dataclass(frozen=True)
class Identity:
    did: str
    did_url: str
    did_path: str
    document: Path
    private_key: Path
    tls_cert: Path
    tls_key: Path
    ca_cert: Path


def _name(common: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common)])


def _write_tls(dir_: Path, trust_dir: Path) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca = (
        x509.CertificateBuilder()
        .subject_name(_name("ANP interop demo CA"))
        .issuer_name(_name("ANP interop demo CA"))
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=825))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(DID_HOST))
        .issuer_name(ca.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(DID_HOST)]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    pem = serialization.Encoding.PEM
    (dir_ / "tls.key").write_bytes(
        key.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    (dir_ / "tls.crt").write_bytes(cert.public_bytes(pem))
    (dir_ / "ca.crt").write_bytes(ca.public_bytes(pem))
    trust_dir.mkdir(parents=True, exist_ok=True)
    (trust_dir / "ca.crt").write_bytes(ca.public_bytes(pem))


def ensure_identity(data_dir: Path, trust_dir: Path) -> Identity:
    dir_ = data_dir / "identity"
    doc_path = dir_ / "did.json"
    if not doc_path.exists():
        dir_.mkdir(parents=True, exist_ok=True)
        # plain_legacy + secp256k1 JWK: the profile the anp 0.4.4 verifier understands.
        doc, keys = create_did_wba_document(
            hostname=DID_HOST,
            path_segments=DID_PATH,
            enable_e2ee=False,
            did_profile="plain_legacy",
        )
        private_pem = next(iter(keys.values()))[0]
        (dir_ / "private.pem").write_bytes(private_pem)
        os.chmod(dir_ / "private.pem", 0o600)
        doc_path.write_text(json.dumps(doc, indent=2))
        _write_tls(dir_, trust_dir)
    elif not (trust_dir / "ca.crt").exists():
        trust_dir.mkdir(parents=True, exist_ok=True)
        (trust_dir / "ca.crt").write_bytes((dir_ / "ca.crt").read_bytes())
    did = json.loads(doc_path.read_text())["id"]
    path = "/" + "/".join(did.split(":")[3:]) + "/did.json"
    return Identity(
        did=did,
        did_url=f"https://{DID_HOST}{path}",
        did_path=path,
        document=doc_path,
        private_key=dir_ / "private.pem",
        tls_cert=dir_ / "tls.crt",
        tls_key=dir_ / "tls.key",
        ca_cert=dir_ / "ca.crt",
    )
