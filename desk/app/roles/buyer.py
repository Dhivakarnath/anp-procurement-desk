"""Buyer session: extract → confirm → search → quote → negotiate → rank → approve → order."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..bedrock import extract_request_lines, phrase_ranking
from ..config import Settings
from ..guard import inspect_reply, quarantined
from ..identity import quote_hash, sign_request, utc_now_iso, verify_envelope
from ..models import (
    ApproveBody,
    ConfirmBody,
    CounterOffer,
    MarketHit,
    NegotiateBody,
    OrderRequest,
    RequestLines,
    SessionState,
    SignedEnvelope,
    StoryEvent,
)
from ..negotiation import default_policy, live_offers, plan_counters, resolve_target, spec_answer
from ..ranking import rank_quotes
from ..redis_store import SessionStore

logger = logging.getLogger("desk.buyer")

router = APIRouter()

# Pause between negotiation steps so people watching can follow each round.
PACE_SECONDS = max(0, int(os.environ.get("NEGOTIATION_PACE_MS", "700"))) / 1000


class CreateSessionBody(BaseModel):
    text: str


def _event(mark: str, sentence: str, detail: dict[str, Any] | None = None) -> StoryEvent:
    return StoryEvent(
        id=str(uuid.uuid4()),
        at=utc_now_iso(),
        mark=mark,
        sentence=sentence,
        detail=detail or {},
    )


def build_buyer_app(settings: Settings) -> APIRouter:
    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"role": "buyer", "status": "ok", "did": settings.did}

    @router.get("/.well-known/did.json")
    async def did_doc(request: Request) -> dict[str, Any]:
        return request.app.state.did_document

    @router.get("/ad.json")
    async def ad() -> dict[str, Any]:
        return {
            "name": "Buyer",
            "did": settings.did,
            "description": "Procurement buyer. Discovers suppliers only via the marketplace.",
            "endpoints": {
                "sessions": f"{settings.public_base}/sessions",
            },
        }

    @router.post("/sessions")
    async def create_session(body: CreateSessionBody, request: Request) -> dict[str, Any]:
        store: SessionStore = request.app.state.sessions
        session_id = str(uuid.uuid4())
        lines, explanation, unavailable = extract_request_lines(
            body.text,
            region=settings.bedrock_region,
            model_id=settings.haiku_model,
        )
        assert lines is not None
        state = SessionState(
            session_id=session_id,
            status="awaiting_confirm",
            lines=lines,
            policy=default_policy(lines),
            confirmed=False,
            extract_unavailable=unavailable,
            events=[
                _event("buyer", "You typed a procurement request."),
                _event(
                    "buyer",
                    (
                        "Haiku could not be reached; showing heuristic lines for you to edit."
                        if unavailable
                        else "Haiku extracted request lines for your review."
                    ),
                    {
                        "lines": lines.model_dump(),
                        "explanation": explanation,
                        "explanation_unavailable": unavailable,
                    },
                ),
            ],
        )
        await store.save(state)
        return _session_view(state)

    @router.get("/sessions/{session_id}")
    async def get_session(session_id: str, request: Request) -> dict[str, Any]:
        state = await _load(request, session_id)
        return _session_view(state)

    @router.put("/sessions/{session_id}/lines")
    async def edit_lines(
        session_id: str, body: ConfirmBody, request: Request
    ) -> dict[str, Any]:
        store: SessionStore = request.app.state.sessions
        state = await _load(request, session_id)
        if state.confirmed:
            raise HTTPException(400, "lines already confirmed")
        state.lines = body.lines
        state.events.append(
            _event("buyer", "You edited the request lines.", {"lines": body.lines.model_dump()})
        )
        await store.save(state)
        return _session_view(state)

    @router.post("/sessions/{session_id}/confirm")
    async def confirm(session_id: str, body: ConfirmBody, request: Request) -> dict[str, Any]:
        store: SessionStore = request.app.state.sessions
        state = await _load(request, session_id)
        if state.confirmed:
            raise HTTPException(400, "already confirmed")
        state.lines = body.lines
        state.policy = body.policy or default_policy(body.lines)
        state.confirmed = True
        state.status = "searching"
        state.events.append(
            _event(
                "buyer",
                "You confirmed the lines. The buyer will search the marketplace.",
                {"lines": body.lines.model_dump(), "policy": state.policy.model_dump()},
            )
        )
        await store.save(state)

        # Search marketplace
        hits = await _market_search(request, body.lines)
        state.market_hits = hits
        state.events.append(
            _event(
                "market",
                (
                    f"Marketplace returned {len(hits)} supplier(s)."
                    if hits
                    else "Marketplace returned no matching suppliers."
                ),
                {"hits": [h.model_dump() for h in hits]},
            )
        )
        for hit in hits:
            state.events.append(
                _event(
                    hit.name.lower(),
                    f"Search found {hit.name} for {hit.matched_name} (sample data).",
                    hit.model_dump(),
                )
            )
            state.threads[hit.did] = {
                "supplier_did": hit.did,
                "supplier_name": hit.name,
                "public_url": hit.public_url,
                "description_url": hit.description_url,
                "matched_sku": hit.matched_sku,
                "replies": [],
                "latest": None,
            }

        if not hits:
            state.status = "no_suppliers"
            await store.save(state)
            return _session_view(state)

        state.status = "quoting"
        await store.save(state)

        # Fan out quotes in parallel
        await _fanout_quotes(request, state)
        await _rerank(request, state)
        await store.save(state)
        await asyncio.sleep(PACE_SECONDS)
        await _answer_from_spec(request, state)
        await _bargain(request, state)
        state.status = "ranked"
        await store.save(state)
        return _session_view(state)

    @router.post("/sessions/{session_id}/negotiate")
    async def negotiate(
        session_id: str, body: NegotiateBody, request: Request
    ) -> dict[str, Any]:
        store: SessionStore = request.app.state.sessions
        state = await _load(request, session_id)
        if not state.confirmed:
            raise HTTPException(400, "confirm lines first")
        thread = state.threads.get(body.supplier_did)
        if not thread:
            raise HTTPException(404, "supplier not in this session")

        state.events.append(
            _event(
                "buyer",
                f"You sent a counter to {thread['supplier_name']} only.",
                {"lines": body.lines.model_dump(), "supplier_did": body.supplier_did},
            )
        )
        await store.save(state)

        reply = await _request_quote(
            request,
            public_url=thread["public_url"],
            lines=body.lines,
            negotiation=True,
        )
        _apply_reply(state, body.supplier_did, reply)
        if state.lines is not None:
            state.lines.attributes.update({k: v for k, v in body.lines.attributes.items() if v})
        await _rerank(request, state)
        await store.save(state)
        await _bargain(request, state)
        state.status = "ranked"
        await store.save(state)
        return _session_view(state)

    @router.post("/sessions/{session_id}/approve")
    async def approve(
        session_id: str, body: ApproveBody, request: Request
    ) -> dict[str, Any]:
        store: SessionStore = request.app.state.sessions
        state = await _load(request, session_id)
        if state.status in {"searching", "quoting", "negotiating"}:
            raise HTTPException(409, "negotiation still running; approve after the final ranking")
        if not state.ranking or not state.ranking.winner:
            raise HTTPException(400, "no eligible quote to approve")
        winner = state.ranking.winner
        if body.quote_hash != winner.quote_hash or body.supplier_did != winner.supplier_did:
            raise HTTPException(400, "approve must match the exact ranked quote")

        state.approved_hash = body.quote_hash
        state.approved_supplier = body.supplier_did
        state.status = "approved"
        state.events.append(
            _event(
                "buyer",
                f"You approved the exact quote from {winner.supplier_name}.",
                {
                    "quote_hash": body.quote_hash,
                    "unit_price": winner.quote.unit_price,
                    "supplier_did": body.supplier_did,
                },
            )
        )
        await store.save(state)
        return _session_view(state)

    @router.post("/sessions/{session_id}/order")
    async def place_order(session_id: str, request: Request) -> dict[str, Any]:
        store: SessionStore = request.app.state.sessions
        state = await _load(request, session_id)
        if not state.approved_hash or not state.approved_supplier:
            raise HTTPException(400, "approve an exact quote before ordering")
        if not state.ranking or not state.ranking.winner:
            raise HTTPException(400, "no winner")
        winner = state.ranking.winner
        if winner.quote_hash != state.approved_hash:
            raise HTTPException(400, "approved quote no longer matches ranking")

        thread = state.threads[state.approved_supplier]
        order_id = str(uuid.uuid4())
        quote_body = winner.quote.model_dump(mode="json")
        oreq = OrderRequest(
            order_id=order_id,
            buyer_did=settings.did,
            quote_hash=state.approved_hash,
            quote=quote_body,
            approved_at=utc_now_iso(),
        )
        url = f"{thread['public_url'].rstrip('/')}/order"
        envelope = sign_request(
            private_key=request.app.state.private_key,
            sender_did=settings.did,
            method="POST",
            url=url,
            body=oreq.model_dump(mode="json"),
        )
        client: httpx.AsyncClient = request.app.state.http
        try:
            resp = await client.post(url, json=envelope.model_dump(), timeout=20.0)
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"order transport failed: {type(exc).__name__}") from exc

        result = data.get("envelope", {}).get("body") or data
        accepted = bool(result.get("accepted"))
        message = str(result.get("message") or ("accepted" if accepted else "refused"))
        from ..models import OrderResult

        state.order = OrderResult(accepted=accepted, order_id=order_id, message=message)
        state.status = "ordered" if accepted else "order_refused"
        state.events.append(
            _event(
                thread["supplier_name"].lower(),
                message,
                {"accepted": accepted, "order_id": order_id},
            )
        )
        await store.save(state)
        return _session_view(state)

    return router


async def _load(request: Request, session_id: str) -> SessionState:
    store: SessionStore = request.app.state.sessions
    state = await store.get(session_id)
    if not state:
        raise HTTPException(404, "session not found")
    return state


def _session_view(state: SessionState) -> dict[str, Any]:
    return state.model_dump(mode="json")


async def _market_search(request: Request, lines: RequestLines) -> list[MarketHit]:
    settings: Settings = request.app.state.settings
    client: httpx.AsyncClient = request.app.state.http
    url = f"{settings.market_url}/market/search"
    try:
        resp = await client.post(url, json={"lines": lines.model_dump()}, timeout=15.0)
        data = resp.json()
        return [MarketHit.model_validate(h) for h in data.get("hits", [])]
    except Exception as exc:  # noqa: BLE001
        logger.warning("market search failed: %s", type(exc).__name__)
        return []


async def _fanout_quotes(request: Request, state: SessionState) -> None:
    assert state.lines is not None
    tasks = []
    dids = list(state.threads.keys())
    for did in dids:
        thread = state.threads[did]
        tasks.append(_request_quote(request, thread["public_url"], state.lines, False))
    state.status = "quoting"
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for did, result in zip(dids, results, strict=True):
        if isinstance(result, Exception):
            _apply_reply(
                state,
                did,
                {
                    "ok": False,
                    "reason": f"transport error: {type(result).__name__}",
                    "payload": None,
                    "kind": None,
                    "signature_verified": False,
                    "quote_hash": None,
                    "check": {},
                },
            )
        else:
            _apply_reply(state, did, result)


async def _request_quote(
    request: Request,
    public_url: str,
    lines: RequestLines,
    negotiation: bool,
    counter: CounterOffer | None = None,
) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    client: httpx.AsyncClient = request.app.state.http
    url = f"{public_url.rstrip('/')}/quote"
    body = {
        "request_id": str(uuid.uuid4()),
        "buyer_did": settings.did,
        "lines": lines.model_dump(),
        "negotiation": negotiation,
        "counter": counter.model_dump() if counter else None,
    }
    envelope = sign_request(
        private_key=request.app.state.private_key,
        sender_did=settings.did,
        method="POST",
        url=url,
        body=body,
    )
    sent = {
        "request_id": body["request_id"],
        "url": url,
        "lines": body["lines"],
        "negotiation": negotiation,
        "counter": body["counter"],
        "nonce": envelope.nonce,
        "timestamp": envelope.timestamp,
        "body_digest": envelope.body_digest,
    }
    try:
        resp = await client.post(url, json=envelope.model_dump(), timeout=25.0)
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "reason": f"transport error: {type(exc).__name__}",
            "payload": None,
            "kind": None,
            "signature_verified": False,
            "quote_hash": None,
            "check": {},
            "request": sent,
        }

    env_data = data.get("envelope")
    if not env_data:
        return {
            "ok": False,
            "reason": "missing envelope",
            "payload": None,
            "kind": None,
            "signature_verified": False,
            "quote_hash": None,
            "check": data.get("check") or {},
            "request": sent,
        }

    signed = SignedEnvelope.model_validate(env_data)
    # Verify against the supplier's response URL they signed.
    ok, reason, did_doc = await verify_envelope(
        signed,
        expected_url=signed.url,
        expected_method="POST",
        max_age_seconds=settings.signature_ttl_seconds,
        client=client,
        nonce_store=request.app.state.nonce_store,
    )
    payload = signed.body
    kind = payload.get("kind")
    qhash = quote_hash(payload) if kind == "quote" else None
    return {
        "ok": ok,
        "reason": reason,
        "payload": payload,
        "guard": (
            inspect_reply(
                payload,
                own_numbers=(counter.target_unit_price,) if counter else (),
            )
            if ok
            else []
        ),
        "kind": kind,
        "signature_verified": ok,
        "quote_hash": qhash,
        "sender_did": signed.sender_did,
        "did_doc": did_doc,
        "check": {
            "signature": reason,
            "quote_hash": qhash,
            "discovery_url": f"{public_url.rstrip('/')}/ad.json",
            "certificate_host": public_url,
            "recovered_did": signed.sender_did if ok else None,
            "reply_nonce": signed.nonce,
            "reply_timestamp": signed.timestamp,
        },
        "request": sent,
    }


def _apply_reply(state: SessionState, supplier_did: str, reply: dict[str, Any]) -> None:
    thread = state.threads[supplier_did]
    name = thread["supplier_name"]
    mark = name.lower()
    payload = reply.get("payload")
    kind = reply.get("kind")
    sentence = "No reply."
    if not reply.get("ok"):
        sentence = f"{name}: signature or transport failed ({reply.get('reason')})."
    elif kind == "quote" and payload and payload.get("round"):
        prev = payload.get("previous_unit_price")
        moved = prev is not None and payload["unit_price"] < prev
        sentence = (
            f"{name} round {payload['round']}: "
            + (
                f"came down from ${prev:.2f} to ${payload['unit_price']:.2f}"
                if moved
                else f"held at ${payload['unit_price']:.2f}"
            )
            + (" (best and final)." if payload.get("final_offer") else ".")
        )
    elif kind == "quote" and payload:
        basis = payload.get("price_basis", "list")
        sentence = (
            f"{name} offered a {basis} price of ${payload['unit_price']:.2f} "
            f"with {payload['lead_time_days']}-day lead time"
            f"{' (expedited)' if payload.get('delivery') == 'expedited' else ''}."
        )
    elif kind == "refusal" and payload:
        sentence = (
            f"{name} cannot meet the date "
            f"(lead {payload.get('lead_time_days')} days vs need-by "
            f"{payload.get('need_by_days')}). {payload.get('phrasing') or ''}"
        ).strip()
    elif kind == "question" and payload:
        sentence = (
            f"{name} asked for {payload.get('missing_attribute')} before pricing. "
            f"{payload.get('phrasing') or ''}"
        ).strip()

    record = {
        "at": utc_now_iso(),
        "kind": kind,
        "payload": payload,
        "signature_verified": reply.get("signature_verified"),
        "quote_hash": reply.get("quote_hash"),
        "check": reply.get("check") or {},
        "sentence": sentence,
        "request": reply.get("request"),
        "guard": reply.get("guard") or [],
    }
    thread["replies"].append(record)
    thread["latest"] = record
    # Prefer DID recovered from signature when verified.
    if reply.get("signature_verified") and reply.get("sender_did"):
        thread["recovered_did"] = reply["sender_did"]

    state.events.append(_event(mark, sentence, {"check": record["check"], "kind": kind}))
    if record["guard"]:
        state.events.append(
            _event(
                "buyer",
                f"Ignored untrusted text from {name}: "
                + "; ".join(sorted({f["reason"] for f in record["guard"]}))
                + (
                    f". {name} is quarantined: no more counters, not eligible for the award."
                    if quarantined(thread)
                    else ". Decisions use only the signed fields."
                ),
                {"guard": record["guard"], "supplier_did": supplier_did},
            )
        )


async def _rerank(request: Request, state: SessionState) -> None:
    settings: Settings = request.app.state.settings
    candidates = []
    for did, thread in state.threads.items():
        latest = thread.get("latest") or {}
        candidates.append(
            {
                "supplier_did": did,
                "supplier_name": thread["supplier_name"],
                "payload": latest.get("payload"),
                "kind": latest.get("kind"),
                "signature_verified": bool(latest.get("signature_verified")),
                "quarantined": quarantined(thread),
            }
        )
    ranking = rank_quotes(candidates, max_unit_price=state.policy.walk_away_unit_price)
    expl, modeled = phrase_ranking(
        ranking, region=settings.bedrock_region, model_id=settings.haiku_model
    )
    ranking = ranking.model_copy(
        update={
            "explanation": expl if expl else "explanation unavailable",
            "explanation_unavailable": not modeled,
        }
    )
    state.ranking = ranking
    sentence = ranking.explanation
    if ranking.explanation_unavailable:
        sentence = f"{ranking.explanation} (explanation unavailable from the model)."
    state.events.append(
        _event(
            "buyer",
            sentence,
            {
                "winner": ranking.winner.supplier_name if ranking.winner else None,
                "quote_hash": ranking.winner.quote_hash if ranking.winner else None,
                "eligible": len(ranking.eligible),
            },
        )
    )


async def _answer_from_spec(request: Request, state: SessionState) -> None:
    """Answer supplier questions the buyer's spec sheet already covers."""
    assert state.lines is not None
    jobs: list[tuple[str, Any]] = []
    lines = state.lines
    for did, thread in state.threads.items():
        latest = thread.get("latest") or {}
        payload = latest.get("payload") or {}
        if latest.get("kind") != "question" or not latest.get("signature_verified"):
            continue
        attr = str(payload.get("missing_attribute") or "")
        if not attr or attr == "part":
            continue
        answer = spec_answer(lines, attr)
        if not answer:
            continue
        if attr not in state.spec_answers:
            state.spec_answers[attr] = answer
            state.events.append(
                _event(
                    "buyer",
                    f"Answered {attr}: {answer} from the buyer's spec sheet.",
                    {"spec_answer": {attr: answer}},
                )
            )
        lines = lines.model_copy(update={"attributes": {**lines.attributes, attr: answer}})
        jobs.append((did, thread))
    if not jobs:
        return
    state.lines = lines
    results = await asyncio.gather(
        *[_request_quote(request, t["public_url"], lines, True) for _, t in jobs],
        return_exceptions=True,
    )
    for (did, _), result in zip(jobs, results, strict=True):
        _apply_reply(state, did, _transport_failure(result) if isinstance(result, Exception) else result)
    await _rerank(request, state)
    await request.app.state.sessions.save(state)


async def _bargain(request: Request, state: SessionState) -> None:
    """Autonomous counter-offer rounds within the buyer's private limits."""
    if state.lines is None or any(
        (t.get("latest") or {}).get("kind") == "question" for t in state.threads.values()
    ):
        return
    target = resolve_target(state.policy, live_offers(state.threads))
    if target is None or state.policy.max_rounds == 0:
        return
    if state.policy.target_unit_price is None:
        state.policy = state.policy.model_copy(update={"target_unit_price": target})
        state.events.append(
            _event(
                "buyer",
                f"No target set; asking ${target:.2f}, 8% below the best opening offer.",
                {"target": target},
            )
        )
    for round_no in range(state.round + 1, state.round + 1 + state.policy.max_rounds):
        plan = plan_counters(state.threads, target=target, round_no=round_no)
        if not plan:
            break
        await asyncio.sleep(PACE_SECONDS)
        state.round = round_no
        state.status = "negotiating"
        state.events.append(
            _event(
                "buyer",
                f"Round {round_no}: countered {len(plan)} supplier(s) at ${target:.2f}.",
                {"round": round_no, "target": target},
            )
        )
        results = await asyncio.gather(
            *[
                _request_quote(
                    request, state.threads[did]["public_url"], state.lines, True, counter=counter
                )
                for did, counter in plan
            ],
            return_exceptions=True,
        )
        for (did, _), result in zip(plan, results, strict=True):
            _apply_reply(
                state, did, _transport_failure(result) if isinstance(result, Exception) else result
            )
        await _rerank(request, state)
        await request.app.state.sessions.save(state)


def _transport_failure(exc: BaseException) -> dict[str, Any]:
    return {
        "ok": False,
        "reason": f"transport error: {type(exc).__name__}",
        "payload": None,
        "kind": None,
        "signature_verified": False,
        "quote_hash": None,
        "check": {},
    }
