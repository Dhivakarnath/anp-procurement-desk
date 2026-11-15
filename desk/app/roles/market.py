"""Marketplace: match confirmed lines against published catalogs. No quote proxy."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..config import Settings
from ..identity import utc_now_iso
from ..redis_store import Ledger
from ..models import AgentDescription, CatalogOffer, MarketHit, RequestLines
from ..pricing import seed_s1, seed_s2, seed_s3

logger = logging.getLogger("desk.market")

router = APIRouter()


class SearchBody(BaseModel):
    lines: RequestLines


def _static_registry(settings: Settings, buyer_did: str) -> list[AgentDescription]:
    """Known supplier description endpoints on this desk (sample data)."""
    s1 = seed_s1(buyer_did, "did:wba:s1.test:agent")
    s2 = seed_s2("did:wba:s2.test:agent")
    s3 = seed_s3("did:wba:s3.test:agent")

    def to_ad(book, host: str, name: str) -> AgentDescription:
        return AgentDescription(
            did=book.supplier_did,
            name=name,
            public_url=f"https://{host}",
            description_url=f"https://{host}/ad.json",
            offers=[
                CatalogOffer(
                    sku=e.sku,
                    name=e.name,
                    description=e.description,
                    attributes=e.attributes,
                    sample_data=True,
                )
                for e in book.entries
            ],
            sample_data=True,
        )

    return [
        to_ad(s1, "s1.test", "S1"),
        to_ad(s2, "s2.test", "S2"),
        to_ad(s3, "s3.test", "S3"),
    ]


def match_offers(lines: RequestLines, agents: list[AgentDescription]) -> list[MarketHit]:
    needle = lines.part.strip().lower()
    hits: list[MarketHit] = []
    for agent in agents:
        for offer in agent.offers:
            hay = " ".join(
                [offer.sku, offer.name, offer.description, *offer.attributes.values()]
            ).lower()
            if needle and needle in hay:
                hits.append(
                    MarketHit(
                        did=agent.did,
                        name=agent.name,
                        public_url=agent.public_url,
                        description_url=agent.description_url,
                        matched_sku=offer.sku,
                        matched_name=offer.name,
                    )
                )
                break
    return hits


def build_market_app(settings: Settings) -> APIRouter:
    buyer_did = "did:wba:buyer.test:agent"

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"role": "market", "status": "ok"}

    @router.get("/.well-known/did.json")
    async def did_doc(request: Request) -> dict[str, Any]:
        return request.app.state.did_document

    @router.get("/ad.json")
    async def market_ad() -> dict[str, Any]:
        return {
            "name": "ANP Marketplace",
            "did": settings.did,
            "description": "Matches confirmed request lines to published supplier catalogs. Sample data.",
            "sample_data": True,
            "endpoints": {
                "search": f"{settings.public_base}/market/search",
            },
        }

    async def load_catalogs(request: Request) -> tuple[list[AgentDescription], dict[str, str]]:
        """Live ad.json from each supplier; static registry only when none answer."""
        agents: list[AgentDescription] = []
        sources: dict[str, str] = {}
        client: httpx.AsyncClient = request.app.state.http
        for host, name, did in [
            ("s1.test", "S1", "did:wba:s1.test:agent"),
            ("s2.test", "S2", "did:wba:s2.test:agent"),
            ("s3.test", "S3", "did:wba:s3.test:agent"),
        ]:
            url = f"https://{host}/ad.json"
            try:
                resp = await client.get(url, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    agents.append(
                        AgentDescription(
                            did=data.get("did", did),
                            name=data.get("name", name),
                            public_url=f"https://{host}",
                            description_url=url,
                            offers=[
                                CatalogOffer.model_validate(o)
                                for o in data.get("offers", [])
                            ],
                            sample_data=True,
                        )
                    )
                    sources[name] = "live"
                    continue
            except Exception:  # noqa: BLE001
                logger.info("live ad fetch failed for %s; using registry", host)
        if not agents:
            agents = _static_registry(settings, buyer_did)
            sources = {a.name: "registry" for a in agents}
        return agents, sources

    @router.post("/market/search")
    async def search(body: SearchBody, request: Request) -> dict[str, Any]:
        agents, sources = await load_catalogs(request)
        hits = match_offers(body.lines, agents)
        sentence = (
            f"Marketplace returned {len(hits)} supplier(s) for “{body.lines.part}”."
            if hits
            else f"No supplier publishes “{body.lines.part}” in the sample catalogs."
        )
        ledger: Ledger = request.app.state.ledger
        await ledger.append(
            {
                "type": "search",
                "at": utc_now_iso(),
                "part": body.lines.part,
                "quantity": body.lines.quantity,
                "catalogs_checked": [
                    {"name": a.name, "did": a.did, "source": sources.get(a.name, "registry")}
                    for a in agents
                ],
                "hits": [h.model_dump() for h in hits],
                "sentence": sentence,
            }
        )
        return {
            "query": body.lines.model_dump(),
            "hits": [h.model_dump() for h in hits],
            "sample_data": True,
            "sentence": sentence,
        }

    @router.get("/market/ledger")
    async def ledger_view(request: Request) -> dict[str, Any]:
        agents, sources = await load_catalogs(request)
        ledger: Ledger = request.app.state.ledger
        return {
            "role": "market",
            "name": "Marketplace",
            "did": settings.did,
            "public_base": settings.public_base,
            "role_line": "Matches confirmed request lines to published catalogs. Never sees prices.",
            "catalogs": [
                {
                    "name": a.name,
                    "did": a.did,
                    "description_url": a.description_url,
                    "source": sources.get(a.name, "registry"),
                    "offers": [o.model_dump() for o in a.offers],
                }
                for a in agents
            ],
            "entries": await ledger.recent(),
        }

    return router
