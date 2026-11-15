"""Shared schemas: request lines, quotes, ranking, agent descriptions."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# Values that steer pricing must be short catalog-style tokens, never prose.
_TOKEN = re.compile(r"^[A-Za-z0-9 ._/+×\-]{1,40}$")
_KEY = re.compile(r"^[a-z][a-z0-9_ ]{0,29}$")


class ReplyKind(str, Enum):
    quote = "quote"
    refusal = "refusal"
    question = "question"


class RequestLines(BaseModel):
    part: str = Field(min_length=1, max_length=80)
    quantity: int = Field(ge=1, le=10_000_000)
    need_by_days: int = Field(ge=1, le=365)
    attributes: dict[str, str] = Field(default_factory=dict)
    # Free text. Shown to people, never used for a decision or put in a model prompt.
    notes: str = Field(default="", max_length=500)

    @field_validator("attributes")
    @classmethod
    def _tokens_only(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 8:
            raise ValueError("at most 8 attributes")
        clean: dict[str, str] = {}
        for key, val in value.items():
            k = key.strip().lower()
            v = val.strip()
            if not _KEY.match(k):
                raise ValueError(f"attribute name {key!r} must be a short lowercase word")
            if v and not _TOKEN.match(v):
                raise ValueError(f"attribute {k} must be a short value like FKM or M8x40")
            clean[k] = v
        return clean


class BuyerPolicy(BaseModel):
    """Buyer-private limits. The target is sent as an ask; the walk-away never leaves the buyer."""

    target_unit_price: float | None = Field(default=None, gt=0)
    walk_away_unit_price: float | None = Field(default=None, gt=0)
    max_rounds: int = Field(default=4, ge=0, le=6)


class ExtractResponse(BaseModel):
    session_id: str
    lines: RequestLines
    explanation: str | None = None
    explanation_unavailable: bool = False


class ConfirmBody(BaseModel):
    lines: RequestLines
    policy: BuyerPolicy | None = None


class CatalogOffer(BaseModel):
    sku: str
    name: str
    description: str
    attributes: dict[str, str] = Field(default_factory=dict)
    sample_data: bool = True


class AgentDescription(BaseModel):
    did: str
    name: str
    public_url: str
    description_url: str
    offers: list[CatalogOffer]
    sample_data: bool = True


class MarketHit(BaseModel):
    did: str
    name: str
    public_url: str
    description_url: str
    matched_sku: str
    matched_name: str


class CounterOffer(BaseModel):
    round: int = Field(ge=1, le=10)
    target_unit_price: float = Field(gt=0)
    # Lowest signed rival price the buyer holds, without naming the rival.
    rival_unit_price: float | None = Field(default=None, gt=0)
    previous_quote_hash: str | None = Field(default=None, max_length=80)


class QuoteRequest(BaseModel):
    request_id: str
    buyer_did: str
    lines: RequestLines
    negotiation: bool = False
    counter: CounterOffer | None = None


class PricedQuote(BaseModel):
    kind: Literal["quote"] = "quote"
    quote_id: str
    supplier_did: str
    sku: str
    part_name: str
    quantity: int
    unit_price: float
    currency: str = "USD"
    price_basis: Literal["contract", "list", "volume"]
    lead_time_days: int
    need_by_days: int
    meets_date: bool
    expires_at: str
    attributes: dict[str, str] = Field(default_factory=dict)
    delivery: Literal["standard", "expedited"] = "standard"
    expedite_premium: float = 0.0
    round: int = 0
    opening_unit_price: float | None = None
    previous_unit_price: float | None = None
    final_offer: bool = False
    phrasing: str
    phrasing_from_model: bool = False
    # Free text from the supplier. Untrusted: displayed, never acted on.
    note: str = Field(default="", max_length=1000)


class DatedRefusal(BaseModel):
    kind: Literal["refusal"] = "refusal"
    quote_id: str
    supplier_did: str
    sku: str
    part_name: str
    quantity: int
    lead_time_days: int
    need_by_days: int
    meets_date: bool = False
    reason: str
    phrasing: str
    phrasing_from_model: bool = False
    note: str = Field(default="", max_length=1000)


class QuoteQuestion(BaseModel):
    kind: Literal["question"] = "question"
    quote_id: str
    supplier_did: str
    sku: str
    part_name: str
    missing_attribute: str
    phrasing: str
    phrasing_from_model: bool = False
    note: str = Field(default="", max_length=1000)


QuotePayload = PricedQuote | DatedRefusal | QuoteQuestion


class SignedEnvelope(BaseModel):
    """Wire format for signed quote / order messages."""

    sender_did: str
    method: str
    url: str
    timestamp: str
    nonce: str
    body: dict[str, Any]
    body_digest: str
    signature: str
    key_id: str


class RankedQuote(BaseModel):
    supplier_did: str
    supplier_name: str
    quote: PricedQuote
    quote_hash: str
    signature_verified: bool
    quote_valid: bool
    date_met: bool
    rank: int | None
    eligible: bool
    reason: str


class RankingResult(BaseModel):
    eligible: list[RankedQuote]
    excluded: list[RankedQuote]
    winner: RankedQuote | None
    explanation: str
    explanation_unavailable: bool = False


class NegotiateBody(BaseModel):
    supplier_did: str
    lines: RequestLines


class ApproveBody(BaseModel):
    quote_hash: str
    supplier_did: str


class OrderRequest(BaseModel):
    order_id: str
    buyer_did: str
    quote_hash: str
    quote: dict[str, Any]
    approved_at: str


class OrderResult(BaseModel):
    accepted: bool
    order_id: str
    message: str


class StoryEvent(BaseModel):
    id: str
    at: str
    mark: str
    sentence: str
    detail: dict[str, Any] = Field(default_factory=dict)


class SessionState(BaseModel):
    session_id: str
    status: str
    lines: RequestLines | None = None
    policy: BuyerPolicy = Field(default_factory=BuyerPolicy)
    spec_answers: dict[str, str] = Field(default_factory=dict)
    round: int = 0
    confirmed: bool = False
    market_hits: list[MarketHit] = Field(default_factory=list)
    threads: dict[str, dict[str, Any]] = Field(default_factory=dict)
    ranking: RankingResult | None = None
    approved_hash: str | None = None
    approved_supplier: str | None = None
    order: OrderResult | None = None
    events: list[StoryEvent] = Field(default_factory=list)
    extract_unavailable: bool = False
