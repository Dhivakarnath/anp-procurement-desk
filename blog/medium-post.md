# I Built a Multi-Agent Procurement Desk on ANP — With Signed Prices and Private Floors

*A buyer agent discovers suppliers, counters on signed numbers, and ranks only what cryptography allows — while models only word the replies.*

**Reading time:** ~7 minutes  
**Role lens:** AI Forward Deployed Engineer

---

> **In this desk, models write the email. Code owns the price.**

Most multi-agent demos stop when the chat looks clever. Procurement does not work that way.

A real desk needs machine-checkable quotes, rival leverage, private limits, and a human who still hits Approve. Soft prose cannot own the price.

So I built an **ANP Procurement Desk**: one buyer agent, a marketplace, and three supplier agents. They exchange **signed** envelopes. **Code** owns every number. Models (Claude Haiku / Amazon Nova on Bedrock) only **word** the replies.

**ANP (Agent Network Protocol)** is an open protocol for agents that do not share a company login. It gives each agent an identity (a DID, a Decentralized Identifier), a way to be discovered, and signed messages so a quote can be checked instead of trusted as prose. This desk is one professional use of that protocol: cross-company quote-to-order.

This is policy realism in a local Compose demo — not a claim that we already run a live multi-enterprise market.

![ANP Procurement Desk home — scenario bar, request composer, and empty lanes](./assets/01-desk-home.png)
*Figure 1. The desk opens like an exchange floor, not a chatbot: pick a scenario, describe a need, watch every party get its own lane.*

---

## The problem this maps to

B2B RFQs still often die in PDF and inbox lag. Agents make that worse if free text can rewrite the quote.

The open gap is not “can an LLM write a polite email?” It is:

- **Who is this counterparty’s agent?** (identity without a shared password vault)
- **What can it do?** (discoverable interfaces, not hard-coded URLs)
- **Which numbers are binding?** (signed fields vs free text)
- **Who may commit the company?** (human authorization before the order binds)

That is the layer [Agent Network Protocol (ANP)](https://agent-network-protocol.com/) targets: DIDs (Decentralized Identifiers), discovery, signed requests, agent descriptions. This desk explores that lane for quote-to-order.

---

## What we built

| Piece | Role |
|---|---|
| **Buyer** | Extracts the request, searches the market, fans out RFQs, bargains, ranks, waits for human approve |
| **Marketplace** | Catalog search only — discovery, not pricing |
| **S1** | Contract supplier, short lead, private floors |
| **S2** | Factory list pricing, can **expedite** for a fee |
| **S3** | Seal specialist — asks for compound before pricing |
| **Live ANP tab** | Official [`anp`](https://pypi.org/project/anp/) SDK probe ↔ ANP [Remote Test Agent](https://github.com/agent-network-protocol/anp-agent-example) |

![Architecture of the ANP Procurement Desk](./assets/10-architecture.png)
*Architecture. The person confirms and approves. The buyer searches the marketplace and bargains with S1–S3 on signed quotes. Redis and Postgres hold nonces and sessions. The buyer and the suppliers both use Amazon Bedrock. The price is already set. The Live ANP probe is isolated: its greet and echo never enter ranking.*

Stack: FastAPI roles, Redis (nonce replay), Postgres, Vite board, Docker Compose, local `*.test` DIDs, Bedrock for wording. Every quote carries a **quote hash**. Signatures are verified before a price can win. Local `*.test` DIDs demonstrate the pattern; they are not a production Web-based DID trust fabric.

![Confirm step with private target, walk-away, and bargaining rounds](./assets/02-confirm-limits.png)
*Figure 2. Before anyone is contacted, the person sets the ask and the walk-away. The walk-away is never sent to suppliers.*

**Models never write these fields** (illustrative signed quote shape):

```json
{
  "kind": "quote",
  "unit_price": 0.29,
  "lead_time_days": 5,
  "price_basis": "contract",
  "final_offer": true,
  "meets_date": true
}
```

Free-text `phrasing` can mention dollars only if they already appear in that payload. Anything else is discarded or flagged.

---

## How bargaining actually works

This is not “LLM, please negotiate.”

**Buyer policy**

- Target unit price and walk-away (per run, with sensible defaults)
- Up to **4** autonomous rounds
- Counters every live offer still above target
- Cites the **lowest signed rival** as leverage
- Stops when best ≤ target, or rounds run out
- Walk-away excludes quotes from ranking — and is never disclosed

**Supplier defense**

- Opens at the best applicable book price (list → contract → volume)
- Concedes toward a **private floor** (never disclosed)
- **Token move** when already cheapest (no lower rival cited)
- Larger concession when undercut
- **Expedite** when standard lead misses the date (premium, with its own floor)
- Declares **best and final** when it cannot move further

**Models**

- Haiku: request extraction + ranking explanation
- Nova: supplier phrasing (“We can come down from $0.31 to $0.30…”)

**Tradeoff we accepted:** an LLM negotiator would be shorter to demo and easier to overfit. A policy engine costs more code, but audit trails and injection resistance come with it.

---

## Scenario 1 — Bolts, 10 days: contract wins the rush

**Ask:** 2,000 stainless hex bolts M8×40 within **10 days**.

S1 opens on **contract** at **$0.31** (5-day lead). S2 can only make the date by **expediting** — opening near **$0.47**. The buyer counters at **$0.27**, citing rivals.

- S1: $0.31 → $0.30 → **$0.29 best and final**
- S2: $0.47 → **$0.33 best and final** (expedited)

**Winner: S1 at $0.29** — about **$40** vs the best opening on this toy catalog run (2,000 × $0.02). Signatures verified on every quote.

![Quote board after bolts 10-day bargaining — S1 leads at $0.29](./assets/03-bolts10-board.png)
*Figure 3. Opening vs final, price path, expedite badge, verified signatures, and a locked quote hash for Approve.*

![Message lanes showing counters and “Down to $X / best and final”](./assets/05-message-lanes.png)
*Figure 4. Live bargaining as numbered messages across Buyer, Marketplace, S1, and S2 — not a hidden backend log.*

---

## Scenario 2 — Bolts, 30 days: patience flips the winner

Same part. **30 days** need-by. S2 no longer needs expedite. Bargaining becomes a contest with S1’s contract price. S2 walks down to its floor and **wins near $0.28**; S1 holds near **$0.29**.

![Bolts 30-day board — S2 wins when the calendar opens](./assets/09-bolts30-board.png)
*Figure 5. Same agents, same books — different date constraint, different winner. Policy and data, not prompt luck.*

---

## Scenario 3 — Shaft seal: clarify, then defend

**Ask:** 300 shaft seals 45mm within 14 days.

All three ask for **compound**. The buyer answers **FKM** from its **spec sheet**, then bargains. The leader gives ground slowly; the undercut supplier chases harder. In our live runs, **S3** finished near **$3.38** (still above its private floor). A person still **approves** the exact hashed quote.

![Shaft seal quote board after multi-round bargaining](./assets/07-seal-board.png)
*Figure 6. Clarification → priced quotes → multi-round defense → ranked winner.*

---

## Scenario 4 — Prompt injection: quarantine, don’t argue with prose

We compromise **S3** for a demo run: injected “system” instructions and a fake **$2.10** in free text, while the **signed** unit price stays honest.

The buyer flags instruction-like text and unsigned dollars, **quarantines** S3 (no more counters, not eligible for the award), and ranks **only** on signed fields. Honest suppliers keep bargaining; **S1** wins on signed numbers.

![Prompt injection blocked — S3 quarantined, ranking unchanged by prose](./assets/08-injection-guard.png)
*Figure 7. Free text is untrusted. The banner shows what was ignored; the board shows who can still win.*

> Agent markets don’t fail on fluency — they fail when free text can rewrite the quote. We rank only what was signed.

---

## Live ANP: speaking the official protocol

Procurement lanes show the business pattern. The **Live ANP** tab shows protocol literacy.

An isolated probe uses the official **`anp` SDK** pinned at **0.4.4** to match the Remote Test Agent in this interop path (peer-matched pin — newer PyPI clients are not claimed here) and the public demo identity. It talks to the ANP team’s **Remote Test Agent** ([anp-agent-example](https://github.com/agent-network-protocol/anp-agent-example)) on a private Docker network — no desk keys, no AWS, no shared Redis with procurement.

Live result: identity loaded → agent description fetched → `greet` / `echo` listed → signed **greet** returned our DID → signed **echo** round-tripped.

![Live ANP tab — official SDK connection to Remote Test Agent verified](./assets/06-live-anp.png)
*Figure 8. Separate mode from the desk: Connect → discover → signed call → DID proof. Replies never enter ranking or models.*

We also aimed the probe at public amap on `agent-connect.ai`; that path **timed out** from our network, and `didhost.cc` returned HTML instead of DID JSON during checks. **Client interop against the official example peer is demonstrated; public host health is not.** That is the same class of proof teams use when a SaaS sandbox is flaky: clear the reference agent bar first.

---

## What scales (and what this demo does not pretend)

**Scales as a pattern:** DID identity + signed envelopes + nonce replay + quote hashes; marketplace discovery; policy for bargain / floor / expedite / quarantine; LLMs as a swappable presentation layer; human gates at confirm and approve.

**Does not yet prove:** multi-tenant SaaS / SSO; ERP write-back; that every public ANP host is always up; a formal security audit.

We showed the *contract* between agents — not that we already operate a global procurement network.

---

## Why this matters for FDEs

Forward-deployed work is where protocols meet messy reality: contract books, rush fees, missing attributes, adversarial text, flaky public demos.

1. **Numbers are owned by code**  
2. **Trust is owned by signatures**  
3. **Strategy is owned by policy**  
4. **Commitment is owned by a human**  
5. **Interop is owned by speaking the real protocol**

---

## Talk back

**Source:** [github.com/Dhivakarnath/anp-procurement-desk](https://github.com/Dhivakarnath/anp-procurement-desk) — Docker Compose desk + Live ANP probe. Protocol entry points: [ANP docs](https://agent-network-protocol.com/), [specs](https://www.agent-network-protocol.com/specs/), [getting started](https://agent-network-protocol.com/docs/anp-getting-started-guide), and the [example agent](https://github.com/agent-network-protocol/anp-agent-example).

**Comment prompt:** Would you let an LLM *propose* the counter — or only *narrate* a counter that code already computed?

---

### Tags (Medium — pick 5)

`Agent Network Protocol` · `Multi-Agent Systems` · `AI Engineering` · `Procurement` · `Trustworthy AI`

---

*Built as an AI FDE exploration of ANP for cross-company quote-to-order. Demo-grade environment; production hardening and ERP adapters are deliberate next steps — not claimed shipped.*
