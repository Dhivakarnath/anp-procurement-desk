"""Deterministic ranking. Models only phrase the result afterward."""

from __future__ import annotations

from typing import Any

from .identity import parse_timestamp, quote_hash, utc_now
from .models import PricedQuote, RankedQuote, RankingResult


def _is_unexpired(expires_at: str) -> bool:
    try:
        return parse_timestamp(expires_at) > utc_now()
    except ValueError:
        return False


def rank_quotes(
    candidates: list[dict[str, Any]],
    *,
    max_unit_price: float | None = None,
) -> RankingResult:
    """
    candidates items:
      {
        "supplier_did", "supplier_name",
        "payload": PricedQuote | dict | None,
        "signature_verified": bool,
        "kind": "quote"|"refusal"|"question"|None,
        "quarantined": bool (optional),
      }
    """
    eligible: list[RankedQuote] = []
    excluded: list[RankedQuote] = []

    for item in candidates:
        payload = item.get("payload")
        kind = item.get("kind")
        verified = bool(item.get("signature_verified"))
        name = item.get("supplier_name") or item.get("supplier_did")
        did = item.get("supplier_did") or ""

        if payload is None:
            excluded.append(
                RankedQuote(
                    supplier_did=did,
                    supplier_name=name,
                    quote=_empty_quote(did),
                    quote_hash="",
                    signature_verified=verified,
                    quote_valid=False,
                    date_met=False,
                    rank=None,
                    eligible=False,
                    reason="no priced quote",
                )
            )
            continue

        if isinstance(payload, dict):
            if payload.get("kind") != "quote":
                reason = {
                    "refusal": "date missed",
                    "question": "question with no price",
                }.get(payload.get("kind"), "not a priced quote")
                excluded.append(
                    RankedQuote(
                        supplier_did=did,
                        supplier_name=name,
                        quote=_empty_quote(did),
                        quote_hash="",
                        signature_verified=verified,
                        quote_valid=False,
                        date_met=False,
                        rank=None,
                        eligible=False,
                        reason=reason,
                    )
                )
                continue
            quote = PricedQuote.model_validate(payload)
        elif isinstance(payload, PricedQuote):
            quote = payload
        else:
            excluded.append(
                RankedQuote(
                    supplier_did=did,
                    supplier_name=name,
                    quote=_empty_quote(did),
                    quote_hash="",
                    signature_verified=verified,
                    quote_valid=False,
                    date_met=False,
                    rank=None,
                    eligible=False,
                    reason="unsupported payload",
                )
            )
            continue

        qhash = quote_hash(quote.model_dump(mode="json"))
        valid = verified and _is_unexpired(quote.expires_at)
        date_met = bool(quote.meets_date)

        reasons: list[str] = []
        if not verified:
            reasons.append("signature not verified")
        if not _is_unexpired(quote.expires_at):
            reasons.append("quote expired")
        if not date_met:
            reasons.append("date not met")
        within_budget = max_unit_price is None or quote.unit_price <= max_unit_price + 1e-9
        if not within_budget:
            reasons.append("above the buyer's walk-away price")
        quarantined = bool(item.get("quarantined"))
        if quarantined:
            reasons.append("sent instructions aimed at the buyer's agent; held for human review")

        row = RankedQuote(
            supplier_did=did,
            supplier_name=name,
            quote=quote,
            quote_hash=qhash,
            signature_verified=verified,
            quote_valid=valid,
            date_met=date_met,
            rank=None,
            eligible=valid and date_met and within_budget and not quarantined,
            reason="; ".join(reasons) if reasons else "eligible",
        )
        if row.eligible:
            eligible.append(row)
        else:
            excluded.append(row)

        # silence unused
        _ = kind

    eligible.sort(key=lambda r: (r.quote.unit_price, r.quote.lead_time_days, r.supplier_did))
    for idx, row in enumerate(eligible, start=1):
        row.rank = idx

    winner = eligible[0] if eligible else None
    explanation = _code_explanation(winner, eligible, excluded)
    return RankingResult(
        eligible=eligible,
        excluded=excluded,
        winner=winner,
        explanation=explanation,
        explanation_unavailable=False,
    )


def _empty_quote(did: str) -> PricedQuote:
    return PricedQuote(
        quote_id="none",
        supplier_did=did,
        sku="",
        part_name="",
        quantity=0,
        unit_price=0.0,
        price_basis="list",
        lead_time_days=0,
        need_by_days=0,
        meets_date=False,
        expires_at="1970-01-01T00:00:00Z",
        phrasing="",
    )


def _code_explanation(
    winner: RankedQuote | None,
    eligible: list[RankedQuote],
    excluded: list[RankedQuote],
) -> str:
    parts: list[str] = []
    if winner:
        parts.append(
            f"{winner.supplier_name} is first on price at "
            f"${winner.quote.unit_price:.2f} each "
            f"({winner.quote.price_basis}), lead time "
            f"{winner.quote.lead_time_days} days."
        )
    else:
        parts.append("No eligible quotes after signature, expiry, and date checks.")

    for row in eligible[1:]:
        parts.append(
            f"{row.supplier_name} also qualifies at ${row.quote.unit_price:.2f}."
        )
    for row in excluded:
        if row.reason and row.reason != "eligible":
            parts.append(f"{row.supplier_name}: {row.reason}.")
    return " ".join(parts)


def sanitize_explanation(text: str, ranking: RankingResult) -> str:
    """Drop any number in the model text that is not present in the ranking."""
    allowed: set[str] = set()
    for row in ranking.eligible + ranking.excluded + ([ranking.winner] if ranking.winner else []):
        if row is None or not row.quote_hash:
            continue
        allowed.add(f"{row.quote.unit_price:.2f}")
        allowed.add(f"{row.quote.unit_price:.4f}".rstrip("0").rstrip("."))
        allowed.add(str(row.quote.lead_time_days))
        allowed.add(str(row.quote.quantity))
        allowed.add(str(row.rank or ""))

    # Keep the code explanation if the model invents foreign numbers.
    import re

    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    for num in numbers:
        if num not in allowed and num not in {"1", "2", "3"}:
            return ranking.explanation
    return text.strip() or ranking.explanation
