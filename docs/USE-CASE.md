# Use Case Selection: What to Build on ANP

- Research date: 2026-10-30
- Companion to [ANP-CONTEXT.md](ANP-CONTEXT.md)

## Decision

**Build a cross-company B2B quote-to-order network on ANP.** It has two halves:

- **Supplier agent.** Each supplier company runs one. It publishes its catalog and quoting interfaces, and it recognizes buyer agents by their DID, so a known customer's agent gets that customer's contract prices.
- **Buyer agent.** It discovers suppliers, sends a request for quote (RFQ) to many of them in parallel, compares the quotes locally against budget and policy, gets human approval, and places the order.

ANP's own white paper uses this scenario as its main example (vNext §10.1). It is also the domain of one of ANP's two named adopters, the Trade Agent Network.

## Why this one

### 1. Large, documented demand
- Gartner's top strategic prediction for 2026 is that by 2028, 90% of B2B buying will go through AI agents, which is more than $15 trillion of spend. ([Gartner](https://www.gartner.com/en/articles/strategic-predictions-for-2026))
- Procurement agents already exist:
  - SAP Ariba has sourcing and negotiation agents.
  - Ramp has vendor-review agents.
  - project44 launched a freight procurement agent in February 2026.
  ([Monetizely](https://www.getmonetizely.com/articles/when-ai-agents-negotiate-the-deal-rethinking-b2b-pricing), [project44](https://www.project44.com/press-releases/project44-launches-ai-freight-procurement-agent-to-cut-freight-spend-and-accelerate-sourcing/))
- Buyer agents send RFQs to dozens of suppliers at once and order from whoever answers first. A supplier that replies days later with a PDF loses the order. ([Workist](https://www.workist.com/en/blog/a2a-commerce-b2b-sales))

### 2. The gap is open, and it is exactly what ANP covers
- A McFadyen review of four agent protocols and six commerce platforms (October 2026) found that no current standard supports third-party agents buying at contract prices on credit terms. It lists "agent identity and authority to bind" as not yet supported. ([McFadyen](https://mcfadyen.com/articles/b2b-agentic-commerce-what-works-now/))
- The consumer protocols, ACP (OpenAI, Stripe) and UCP (Google, Shopify), were built for cards and carts.
- UCP's B2B parts are still open proposals ([Scandiweb](https://scandiweb.com/blog/universal-commerce-protocol/), status as of 15 Oct 2026):
  - buyer-specific prices (#877, filed 29 Sep 2026)
  - quotes (#929, filed 11 Oct 2026)
  - procurement charter (#947, filed 14 Oct 2026)
- The open B2B problem is identifying an unknown counterparty's agent and tying it to an account. This is what ANP's released specs provide:

| B2B need | ANP piece (all released) |
|---|---|
| "Which company's agent is this?" with no shared secret or prior OAuth setup | did:wba identity (ANP-03) + signed requests (ANP-02) |
| Contract pricing only for agents that prove they are the customer | DID → customer account mapping, checked on every signed call |
| Suppliers can be found by machines | `/.well-known/agent-descriptions` (ANP-08) + search agents |
| A machine-readable catalog and quoting API | `ad.json` with Information links and OpenRPC interfaces (ANP-07) |
| A human approves before the order binds the company | `humanAuthorization: true` on the order interface (ANP-07) |
| Questions about custom items and spec sheets | Messaging P3 + attachments P7 |

### 3. It avoids ANP's drafts
- **Payment:** B2B orders are usually paid on net terms against an invoice, so the ANP-10 payment draft is not needed.
- **Buyer authority:** the supplier keeps its own trading-partner registry (which buyer DID may order for which account, up to what limit). This is the same setup step EDI partners already go through. The ANP-05 credential draft is not needed for v1.

## Alternatives considered

| Use case | Demand | Open gap? | Fit with released ANP specs | Competition | Verdict |
|---|---|---|---|---|---|
| **B2B quote-to-order** | Gartner: 90% / $15T by 2028 | Yes; UCP B2B is still proposals | Strong; no drafts needed | UCP B2B proposals (Google, SAP, Zip) | **Build this** |
| Consumer shopping or booking (hotel, coffee) | Juniper: $1.5T agent purchases by 2030 ([Forbes](https://www.forbes.com/sites/neha-mehra/2026/10/29/agentic-commerce-is-here-is-your-startup-ready-to-sell-to-ai-agents/)) | Mostly closed | Weak; needs the ANP-10 payment draft | UCP (8,000+ verified stores), ACP, AP2, Visa TAP, Mastercard Agent Pay | Avoid |
| Gateway that verifies agent traffic | Real: Cloudflare, Akamai, AWS WAF, Vercel and HUMAN verify RFC 9421 agent signatures ([dev.to](https://dev.to/tomwangcn/web-bot-auth-vs-visa-tap-how-to-verify-ai-agents-27d4)) | Partly; Web Bot Auth, Visa TAP and Mastercard Agent Pay disagree on details | Good; ANP-02 is also RFC 9421 | CDN and WAF vendors at the edge | Add to the supplier verifier later |
| Freight spot quoting (shipper ↔ carrier and broker agents) | Real: project44 and broker automation vendors | Coordination still runs over email and voice | Good; same pattern | project44, Parade, HappyRobot | Second vertical for the same platform |
| Messaging app between organizations | AWiki | Already served | Good | AWiki (built on ANP) | Skip |
| Telecom 6G network agents | 3GPP / IETF studies | Requirements stage | Framework only | Network operators | Out of reach for one team |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| UCP's B2B quote and procurement proposals could become the standard business payload | ANP carries identity, discovery and transport. Quote and PO payloads follow the UCP #929 quote model (time-bound fixed price, issued by the seller, accepted by the buyer), and a payload adapter lets the supplier also expose UCP or MCP later. |
| Few buyers speak ANP today | Build both sides. The supplier agent publishes an MCP-compatible interface alongside the ANP interfaces. |
| An LLM agrees to terms the company didn't approve | Price, credit and approval checks are deterministic code. Orders require human approval. Quotes and order acknowledgements are signed so both sides hold evidence. |
| The SDK verifier deviates from ANP-02 (ANP-CONTEXT §6) | Our own verifier is the platform core, gated by the official ANP-02 vectors in CI. |

## Proposed v1 scope (to refine in the spec)

**Platform core** (the gateway from ANP-CONTEXT §10 A)
- did:wba identity hosting, with keys behind a signing interface.
- An ANP-02 verifier that conforms to the spec, with Redis replay protection and a cached, SSRF-safe DID resolver.
- `ad.json` and discovery publishing.
- A signing client.

**Supplier agent** (multi-tenant, so several demo suppliers run from one deployment)
- **Information:** a public catalog (JSON) linked from `ad.json`.
- **OpenRPC interfaces:**
  - `catalog.search`
  - `availability.check`
  - `rfq.submit`, which returns a signed quote with line prices, lead time, validity and terms
  - `order.place` (`humanAuthorization: true`), which returns a signed order acknowledgement
  - `order.status`
- **Natural-language interface:** for open questions. Anything it can't answer goes to a human sales inbox.
- **Trading-partner registry:** buyer DID → account → role and order limit. Anonymous callers get list prices; recognized DIDs get contract prices.
- **ERP adapter interface:** v1 uses a Postgres-backed reference ERP, with SAP and NetSuite adapters possible later.
- **Audit log** of verified signed requests, issued quotes and orders.

**Buyer agent**
- Discovers suppliers through `.well-known` on known domains or a small directory.
- Sends signed RFQs in parallel and collects the quotes.
- Compares quotes locally: deterministic budget and policy checks, plus an LLM explanation of the ranking.
- Has an approval screen for a human approver, then places the order.

**Phase 2**
- Messaging (P1/P3) for exception handling, and attachments (P7) for spec sheets and POs.
- Supplier directory with passive registration.
- Freight-quoting vertical.

**Stack and environment**
- Python 3.12, FastAPI, `anp==1.0.7` pinned for low-level helpers, Redis, Postgres, a small web UI for the approver.
- Docker Compose with several local HTTPS domains, so that `did:wba` resolution runs offline.
- AWS deployment once a domain is available.
