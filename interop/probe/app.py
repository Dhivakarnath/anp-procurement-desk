"""Interop probe: talks to ANP agents we do not control, using only the official ANP SDK.

Everything a remote agent returns is untrusted. It is size-capped and returned as data
for display; nothing here feeds a model, a price, or the procurement desk.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from yarl import URL

PEER_HOST = os.environ.get("PEER_HOST", "172.30.0.10")
PEER_AD_URL = f"http://{PEER_HOST}:8000/agents/test/ad.json"
PUBLIC_AD_URL = "https://agent-connect.ai/mcp/agents/amap/ad.json"
DID_URL = "https://didhost.cc/public/did.json"
IDENTITY_DIR = Path(os.environ.get("IDENTITY_DIR", "/identity"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
WEB_ORIGIN = os.environ.get("WEB_ORIGIN", "http://localhost:8080")

ALLOWED_HTTPS = {"agent-connect.ai", "didhost.cc"}
MAX_BODY = 512 * 1024
RUN_TIMEOUT = 45.0
COOLDOWN = 3.0

# The SDK's crawler follows URLs it finds inside remote documents. Every request it makes
# goes through this guard: only the peer (plain HTTP on the private network) and the
# allow-listed public hosts, no redirects, bounded bodies.
_original_request = aiohttp.ClientSession._request


async def _guarded_request(self, method, str_or_url, *args, **kwargs):
    url = URL(str(str_or_url))
    if url.scheme == "https" and url.host == PEER_HOST:
        # The example agent always advertises https; on the private network it serves http.
        url = url.with_scheme("http")
        str_or_url = url
    allowed = (url.scheme == "http" and url.host == PEER_HOST) or (
        url.scheme == "https" and url.host in ALLOWED_HTTPS
    )
    if not allowed:
        raise aiohttp.ClientError(f"blocked by probe allow-list: {url.scheme}://{url.host}")
    kwargs["allow_redirects"] = False
    response = await _original_request(self, method, str_or_url, *args, **kwargs)
    if response.content_length is not None and response.content_length > MAX_BODY:
        response.close()
        raise aiohttp.ClientError("response larger than the probe allows")
    return response


aiohttp.ClientSession._request = _guarded_request

from anp.anp_crawler.anp_crawler import ANPCrawler  # noqa: E402  (after the guard)

app = FastAPI(title="ANP interop probe")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[WEB_ORIGIN],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_lock = asyncio.Lock()
_last_started = 0.0


class RunBody(BaseModel):
    target: Literal["peer", "public"] = "peer"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clip(value: Any, depth: int = 0) -> Any:
    """Bound untrusted data before it is stored or displayed."""
    if depth > 5:
        return "…"
    if isinstance(value, str):
        return value if len(value) <= 600 else value[:600] + "…"
    if isinstance(value, list):
        return [_clip(v, depth + 1) for v in value[:20]]
    if isinstance(value, dict):
        return {str(k)[:60]: _clip(v, depth + 1) for k, v in list(value.items())[:30]}
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _clip(str(value), depth)


def _identity() -> dict[str, Any]:
    doc = json.loads((IDENTITY_DIR / "public-did-doc.json").read_text())
    method = (doc.get("verificationMethod") or [{}])[0]
    return {
        "did": doc.get("id"),
        "key_type": method.get("type"),
        "curve": (method.get("publicKeyJwk") or {}).get("crv"),
        "verification_method": method.get("id"),
        "did_url": DID_URL,
        "document": doc,
    }


class Recorder:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []

    async def step(self, sid: str, title: str, work):
        started = time.perf_counter()
        try:
            ok, detail, data = await work()
        except Exception as exc:  # noqa: BLE001 — a failed step is a result, not a crash
            ok, detail, data = False, f"{type(exc).__name__}: {str(exc)[:200]}", None
        self.steps.append(
            {
                "id": sid,
                "title": title,
                "ok": ok,
                "detail": _clip(detail),
                "ms": round((time.perf_counter() - started) * 1000),
            }
        )
        return ok, data


def _unwrap(result: Any) -> Any:
    if isinstance(result, dict) and isinstance(result.get("result"), (dict, list, str, int, float, bool)):
        return result["result"]
    return result


async def _run(target: str) -> dict[str, Any]:
    ad_url = PEER_AD_URL if target == "peer" else PUBLIC_AD_URL
    ours = _identity()
    rec = Recorder()
    out: dict[str, Any] = {
        "run_id": str(uuid.uuid4()),
        "target": target,
        "ad_url": ad_url,
        "started_at": _now(),
        "sdk": {"client": f"anp {importlib.metadata.version('anp')}"},
        "us": {k: v for k, v in ours.items() if k != "document"},
        "them": None,
        "tools": [],
        "exchanges": [],
        "proof": {},
    }

    async def load():
        return True, f"{ours['did']} ({ours['key_type']})", None

    await rec.step("identity", "Load our ANP identity", load)

    async def resolve():
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as http:
            async with http.get(DID_URL) as resp:
                body = await resp.text()
        try:
            published = json.loads(body)
        except json.JSONDecodeError:
            # didhost.cc sometimes serves an HTML shell instead of the DID document.
            # The peer still verifies against the public key we carry locally.
            return True, (
                "didhost.cc did not return JSON for the public DID; "
                "continuing with the local public demo identity."
            ), None
        same = published.get("id") == ours["did"] and published.get(
            "verificationMethod"
        ) == ours["document"].get("verificationMethod")
        return same, (
            "Published document matches our key, so any agent can verify our signatures."
            if same
            else "Published document does not match our local key."
        ), None

    await rec.step("resolve", "Resolve our identity on the public web", resolve)

    crawler = ANPCrawler(
        did_document_path=str(IDENTITY_DIR / "public-did-doc.json"),
        private_key_path=str(IDENTITY_DIR / "public-private-key.pem"),
        cache_enabled=False,
    )
    # anp 0.4.4 (matched to the example agent) always uses legacy DIDWba headers.
    auth = getattr(crawler._client, "auth_client", None)
    if auth is not None and hasattr(auth, "auth_mode"):
        auth.auth_mode = "legacy_didwba" if target == "peer" else "http_signatures"
        out["sdk"]["auth_mode"] = auth.auth_mode
    else:
        out["sdk"]["auth_mode"] = "legacy_didwba"

    async def discover():
        content, _ = await crawler.fetch_text(ad_url)
        raw = content.get("content") if isinstance(content, dict) else None
        if not isinstance(raw, str) or raw.startswith("Error:"):
            return False, (raw or "No agent description returned")[:200], None
        ad = json.loads(raw)
        out["them"] = _clip(
            {
                "name": ad.get("name"),
                "did": ad.get("did"),
                "description": ad.get("description"),
                "protocol_version": ad.get("protocolVersion") or ad.get("protocol_version"),
                "owner": (ad.get("owner") or {}).get("name") if isinstance(ad.get("owner"), dict) else None,
                "interfaces": len(ad.get("interfaces") or []),
            }
        )
        return True, f"{ad.get('name')} · {ad.get('did')}", ad

    ok, _ = await rec.step("discover", "Fetch and parse their agent description", discover)
    if not ok:
        return _finish(out, rec)

    async def interfaces():
        names = crawler.list_available_tools()
        tools = []
        for name in names[:20]:
            info = crawler.get_tool_interface_info(name) or {}
            data = info.get("interface_data") or {}
            servers = info.get("servers") or [{}]
            tools.append(
                {
                    "name": name,
                    "description": data.get("summary") or data.get("description"),
                    "params": [p.get("name") for p in data.get("params") or []][:8],
                    "endpoint": servers[0].get("url"),
                }
            )
        out["tools"] = _clip(tools)
        return bool(names), f"{len(names)} callable interface(s): {', '.join(names[:6])}", names

    ok, names = await rec.step("interfaces", "Read their interface documents", interfaces)
    if not ok:
        return _finish(out, rec)

    if target == "peer":
        # FastANP advertises https:// even for plain-HTTP peers. Sign and call over
        # the same scheme the peer actually serves, or the signature will not verify.
        _force_http_peer_urls(crawler)

    calls: list[tuple[str, str, dict[str, Any]]] = []
    if target == "peer":
        calls = [
            ("greet", "Call greet (requires DID-WBA login)", {"params": {"name": "ANP Procurement Desk"}}),
            ("echo", "Call echo", {"params": {"message": "RFQ-ready: 300 × shaft seal 45mm"}}),
        ]
    else:
        search = next((n for n in names if "search" in n.lower() or "poi" in n.lower()), None)
        if search:
            calls = [(search, f"Call {search}", {"keywords": "coffee", "city": "Beijing"})]

    for tool, title, args in calls:

        async def call(tool=tool, args=args):
            result = await crawler.execute_tool_call(tool, args)
            body = _unwrap(result)
            out["exchanges"].append({"tool": tool, "request": _clip(args), "response": _clip(body)})
            failed = isinstance(result, dict) and result.get("success") is False
            if failed:
                return False, str(result.get("error") or "call failed")[:300], None
            if tool == "greet" and isinstance(body, dict):
                seen = body.get("did")
                matched = seen == ours["did"]
                out["proof"] = {"peer_saw_did": seen, "matches_ours": matched}
                return (
                    matched,
                    (
                        f"Peer verified our signature and saw {seen}"
                        if matched
                        else f"Peer answered but DID mismatch: {seen}"
                    ),
                    None,
                )
            return True, json.dumps(_clip(body), ensure_ascii=False)[:300], None

        await rec.step(f"call:{tool}", title, call)

    return _finish(out, rec)


def _force_http_peer_urls(crawler: Any) -> None:
    https_prefix = f"https://{PEER_HOST}"
    http_prefix = f"http://{PEER_HOST}"
    for interface in getattr(crawler, "_anp_interfaces", {}).values():
        servers = getattr(interface, "servers", None) or []
        for server in servers:
            url = server.get("url") or ""
            if url.startswith(https_prefix):
                server["url"] = http_prefix + url[len(https_prefix) :]


def _finish(out: dict[str, Any], rec: Recorder) -> dict[str, Any]:
    out["steps"] = rec.steps
    out["finished_at"] = _now()
    # A successful demo needs discovery plus at least one authenticated call.
    critical = {"identity", "discover", "interfaces"} | {
        s["id"] for s in rec.steps if s["id"].startswith("call:")
    }
    calls = [s for s in rec.steps if s["id"].startswith("call:")]
    out["ok"] = (
        bool(rec.steps)
        and all(s["ok"] for s in rec.steps if s["id"] in critical and not s["id"].startswith("call:"))
        and bool(calls)
        and any(s["ok"] for s in calls)
    )
    return out


def _last_path(target: str) -> Path:
    return DATA_DIR / f"last-{target}.json"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/probe/last")
async def last(target: Literal["peer", "public"] = "peer") -> dict[str, Any]:
    path = _last_path(target)
    if path.exists():
        return {**json.loads(path.read_text()), "recorded": True}
    fallback = Path(__file__).resolve().parent / "fallback" / f"last-{target}.json"
    if fallback.exists():
        return {**json.loads(fallback.read_text()), "recorded": True, "fallback": True}
    raise HTTPException(404, "no recorded run yet")


@app.post("/probe/run")
async def run(body: RunBody) -> dict[str, Any]:
    global _last_started
    if _lock.locked() or time.monotonic() - _last_started < COOLDOWN:
        raise HTTPException(429, "a run just happened; try again in a few seconds")
    async with _lock:
        _last_started = time.monotonic()
        try:
            result = await asyncio.wait_for(_run(body.target), timeout=RUN_TIMEOUT)
        except asyncio.TimeoutError:
            raise HTTPException(504, "the remote agent took too long") from None
    if result["ok"]:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _last_path(body.target).write_text(json.dumps(result))
    return {**result, "recorded": False}
