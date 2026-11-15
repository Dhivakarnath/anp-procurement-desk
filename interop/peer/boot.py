"""Start the upstream remote agent after teaching it to resolve the public demo DID locally.

didhost.cc currently serves HTML for /public/did.json, so the unmodified verifier cannot
fetch the public demo identity from the internet. Both this peer and the probe already
ship that same document on disk; we resolve it from there and leave every other DID to
the upstream resolver.
"""

from __future__ import annotations

import json
import runpy
from pathlib import Path

from anp.authentication import did_wba_verifier

PUBLIC_DID = Path(__file__).resolve().parent.parent / "docs" / "did_public" / "public-did-doc.json"
_upstream = did_wba_verifier.resolve_did_wba_document


async def resolve_did_wba_document(did: str):
    if did == "did:wba:didhost.cc:public" and PUBLIC_DID.exists():
        return json.loads(PUBLIC_DID.read_text())
    return await _upstream(did)


did_wba_verifier.resolve_did_wba_document = resolve_did_wba_document

runpy.run_path(str(Path(__file__).with_name("remote_agent.py")), run_name="__main__")
