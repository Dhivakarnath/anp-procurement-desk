"""Price book and lead-time logic. Models never set these numbers."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from .identity import utc_now, utc_now_iso
from .models import (
    CounterOffer,
    DatedRefusal,
    PricedQuote,
    QuotePayload,
    QuoteQuestion,
    RequestLines,
)


@dataclass
class VolumeTier:
    min_qty: int
    unit_price: float


@dataclass
class PriceBookEntry:
    sku: str
    name: str
    description: str
    attributes: dict[str, str] = field(default_factory=dict)
    list_price: float = 0.0
    contract_price: float | None = None
    volume_tiers: list[VolumeTier] = field(default_factory=list)
    stock_qty: int = 0
    lead_time_days: int = 0
    # Attribute that must be present before a price is offered (e.g. compound).
    required_attribute: str | None = None
    sample_data: bool = True
    # Private negotiation policy. Never published, never sent to a buyer.
    floor_price: float | None = None
    concession_rate: float = 0.5
    expedite_lead_days: int | None = None
    expedite_premium: float = 0.0
    expedite_premium_floor: float = 0.0


@dataclass
class SupplierBook:
    supplier_id: str
    supplier_did: str
    supplier_name: str
    # Buyer DIDs that get contract pricing when contract_price is set.
    contract_buyers: set[str] = field(default_factory=set)
    entries: list[PriceBookEntry] = field(default_factory=list)

    def find(self, part: str) -> PriceBookEntry | None:
        needle = part.strip().lower()
        for entry in self.entries:
            if needle in entry.name.lower() or needle in entry.sku.lower():
                return entry
            for value in entry.attributes.values():
                if needle in value.lower():
                    return entry
        return None


def _pick_unit_price(
    book: SupplierBook,
    entry: PriceBookEntry,
    buyer_did: str,
    quantity: int,
) -> tuple[float, Literal["contract", "list", "volume"]]:
    volume_price = None
    for tier in sorted(entry.volume_tiers, key=lambda t: t.min_qty, reverse=True):
        if quantity >= tier.min_qty:
            volume_price = tier.unit_price
            break

    if (
        entry.contract_price is not None
        and buyer_did in book.contract_buyers
    ):
        # Contract wins unless a volume tier is strictly lower.
        if volume_price is not None and volume_price < entry.contract_price:
            return volume_price, "volume"
        return entry.contract_price, "contract"

    if volume_price is not None and volume_price < entry.list_price:
        return volume_price, "volume"
    return entry.list_price, "list"


def compute_quote(
    book: SupplierBook,
    *,
    buyer_did: str,
    lines: RequestLines,
    quote_ttl_seconds: int,
    counter: CounterOffer | None = None,
    previous: dict[str, Any] | None = None,
) -> QuotePayload:
    payload, _trace = compute_quote_with_trace(
        book,
        buyer_did=buyer_did,
        lines=lines,
        quote_ttl_seconds=quote_ttl_seconds,
        counter=counter,
        previous=previous,
    )
    return payload


# Share of the normal concession a supplier gives when no rival undercuts it.
UNPRESSURED_SHARE = 0.25


def _cents_down(value: float) -> float:
    return math.floor(round(value * 100, 6)) / 100


def _cents_up(value: float) -> float:
    return math.ceil(round(value * 100, 6)) / 100


def concede(
    *,
    current: float,
    floor: float,
    rate: float,
    target: float,
    rival: float | None,
) -> tuple[float, bool, list[str]]:
    """One supplier move. Returns (new price, best-and-final, steps)."""
    steps: list[str] = []
    floor = _cents_up(floor)
    if target >= current:
        steps.append(f"Ask ${target:.2f} is at or above the current ${current:.2f}; price stands.")
        return current, False, steps
    pressured = rival is not None and rival <= current
    step = rate if pressured else rate * UNPRESSURED_SHARE
    desired = current - (current - floor) * step
    if pressured:
        steps.append(
            f"Undercut by a rival: move {int(step * 100)}% of the way from ${current:.2f} toward the floor, "
            f"to ${desired:.3f}."
        )
    else:
        steps.append(
            f"No lower rival cited, so we lead: token move of {int(step * 100)}% toward the floor, "
            f"to ${desired:.3f}."
        )
    if pressured:
        beat = rival - 0.01
        if beat < desired:
            steps.append(f"Rival offer ${rival:.2f} cited; tries ${beat:.2f} to beat it.")
            desired = beat
    new = max(floor, target, _cents_down(desired))
    if new >= current - 0.0049:
        steps.append(f"Cannot move below ${current:.2f}; holds as best and final.")
        return current, True, steps
    if new <= floor + 1e-9:
        steps.append(f"Reached the floor: ${floor:.2f} is best and final.")
        return floor, True, steps
    if new == target:
        steps.append(f"Meets the buyer's ask of ${target:.2f}.")
    else:
        steps.append(f"Offers ${new:.2f}.")
    return new, False, steps


def compute_quote_with_trace(
    book: SupplierBook,
    *,
    buyer_did: str,
    lines: RequestLines,
    quote_ttl_seconds: int,
    counter: CounterOffer | None = None,
    previous: dict[str, Any] | None = None,
) -> tuple[QuotePayload, list[str]]:
    """Return the reply plus the plain-language steps the price book took."""
    trace: list[str] = []
    entry = book.find(lines.part)
    if entry is None:
        trace.append(f"No catalog entry matches “{lines.part}”.")
        return (
            QuoteQuestion(
                quote_id=str(uuid.uuid4()),
                supplier_did=book.supplier_did,
                sku="unknown",
                part_name=lines.part,
                missing_attribute="part",
                phrasing="We do not stock the requested part.",
                phrasing_from_model=False,
            ),
            trace,
        )
    trace.append(f"Catalog match: {entry.sku} ({entry.name}).")

    if entry.required_attribute:
        value = lines.attributes.get(entry.required_attribute, "").strip()
        if not value:
            trace.append(
                f"{entry.required_attribute.capitalize()} is required before pricing and was not given."
            )
            return (
                QuoteQuestion(
                    quote_id=str(uuid.uuid4()),
                    supplier_did=book.supplier_did,
                    sku=entry.sku,
                    part_name=entry.name,
                    missing_attribute=entry.required_attribute,
                    phrasing=(
                        f"Please provide the required {entry.required_attribute} "
                        f"for {entry.name} before we can price it."
                    ),
                    phrasing_from_model=False,
                ),
                trace,
            )
        trace.append(f"{entry.required_attribute.capitalize()} given: {value}.")

    lead = entry.lead_time_days
    if lines.quantity <= entry.stock_qty:
        lead = min(lead, 7)
        trace.append(
            f"Stock of {entry.stock_qty:,} covers {lines.quantity:,}; ships in {lead} days."
        )
    else:
        trace.append(
            f"Stock of {entry.stock_qty:,} does not cover {lines.quantity:,}; "
            f"factory lead time is {lead} days."
        )

    expedited = False
    if lead > lines.need_by_days:
        fast = entry.expedite_lead_days
        if fast is not None and fast <= lines.need_by_days:
            expedited = True
            trace.append(
                f"{lead} days misses the {lines.need_by_days}-day need-by date; expedited production "
                f"ships in {fast} days for ${entry.expedite_premium:.2f} more per unit."
            )
            lead = fast
        else:
            trace.append(
                f"{lead} days misses the {lines.need_by_days}-day need-by date and no faster option "
                "exists, so no price is offered."
            )
            return (
                DatedRefusal(
                    quote_id=str(uuid.uuid4()),
                    supplier_did=book.supplier_did,
                    sku=entry.sku,
                    part_name=entry.name,
                    quantity=lines.quantity,
                    lead_time_days=lead,
                    need_by_days=lines.need_by_days,
                    meets_date=False,
                    reason=f"Lead time is {lead} days; need-by is {lines.need_by_days} days.",
                    phrasing=(
                        f"We can supply {entry.name} in {lead} days, which misses "
                        f"your {lines.need_by_days}-day need-by date."
                    ),
                    phrasing_from_model=False,
                ),
                trace,
            )
    else:
        trace.append(f"{lead} days meets the {lines.need_by_days}-day need-by date.")

    unit_price, basis = _pick_unit_price(book, entry, buyer_did, lines.quantity)
    has_contract = entry.contract_price is not None and buyer_did in book.contract_buyers
    if has_contract:
        trace.append(f"Buyer holds a contract account: contract price ${entry.contract_price:.2f}.")
    else:
        trace.append(f"No contract account for this buyer: list price ${entry.list_price:.2f}.")
    for tier in sorted(entry.volume_tiers, key=lambda t: t.min_qty):
        if lines.quantity >= tier.min_qty:
            trace.append(f"Volume tier {tier.min_qty:,}+ reached at ${tier.unit_price:.2f}.")
        else:
            trace.append(f"Volume tier {tier.min_qty:,}+ not reached.")

    premium = entry.expedite_premium if expedited else 0.0
    opening = round(unit_price + premium, 4)
    if expedited:
        trace.append(f"Opening price ${unit_price:.2f} + ${premium:.2f} expedite = ${opening:.2f}.")
    else:
        trace.append(f"Opening {basis} price ${opening:.2f} each.")

    price = opening
    previous_price: float | None = None
    final = False
    round_no = 0
    if counter is not None:
        round_no = counter.round
        floor = (entry.floor_price if entry.floor_price is not None else unit_price) + (
            entry.expedite_premium_floor if expedited else 0.0
        )
        floor = min(floor, opening)
        current = opening
        if (
            previous
            and previous.get("sku") == entry.sku
            and previous.get("quantity") == lines.quantity
            and previous.get("delivery", "standard") == ("expedited" if expedited else "standard")
        ):
            current = float(previous["unit_price"])
            trace.append(f"Our last signed offer on this request: ${current:.2f}.")
        ask = f"Counter round {counter.round}: buyer asks ${counter.target_unit_price:.2f}"
        if counter.rival_unit_price is not None:
            ask += f" and cites a rival offer at ${counter.rival_unit_price:.2f}"
        trace.append(ask + ".")
        trace.append(f"Private floor ${floor:.2f} (never disclosed).")
        price, final, steps = concede(
            current=current,
            floor=floor,
            rate=entry.concession_rate,
            target=counter.target_unit_price,
            rival=counter.rival_unit_price,
        )
        trace.extend(steps)
        previous_price = current

    expires = utc_now().timestamp() + quote_ttl_seconds
    from datetime import datetime, timezone

    expires_at = datetime.fromtimestamp(expires, tz=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )

    attrs = dict(entry.attributes)
    attrs.update({k: v for k, v in lines.attributes.items() if v})

    if counter is None:
        sentence = (
            f"{basis.capitalize()} price ${price:.2f} each for {lines.quantity} × {entry.name}, "
            f"ship in {lead} days{' (expedited)' if expedited else ''}."
        )
    elif previous_price is not None and price < previous_price:
        sentence = (
            f"We can come down from ${previous_price:.2f} to ${price:.2f} each"
            f"{', our best and final' if final else ''}."
        )
    else:
        sentence = f"${price:.2f} each is our best and final price."

    return (
        PricedQuote(
            quote_id=str(uuid.uuid4()),
            supplier_did=book.supplier_did,
            sku=entry.sku,
            part_name=entry.name,
            quantity=lines.quantity,
            unit_price=round(price, 4),
            currency="USD",
            price_basis=basis,
            lead_time_days=lead,
            need_by_days=lines.need_by_days,
            meets_date=True,
            expires_at=expires_at,
            attributes=attrs,
            delivery="expedited" if expedited else "standard",
            expedite_premium=premium,
            round=round_no,
            opening_unit_price=opening,
            previous_unit_price=previous_price,
            final_offer=final,
            phrasing=sentence,
            phrasing_from_model=False,
        ),
        trace,
    )


def seed_s1(buyer_did: str, supplier_did: str) -> SupplierBook:
    return SupplierBook(
        supplier_id="s1",
        supplier_did=supplier_did,
        supplier_name="S1",
        contract_buyers={buyer_did},
        entries=[
            PriceBookEntry(
                sku="BOLT-SS-M8-40",
                name="Stainless steel hex bolts M8×40",
                description="A2-70 stainless hex bolts, sample catalog data",
                attributes={"material": "stainless", "size": "M8x40"},
                list_price=0.42,
                contract_price=0.31,
                volume_tiers=[VolumeTier(min_qty=5000, unit_price=0.27)],
                stock_qty=20000,
                lead_time_days=5,
                floor_price=0.29,
                concession_rate=0.5,
            ),
            PriceBookEntry(
                sku="SEAL-SHAFT-45",
                name="Shaft seal 45mm",
                description="Rotary shaft seal, sample catalog data",
                attributes={"size": "45mm"},
                list_price=4.80,
                contract_price=3.90,
                volume_tiers=[VolumeTier(min_qty=200, unit_price=3.50)],
                stock_qty=500,
                lead_time_days=7,
                required_attribute="compound",
                floor_price=3.32,
                concession_rate=0.4,
            ),
        ],
    )


def seed_s2(supplier_did: str) -> SupplierBook:
    return SupplierBook(
        supplier_id="s2",
        supplier_did=supplier_did,
        supplier_name="S2",
        contract_buyers=set(),
        entries=[
            PriceBookEntry(
                sku="BOLT-SS-M8-40",
                name="Stainless steel hex bolts M8×40",
                description="A2-70 stainless hex bolts, sample catalog data",
                attributes={"material": "stainless", "size": "M8x40"},
                list_price=0.38,
                contract_price=None,
                volume_tiers=[VolumeTier(min_qty=5000, unit_price=0.33)],
                stock_qty=0,
                lead_time_days=21,
                floor_price=0.28,
                concession_rate=0.5,
                expedite_lead_days=9,
                expedite_premium=0.09,
                expedite_premium_floor=0.05,
            ),
            PriceBookEntry(
                sku="SEAL-SHAFT-45",
                name="Shaft seal 45mm",
                description="Rotary shaft seal, sample catalog data",
                attributes={"size": "45mm"},
                list_price=4.50,
                volume_tiers=[VolumeTier(min_qty=200, unit_price=4.10)],
                stock_qty=0,
                lead_time_days=18,
                required_attribute="compound",
                floor_price=3.70,
                concession_rate=0.5,
                expedite_lead_days=12,
                expedite_premium=0.45,
                expedite_premium_floor=0.30,
            ),
        ],
    )


def seed_s3(supplier_did: str) -> SupplierBook:
    return SupplierBook(
        supplier_id="s3",
        supplier_did=supplier_did,
        supplier_name="S3",
        contract_buyers=set(),
        entries=[
            PriceBookEntry(
                sku="SEAL-SHAFT-45",
                name="Shaft seal 45mm",
                description="Rotary shaft seal, sample catalog data",
                attributes={"size": "45mm"},
                list_price=4.20,
                volume_tiers=[VolumeTier(min_qty=100, unit_price=3.85)],
                stock_qty=1000,
                lead_time_days=6,
                required_attribute="compound",
                floor_price=3.36,
                concession_rate=0.5,
            ),
        ],
    )


# Re-export for callers that want a stamp
__all__ = [
    "SupplierBook",
    "PriceBookEntry",
    "VolumeTier",
    "compute_quote",
    "compute_quote_with_trace",
    "concede",
    "seed_s1",
    "seed_s2",
    "seed_s3",
    "utc_now_iso",
]
