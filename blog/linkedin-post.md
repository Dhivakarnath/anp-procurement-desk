# LinkedIn post (publish after the Medium article)

**Status:** FINAL — inspiring quote → build story · Medium + GitHub in the post body.

**How to post**

1. Publish the Medium article first; copy the public URL into the body below.
2. Paste the post body into LinkedIn (personal profile).
3. Attach a carousel, in this order:
   - `assets/10-architecture.png` — what the system is
   - `assets/03-bolts10-board.png` — the bargain, with prices
   - `assets/08-injection-guard.png` — free text cannot rewrite the quote
   - `assets/06-live-anp.png` — official ANP proof
4. Optional hashtags: at most one (`#AIEngineering`) — or none.

**Length target:** ~250 words · quote on line 1 · no emoji spam.

---

## Post body (copy) — FINAL

"Words can offer a price. Only a signature can bind it."

That is the rule behind the ANP Procurement Desk I built and open-sourced.

ANP (Agent Network Protocol) is how agents that do not share a login find each other, prove who they are with DIDs (Decentralized Identifiers), and sign what they send. I used it for quote-to-order.

One buyer agent. A marketplace, the only way suppliers are found. Three suppliers: S1, S2, and S3. Code owns every price, date, and rank. Claude Haiku and Amazon Nova, on Amazon Bedrock, speak for the buyer and the suppliers. A person still approves a locked quote hash.

The bargain is policy. The buyer counters with the lowest signed rival. Suppliers defend private floors: a small move when they already lead, a harder chase when they are undercut, an expedite premium when the date is tight.

I ran it:

→ Bolts, 10 days: S1 from $0.31 to $0.29
→ Same bolts, 30 days: S2 wins near $0.28
→ Shaft seals: name the compound, then defend the price
→ A $2.10 slipped into the message: S3 quarantined. The signed number won.

Then I checked whether the stack speaks real Agent Network Protocol, not only my own agents.

On the Live ANP tab, the official anp SDK reached the ANP team's Remote Test Agent: discovery, a signed greet, an echo, and a DID proof. A public amap host timed out on my path. I treated that as the host, not the protocol. The reference peer was green.

This is not a global procurement product.
It is the rail underneath one: identity, a signed quote, a policy, and a person who still commits.

Full walkthrough:
<PASTE_MEDIUM_URL_HERE>

Code:
https://github.com/Dhivakarnath/anp-procurement-desk

If you buy through agents, or you build them: what should never be allowed to change the price?

---

## Why this quote

An original line, not a borrowed motivational quote. It is short enough for the see-more fold, and the next paragraphs prove it with prices, the quarantine, and the Live ANP result. Quote posts hold up when the line is interpreted and specific, not when it stands alone.

---

## Do not

- Lead with "Excited to share…"
- Stack 5+ hashtags
- Claim production multi-enterprise ANP mesh
- Hide the public timeout — host health ≠ protocol failure
- Drop the opening quote
- Attribute commits / posts to Aivar work accounts
