"""Untrusted-text handling for agent-to-agent messages.

Decisions never read free text: prices, dates and ranks come from signed
structured fields. This module only reports instruction-like text and wording
that disagrees with the signed numbers, and keeps counterparty strings out of
model prompts.
"""

from __future__ import annotations

import re
from typing import Any

_INSTRUCTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("asks the agent to ignore its rules", re.compile(r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instruction|rule|polic|prompt|previous|above)", re.I)),
    ("claims system or developer authority", re.compile(r"\b(system|developer|admin)\s*(prompt|override|message|mode)?\s*[:\]]", re.I)),
    ("tries to change the agent's role", re.compile(r"\byou are now\b|\bact as\b|\bnew instructions?\b", re.I)),
    ("pushes to skip human approval", re.compile(r"\b(skip|bypass|without)\b.{0,30}\b(approv|human|review|confirm)", re.I)),
    ("tells the buyer to approve or order", re.compile(r"\b(approve|accept|place (the )?order)\b.{0,40}\b(immediately|now|right away|at once)\b", re.I)),
    ("attacks another party's signature", re.compile(r"\b(signature|quote)s?\b.{0,30}\b(invalid|fake|fraud|forged)", re.I)),
]

_MONEY = re.compile(r"\$\s?(\d+(?:\.\d{1,4})?)")


def instruction_flags(text: str) -> list[str]:
    """Plain-language reasons the text looks like an instruction aimed at an agent."""
    if not text:
        return []
    return [label for label, pattern in _INSTRUCTION_PATTERNS if pattern.search(text)]


def wording_mismatches(text: str, allowed: list[float]) -> list[str]:
    """Dollar amounts in wording that match none of the signed numbers."""
    if not text:
        return []
    ok = {round(a, 2) for a in allowed if a is not None}
    bad: list[str] = []
    for raw in _MONEY.findall(text):
        value = round(float(raw), 2)
        if value not in ok:
            bad.append(f"${value:.2f}")
    return bad


def inspect_reply(
    payload: dict[str, Any] | None, *, own_numbers: tuple[float, ...] = ()
) -> list[dict[str, str]]:
    """Flags for a signed supplier reply. The reply's structured fields stay authoritative.

    own_numbers are amounts the buyer itself sent (its ask), so echoing them is not a mismatch.
    """
    if not payload:
        return []
    flags: list[dict[str, str]] = []
    for field in ("note", "phrasing"):
        text = str(payload.get(field) or "")
        for label in instruction_flags(text):
            flags.append({"field": field, "kind": "instruction", "reason": label, "text": text[:300]})
    signed = [
        payload.get("unit_price"),
        payload.get("previous_unit_price"),
        payload.get("opening_unit_price"),
        payload.get("expedite_premium"),
        *own_numbers,
    ]
    for field in ("phrasing", "note"):
        text = str(payload.get(field) or "")
        for amount in wording_mismatches(text, [float(v) for v in signed if v is not None]):
            flags.append(
                {
                    "field": field,
                    "kind": "number",
                    "reason": f"mentions {amount}, which is not a signed number",
                    "text": text[:300],
                }
            )
    return flags


def quarantined(thread: dict[str, Any]) -> bool:
    """A supplier that ever aimed instructions at the buyer is not bargained with or awarded."""
    return any(
        f.get("kind") == "instruction"
        for reply in thread.get("replies") or []
        for f in reply.get("guard") or []
    )


def inspect_request(lines: dict[str, Any] | None) -> list[dict[str, str]]:
    """Flags for a buyer request, checked on the supplier side."""
    if not lines:
        return []
    text = str(lines.get("notes") or "")
    return [
        {"field": "notes", "kind": "instruction", "reason": label, "text": text[:300]}
        for label in instruction_flags(text)
    ]


_MODEL_FACT_KEYS = {
    "kind",
    "sku",
    "part_name",
    "quantity",
    "unit_price",
    "currency",
    "price_basis",
    "lead_time_days",
    "need_by_days",
    "meets_date",
    "missing_attribute",
    "reason",
    "delivery",
    "expedite_premium",
    "round",
    "previous_unit_price",
    "final_offer",
}


def model_facts(payload: dict[str, Any], *, catalog_names: set[str]) -> dict[str, Any]:
    """Only code-owned fields reach a model. Buyer-typed strings are replaced."""
    facts = {k: v for k, v in payload.items() if k in _MODEL_FACT_KEYS}
    if facts.get("part_name") not in catalog_names:
        facts["part_name"] = "the requested part"
    return facts
