#!/usr/bin/env python3
"""Verify 10-day, 30-day, and unmatched search against a running stack."""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

BUYER = os.environ.get("BUYER_URL", "https://buyer.test")
CA = os.environ.get("SSL_CERT_FILE", os.path.join(os.path.dirname(__file__), "..", "certs", "ca.crt"))


def client() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if os.path.exists(CA):
        ctx.load_verify_locations(CA)
    return ctx


def post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BUYER}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, context=client(), timeout=120) as resp:
        return json.loads(resp.read().decode())


def put(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BUYER}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, context=client(), timeout=60) as resp:
        return json.loads(resp.read().decode())


def run_case(name: str, text: str, lines_override: dict | None = None) -> dict:
    print(f"\n=== {name} ===")
    session = post("/sessions", {"text": text})
    lines = session["lines"]
    if lines_override:
        lines = {**lines, **lines_override}
        if "attributes" in lines_override:
            lines["attributes"] = {
                **(session["lines"].get("attributes") or {}),
                **lines_override["attributes"],
            }
    session = post(f"/sessions/{session['session_id']}/confirm", {"lines": lines})
    print("status:", session["status"])
    print("hits:", len(session.get("market_hits") or []))
    for did, th in (session.get("threads") or {}).items():
        latest = th.get("latest") or {}
        print(
            f"  {th.get('supplier_name')}: kind={latest.get('kind')} "
            f"verified={latest.get('signature_verified')}"
        )
    ranking = session.get("ranking") or {}
    winner = ranking.get("winner")
    if winner:
        print(
            f"winner: {winner['supplier_name']} @ {winner['quote']['unit_price']} "
            f"({winner['quote']['price_basis']})"
        )
    else:
        print("winner: none")
    print("explanation:", ranking.get("explanation"))
    return session


def main() -> int:
    try:
        s10 = run_case(
            "10-day bolts",
            "Need 2000 stainless steel hex bolts M8×40 within 10 days.",
            {
                "part": "stainless steel hex bolts M8×40",
                "quantity": 2000,
                "need_by_days": 10,
            },
        )
        kinds = {
            th["supplier_name"]: (th.get("latest") or {}).get("kind")
            for th in (s10.get("threads") or {}).values()
        }
        assert kinds.get("S1") == "quote", kinds
        assert kinds.get("S2") == "refusal", kinds
        assert (s10.get("ranking") or {}).get("winner", {}).get("supplier_name") == "S1"

        s30 = run_case(
            "30-day bolts",
            "Need 2000 stainless steel hex bolts M8×40 within 30 days.",
            {
                "part": "stainless steel hex bolts M8×40",
                "quantity": 2000,
                "need_by_days": 30,
            },
        )
        kinds30 = {
            th["supplier_name"]: (th.get("latest") or {}).get("kind")
            for th in (s30.get("threads") or {}).values()
        }
        assert kinds30.get("S2") == "quote", kinds30

        none = run_case(
            "unmatched part",
            "Need 50 unicorn plasma gaskets within 10 days.",
            {
                "part": "unicorn plasma gasket",
                "quantity": 50,
                "need_by_days": 10,
            },
        )
        assert none.get("status") == "no_suppliers"
        assert len(none.get("market_hits") or []) == 0

        print("\nAll verification checks passed.")
        return 0
    except urllib.error.URLError as exc:
        print("Request failed:", exc, file=sys.stderr)
        return 1
    except AssertionError as exc:
        print("Assertion failed:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
