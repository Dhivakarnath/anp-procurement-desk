"""Local checks: price book and ranking without Docker."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.identity import quote_hash
from app.models import PricedQuote, RequestLines
from app.pricing import compute_quote, seed_s1, seed_s2, seed_s3
from app.ranking import rank_quotes


BUYER = "did:wba:buyer.test:agent"


def test_s1_contract_meets_10_days():
    book = seed_s1(BUYER, "did:wba:s1.test:agent")
    q = compute_quote(
        book,
        buyer_did=BUYER,
        lines=RequestLines(part="stainless steel hex bolts", quantity=2000, need_by_days=10),
        quote_ttl_seconds=900,
    )
    assert q.kind == "quote"
    assert q.price_basis == "contract"
    assert q.unit_price == 0.31
    assert q.meets_date is True


def test_s2_expedites_10_days_refuses_7_quotes_30():
    book = seed_s2("did:wba:s2.test:agent")
    lines10 = RequestLines(part="stainless steel hex bolts", quantity=2000, need_by_days=10)
    e = compute_quote(book, buyer_did=BUYER, lines=lines10, quote_ttl_seconds=900)
    assert e.kind == "quote" and e.delivery == "expedited"
    assert e.lead_time_days == 9 and e.unit_price == 0.47
    lines7 = RequestLines(part="stainless steel hex bolts", quantity=2000, need_by_days=7)
    r = compute_quote(book, buyer_did=BUYER, lines=lines7, quote_ttl_seconds=900)
    assert r.kind == "refusal"
    lines30 = RequestLines(part="stainless steel hex bolts", quantity=2000, need_by_days=30)
    q = compute_quote(book, buyer_did=BUYER, lines=lines30, quote_ttl_seconds=900)
    assert q.kind == "quote"
    assert q.price_basis == "list"


def test_s3_needs_compound():
    book = seed_s3("did:wba:s3.test:agent")
    q = compute_quote(
        book,
        buyer_did=BUYER,
        lines=RequestLines(part="shaft seal", quantity=20, need_by_days=10),
        quote_ttl_seconds=900,
    )
    assert q.kind == "question"
    assert q.missing_attribute == "compound"
    q2 = compute_quote(
        book,
        buyer_did=BUYER,
        lines=RequestLines(
            part="shaft seal",
            quantity=20,
            need_by_days=10,
            attributes={"compound": "NBR"},
        ),
        quote_ttl_seconds=900,
    )
    assert q2.kind == "quote"


def test_volume_tier_changes_price():
    book = seed_s2("did:wba:s2.test:agent")
    small = compute_quote(
        book,
        buyer_did=BUYER,
        lines=RequestLines(part="bolts", quantity=100, need_by_days=30),
        quote_ttl_seconds=900,
    )
    large = compute_quote(
        book,
        buyer_did=BUYER,
        lines=RequestLines(part="bolts", quantity=5000, need_by_days=30),
        quote_ttl_seconds=900,
    )
    assert small.kind == "quote" and large.kind == "quote"
    assert large.unit_price < small.unit_price
    assert large.price_basis == "volume"


def test_ranking_lowest_eligible_price():
    s1 = PricedQuote(
        quote_id="1",
        supplier_did="did:wba:s1.test:agent",
        sku="x",
        part_name="bolts",
        quantity=100,
        unit_price=0.31,
        price_basis="contract",
        lead_time_days=5,
        need_by_days=10,
        meets_date=True,
        expires_at="2099-01-01T00:00:00Z",
        phrasing="ok",
    )
    s2 = PricedQuote(
        quote_id="2",
        supplier_did="did:wba:s2.test:agent",
        sku="x",
        part_name="bolts",
        quantity=100,
        unit_price=0.38,
        price_basis="list",
        lead_time_days=21,
        need_by_days=30,
        meets_date=True,
        expires_at="2099-01-01T00:00:00Z",
        phrasing="ok",
    )
    result = rank_quotes(
        [
            {
                "supplier_did": s1.supplier_did,
                "supplier_name": "S1",
                "payload": s1.model_dump(),
                "kind": "quote",
                "signature_verified": True,
            },
            {
                "supplier_did": s2.supplier_did,
                "supplier_name": "S2",
                "payload": s2.model_dump(),
                "kind": "quote",
                "signature_verified": True,
            },
        ]
    )
    assert result.winner is not None
    assert result.winner.supplier_name == "S1"
    assert result.winner.quote_hash == quote_hash(s1.model_dump(mode="json"))


if __name__ == "__main__":
    test_s1_contract_meets_10_days()
    test_s2_refuses_10_days_quotes_30()
    test_s3_needs_compound()
    test_volume_tier_changes_price()
    test_ranking_lowest_eligible_price()
    print("pricing/ranking tests ok")
