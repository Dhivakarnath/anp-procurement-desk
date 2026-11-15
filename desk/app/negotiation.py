"""Buyer bargaining policy. Pure functions over signed, structured replies only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .guard import quarantined
from .models import BuyerPolicy, CounterOffer, RequestLines

# Buyer-private data, sample values. Keyed by a word in the part name.
BUYER_SPECS: list[tuple[str, dict[str, str]]] = [
    ("seal", {"compound": "FKM"}),
]

BUYER_BUDGETS: list[tuple[str, float, float]] = [
    # keyword, target unit price, walk-away unit price
    ("bolt", 0.27, 0.40),
    ("seal", 3.30, 4.25),
]

NO_TARGET_DISCOUNT = 0.08


def default_policy(lines: RequestLines | None) -> BuyerPolicy:
    part = (lines.part if lines else "").lower()
    for word, target, walk_away in BUYER_BUDGETS:
        if word in part:
            return BuyerPolicy(target_unit_price=target, walk_away_unit_price=walk_away)
    return BuyerPolicy()


def spec_answer(lines: RequestLines | None, attribute: str) -> str | None:
    if lines is None:
        return None
    given = lines.attributes.get(attribute, "").strip()
    if given:
        return given
    part = lines.part.lower()
    for word, specs in BUYER_SPECS:
        if word in part and specs.get(attribute):
            return specs[attribute]
    return None


@dataclass
class Offer:
    supplier_did: str
    unit_price: float
    quote_hash: str
    final: bool


def live_offers(threads: dict[str, dict[str, Any]]) -> list[Offer]:
    """Priced, signature-verified offers that meet the date. Free text is not read."""
    offers: list[Offer] = []
    for did, thread in threads.items():
        latest = thread.get("latest") or {}
        payload = latest.get("payload") or {}
        if (
            not quarantined(thread)
            and latest.get("signature_verified")
            and payload.get("kind") == "quote"
            and payload.get("meets_date")
            and latest.get("quote_hash")
        ):
            offers.append(
                Offer(
                    supplier_did=did,
                    unit_price=float(payload["unit_price"]),
                    quote_hash=latest["quote_hash"],
                    final=bool(payload.get("final_offer")),
                )
            )
    return offers


def resolve_target(policy: BuyerPolicy, offers: list[Offer]) -> float | None:
    if policy.target_unit_price is not None:
        return policy.target_unit_price
    if not offers:
        return None
    best = min(o.unit_price for o in offers)
    return round(best * (1 - NO_TARGET_DISCOUNT), 2)


def plan_counters(
    threads: dict[str, dict[str, Any]],
    *,
    target: float,
    round_no: int,
) -> list[tuple[str, CounterOffer]]:
    """Counter-offers for one round. Empty when bargaining should stop."""
    offers = live_offers(threads)
    if not offers:
        return []
    best = min(o.unit_price for o in offers)
    if best <= target + 1e-9:
        return []
    plan: list[tuple[str, CounterOffer]] = []
    for offer in offers:
        if offer.final or offer.unit_price <= target + 1e-9:
            continue
        rivals = [o.unit_price for o in offers if o.supplier_did != offer.supplier_did]
        rival = min(rivals) if rivals else None
        plan.append(
            (
                offer.supplier_did,
                CounterOffer(
                    round=round_no,
                    target_unit_price=target,
                    rival_unit_price=rival if rival is not None and rival <= offer.unit_price else None,
                    previous_quote_hash=offer.quote_hash,
                ),
            )
        )
    return plan
