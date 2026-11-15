# ANP 1.2 — Application Layer Research Notes (Agent Description, Meta-Protocol, Payments, White Paper, IETF Framework)

Source repo: `/tmp/anp-research/AgentNetworkProtocol` at commit `0837cfdf` (2026-10-23, "Remove scheduled workflow triggers"). Spec set: ANP 1.2.

Files read in full: ANP-01 white paper (release path) + vNext ANP-01 revision (sections 1–2, 5–10, App. A), ANP-06, ANP-07, ANP-08, ANP-10, `docs/agent-description-extended-fields-guide.md`, `docs/how-anp-based-webagent-works.md`, `docs/links.md`, all of `examples/adp/**` (JSON/YAML), `standard/draft-zyyhl-agent-networks-framework-00.md`, IETF124 slide decks (text extracted), and the MCP/A2A comparison blogs. Cross-checked against `message/01-core-binding.md` (P1) and ANP-02/ANP-03 where the application layer depends on them.

Conventions in these notes:
- **[SPEC]** = stated in a normative/released spec. **[DRAFT]** = draft spec. **[EX]** = example file only. **[BLOG]** = author opinion. **[GAP]** = inconsistency or missing definition an implementer must resolve.

---

## 0. TL;DR for an implementer

1. ANP-07 (Agent Description, **Released 1.2**) is the stable entry point: a plain-JSON `ad.json` with required `protocolType`, `protocolVersion`, `type`, `name`, `securityDefinitions`, `security`; optional `url`, `did`, `owner`, `description`, `created`, `Infomations` (sic), `interfaces`, `proof`.
2. Interfaces are either `NaturalLanguageInterface` or `StructuredInterface`; `protocol` values seen: `YAML` (OpenAPI 3 YAML *or* a custom ANP YAML), `openrpc`, `MCP`, `WebRTC`, `AP2/ANP`, `ANP`. Only OpenRPC has a worked example in the spec; MCP is "To be supplemented"; WebRTC has no definition.
3. Authentication is **not** what the `securityDefinitions` example suggests. `{"scheme":"didwba","in":"header","name":"Authorization"}` only describes where the *optional Bearer token* goes. The initial call is signed per ANP-02 with RFC 9421 `Signature-Input` + `Signature` (+ RFC 9530 `Content-Digest` when there is a body). The token comes back in `Authentication-Info`.
4. `humanAuthorization: true` on an interface is a *declaration* that human approval is required. It is not a credential or proof; how approval is obtained/evidenced is out of scope.
5. ANP-06 meta-protocol (**Draft**) = optional JSON-RPC control plane: `MetaProtocolInterface` in AD → `anp.get_capabilities` (from P1 Core Binding) → `anp.negotiate` (profile `anp.meta.negotiation.v1`) → `NegotiationResult` → business call. No code generation required. Old `PT=00` binary model is deprecated.
6. ANP-10 AP2 adaptation (**Draft, EN doc v1.1**) = CartMandate (merchant JWS over `cart_hash`) → user pays via QR (Alipay/WeChat) → PaymentMandate (user JWS over `[cart_hash, pmt_hash]`) → result → optional DeliveryReceipt. IntentMandate not supported. Several internal inconsistencies (alg set vs Ed25519 DID keys, `exp` 180 days vs 15 minutes, non-RFC8785 "JCS" reference code).
7. Safe to depend on: ANP-02/03/04/07/08 (released). Wrap ANP-06 and ANP-10 behind adapters/feature flags.

---

## 1. White Paper (ANP-01)

Two versions exist:
- `01-agentnetworkprotocol-technical-white-paper.md` — **Status: Informative white paper, Version 1.2** (release path). Content is the original 3-layer narrative.
- `vnext/01-agentnetworkprotocol-technical-white-paper.md` — **Status: Draft / not released, Version 1.2, revision date 2026-09-27**. Re-frames architecture as 2 core layers + domain protocols, moves meta-protocol to "optional draft". It introduces no normative requirements.

### 1.1 Vision
- Agents become the new Internet entities after mobile apps; personal AI assistants replace most apps; enterprises deploy agents; point-to-point, de-platformized personal-assistant ↔ enterprise-agent connections.
- Three problems with today's Internet for agents: **data silos/context limits**, **unfriendly (human/GUI) interfaces**, **high collaboration cost**.
- Four trends (release WP §1.2): (1) agents replace traditional software; (2) universal interconnection between agents; (3) protocol-based native connection (Computer Use / Browser Use are transitional); (4) agents self-organize and collaborate via natural-language negotiation.
- Motto: **"Connection is power."** Goal: move from platform-centric closed ecosystems to protocol-centric open ecosystems (analogy: TCP/IP, SMTP, federated email).
- vNext reframing: "the agentic web will inevitably become open", driven by **experience, cost, efficiency**. Two key cross-platform problems: **distributed context** and **adapting service invocation**. Openness = open protocols + open connections; it does NOT mean all data public or unconditional trust ("Open connections do not imply unconditional access, and identity recognition does not imply shared permissions").
- Three problems ANP solves (vNext §1.6 / README): **Interoperability**, **Native interfaces**, **Efficient collaboration**.

### 1.2 Design principles
Release WP §2:
1. **AI-Native Design** — structured data + semantics + natural language; no human simulation.
2. **Compatibility and Reuse** — wrap OpenAPI, JSON-RPC, WebRTC rather than reinvent.
3. **Composability** — DID, ADP, discovery usable independently.
4. **Simplicity and Extensibility** — small stable core, flexible schema.
5. **Pragmatic Deployability** — DNS, HTTPS, web servers, DID; no exotic infra.
6. **Principle of Least Trust** — nobody trusted by default; authenticate + authorize every interaction; minimum permissions.

vNext §2.3 restates as: AI-native; Web reuse; Composability; Natural language alongside structured expression; Minimum trust and minimum disclosure ("External content is treated as data rather than trusted instructions").

### 1.3 Layered architecture
**Release WP (3 layers, bottom→top):**
1. **Identity and Secure Communication Layer** — W3C DID, `did:wba`, E2EE (ECDHE-based in the original WP text).
2. **Meta-Protocol Layer** — natural-language negotiation of communication protocols.
3. **Application Protocol Layer** — Agent Description (ADP) + Agent Discovery.

**vNext / README (current framing, 4 parts):**
1. **Open Internet infrastructure** — HTTP, CA, DNS, CDN, Search, TLS (reused).
2. **Identity and encrypted communication layer** — DID identity ("Who are you, who am I?") + end-to-end messaging ("How can we communicate securely?").
3. **Application protocol layer** — Agent Description, Agent Discovery, agent application protocols ("What do you offer, how can I interact?" / "How can I find you?").
4. **Domain application protocols** (dashed box) — payments, authorization, authentication, transactions, verticals; independently versioned by their own ecosystems.
- Meta-protocol ANP-06 is "optional, not a mandatory step in the released architecture".

Typical first-collaboration flow (vNext Fig. 3):
```
A -> Search agent / target domain : discovery (search, or GET /.well-known/agent-descriptions)
S -> A : AD URLs
A -> B : read AD, selectively follow Information links
A      : decide locally with user's context
A -> B : invoke Interface with DID signature (ANP-02)
B      : resolve/validate A's DID doc; evaluate permissions independently
B -> A : result
A <-> B: continue via ANP messages (optional E2EE)
```
Shortcuts allowed: known contacts message directly; known interfaces invoked directly; public info read unauthenticated; no meta-protocol when interfaces suffice.

Incremental adoption (vNext §10.2):
| Goal | Required | Not required |
|---|---|---|
| Cross-platform auth on existing API | ANP-02 + one DID method | Messaging, naming, meta-protocol |
| Publish discoverable info/interfaces | ANP-07 + ANP-08 (+ANP-02 for protected interfaces) | Direct messaging, groups, payments |
| Ongoing cross-domain collaboration | ANP-09 Messaging Profiles + security modes | Unrelated domain protocols |

### 1.4 Original meta-protocol concept (release WP §3.3 — historical)
6 steps: (1) meta-protocol request in NL with candidate protocols; (2) protocol negotiation (multi-round accept/reject/counter); (3) **code generation and deployment** by each party; (4) joint testing with negotiated test data; (5) formal communication; (6) re-run on requirement change. Results cached/shared for reuse; economic incentives for sharing "still require in-depth research". Inspired by Agora (arXiv 2410.11905). **The current ANP-06 draft drops mandatory codegen** (see §3).

### 1.5 Security & privacy (release WP §4, vNext §9)
- **Human vs agent authorization**: DID Document has no `humanAuthorization` verification relationship. Low-risk ops (query public info) may be automatic per policy; high-risk ops (fund transfers, important data submissions, private info disclosure) may require explicit human authorization. Expressed via ANP-07 `humanAuthorization: true` (interface) and ANP-06 `requiresHumanAuthorization: true` (constraint only). A request signature with an `authentication` key does **not** prove a human approved.
- **Key management**: risk-based key classes; TEE/HSM; extra confirmation (biometrics, OTP, secure hardware); operation logging for sensitive signing.
- **Multi-DID strategy**: primary DID for long-term relationships; sub-DIDs per scenario (e-commerce, food delivery, online services); least privilege per sub-DID; rotation/expiry to prevent correlation.
- **Minimal disclosure**: only necessary fields; E2EE for sensitive fields; bind sessions to identity; selective-disclosure credentials encouraged.
- vNext adds: "start verification from a trusted entry point" (a `did:wba` fingerprint check passes trivially if the attacker swaps the whole DID at first contact); separate authentication / authorization / human approval; treat descriptions, messages, linked content as untrusted input (prompt injection, unauthorized invocation, SSRF into internal networks); bound traversal depth/size/time.

### 1.6 ANP vs MCP / A2A / others (per the authors)
**vNext WP §2.4 (official framing):**
> MCP primarily connects models to tools and data sources, extending agents' internal capabilities. A2A organizes task delegation and result exchange between agents around Task. For identity, both commonly reuse mechanisms such as OAuth and API keys managed by deployment operators. ANP focuses on interconnection between agents from different organizations on the open Internet... The three protocols address different layers and can complement one another: ANP authentication can supply cross-platform identity for other protocols, while MCP services or task-delegation interfaces can be published as Interfaces in agent descriptions.

vNext §5.2: "A2A focuses on asking a counterpart to complete a task... ANP focuses on available information and interfaces... Task delegation can itself be published as an Interface. **In ANP, decision-making remains with the caller.**"

**Blog positions [BLOG]:**
| Dimension | MCP | A2A | ANP |
|---|---|---|---|
| Origin | Connect models with tools/resources | Complex collaboration between agents *within enterprises* | Connection/collaboration of agents *on the Internet* |
| Architecture | Client-Server (stdio, HTTP+SSE) | P2P | P2P (HTTP core; WebSocket theoretically) |
| Worldview | Model-centric ("Internet as context") | Task-centric | Agent-centric (equal nodes) |
| Core concepts | Tools, Resources, Prompts, Sampling, Roots | Skill, Task, Artifact, Message, Part; Task states submitted/working/input-required/completed/canceled/failed/unknown | Information + Interface (NaturalLanguageInterface, StructuredInterface) |
| Interaction mode | "Remote call / full disclosure" (`tools/list`, `resources/list`) | "Task outsourcing" (`tasks/send`, `tasks/sendSubscribe`) | "Data crawling" over Linked Data; local decisions |
| Opacity | White box | Gray box | Black box |
| Identity | OAuth 2.1 + AS metadata + DCR (centralized) | OpenAPI auth schemes, out-of-band credentials | W3C DID in-band; 0-RTT auth in first request; no per-platform registration |
| Discovery | (not defined at time of writing) | `/.well-known/agent.json` (one card per domain) | `/.well-known/agent-descriptions` (list of AD URLs; many agents per domain) |
| Privacy | — | Delegating task leaks user context to remote agent | Pull data, decide locally, minimal disclosure |
| Weakness noted by authors | Stateful bidirectional → hard to scale; complexity (prompts/sampling) | Higher coupling | Native protocol lacks complex task collaboration; must model via Interfaces |

Other protocols compared (blog `Comparison-of-Agent-Communication-Protocols.md`): **Agora** (Oxford meta-protocol; ANP-06 inspiration), **agents.json** (web auxiliary standard), **LMOS** (full-stack platform), **AITP** (NEAR; interaction & transactions). Predicted "protocol fusion": MCP for tools, ANP for identity/P2P, AITP for transactions.

### 1.7 Full list of use cases / scenarios described by the authors
From release WP, vNext WP, specs, docs, and blogs:
1. **Personal AI assistant ↔ enterprise service agents** (point-to-point, de-platformized) — WP §1.2.1.
2. **Universal cross-domain context access + tool calling across the network** — WP §1.2.2.
3. **Agent reverse proxy / renting ports on a third-party platform**, which forwards E2EE traffic it cannot read — WP §3.2.
4. **Search-service agents** that index ADs (passive discovery) and **domain directories** (active discovery) — WP §3.4.2, ANP-08.
5. **AI-native data network** of text, APIs, audio/video, images — WP §3.5.
6. **Multi-DID privacy**: primary DID for friends/business partners; sub-DIDs for e-commerce shopping, food delivery, online services — WP §4.3.
7. **High-risk operations requiring human authorization**: fund transfers, important data submissions, private-info disclosure; purchase/booking interfaces — WP §4.1, ANP-07.
8. **Business trip to Shanghai** — personal agent talks to airline, hotel, map, corporate-expense agents; user confirms only at payment — vNext §1.3.
9. **Trip planning from a group chat** (friends agree on destination/budget in a messaging app; travel assistant can't see it today) — vNext §1.3.
10. **Cross-platform restaurant review reuse** — vNext §1.3.
11. "**Book me a flight to Shanghai for tomorrow**" (expect a booked ticket, not a list) — vNext §1.1.
12. **Cross-organization procurement** (full sequence: search agent → supplier ADs → local comparison against budget → E2EE messaging for lead time → approver → DID-authenticated order → present enterprise-issued procurement role VC → payment protocol → shipping documents as attachments) — vNext §10.1.
13. **Enterprise HR agent** publishing vacancies and scheduling interviews using an enterprise-issued role credential with per-transaction limits — vNext §8.3.
14. **Payments via AP2 and x402** integration — vNext §8.2, ANP-10.
15. **Vertical domain protocols** built on ANP (shared objects, state transitions, delivery evidence) — vNext §8.4.
16. **Hotel booking** (Grand Hotel, Sheraton Chuzhou) — ANP-07, `examples/adp/hotel`, ANP-06, ANP-10.
17. **Coffee ordering with customization** (Luckin Coffee) — `examples/adp/lkcoffe`, W3C CG presentation.
18. **Weather WebAgent** (`agent-weather.xyz`, query/booking/subscription-status interfaces) — `docs/how-anp-based-webagent-works.md`.
19. **E-commerce shoe purchase** via QR-code payment (AP2) — ANP-10 §10.1.
20. **OpenManus / OWL integration**: "one prompt + one HTTP function", start from `https://agent-search.ai/ad.json` to find hotels, tickets, attractions; "book a hotel in Hangzhou for April 1, 2025" — blog.
21. **IoT device agents negotiating actions**, cross-platform personal data integration, research agent communities — comparison blog.
22. **After-sales / personalization via natural-language interface** (why a coffee shop needs an NL interface, not just structured API) — W3C CG Q&A.
23. Telecom use cases (IETF): see §6.

---

## 2. ANP-07 Agent Description Protocol (Released, v1.2)

Header: `Document ID: ANP-07`, `Status: Released`, `Version: 1.2`. Applies to AD documents, interface descriptions, capability publication.

### 2.1 Interaction model ("web crawler" pattern)
- Agents connect externally provided data (files, APIs) and their descriptions into a network via URLs. Other agents, like crawlers, select and pull data to local, decide locally, and call APIs when needed.
- Stated advantages: (a) search-engine indexable, efficient agent data network; (b) pulling data to local as model context avoids privacy leakage (vs task delegation); (c) natural hierarchy scales to many agents.
- AD = entry point, "similar to a website's homepage".
- Core concepts: **Information** (text, images, video, audio, etc.) and **Interface** (APIs). Interfaces: **natural-language** (personalized) and **structured** (efficient, standardized). "If structured interfaces are available, the model should prioritize structured interfaces; if structured interfaces cannot meet user needs, natural language interfaces can be used." "**It is recommended that all agents support natural language interfaces.**"
- Format: recommends structured JSON with liberal natural language inside fields.

End-to-end crawler-style flow (from `docs/how-anp-based-webagent-works.md`):
1. `GET https://<domain>/.well-known/agent-descriptions` → CollectionPage of AD URLs (or passive search).
2. `GET ad.json` → parse `interfaces`.
3. `GET` the interface definition (OpenAPI YAML / OpenRPC JSON).
4. Build request per definition.
5. Add DID authentication (ANP-02 headers).
6. Send HTTP request.
7. Parse structured JSON/YAML response; follow further links as needed.
Public test DID for experiments: `did:wba:agent-did.com:test:public` (from `anp-examples/use_did_test_public`; test only). ANP Explorer: `https://service.agent-network-protocol.com/anp-explorer/`.

### 2.2 Full `ad.json` schema

Spec example (comments removed; copied from ANP-07):
```json
{
  "protocolType": "ANP",
  "protocolVersion": "1.0.0",
  "type": "AgentDescription",
  "url": "https://grand-hotel.com/agents/hotel-assistant/ad.json",
  "name": "Grand Hotel Assistant",
  "did": "did:wba:grand-hotel.com:service:hotel-assistant",
  "owner": {
    "type": "Organization",
    "name": "Grand Hotel Management Group",
    "url": "https://grand-hotel.com"
  },
  "description": "Grand Hotel Assistant is an intelligent hospitality agent providing comprehensive hotel services including room booking, concierge services, guest assistance, and real-time communication capabilities.",
  "created": "2024-12-31T12:00:00Z",
  "securityDefinitions": {
    "didwba_sc": { "scheme": "didwba", "in": "header", "name": "Authorization" }
  },
  "security": "didwba_sc",
  "Infomations": [
    { "type": "Product", "description": "Luxury hotel rooms with premium amenities and personalized services.", "url": "https://grand-hotel.com/products/luxury-rooms.json" },
    { "type": "Product", "description": "Comprehensive concierge and guest services including dining, spa, and local attractions.", "url": "https://grand-hotel.com/products/concierge-services.json" },
    { "type": "Information", "description": "Complete hotel information including facilities, amenities, location, and policies.", "url": "https://grand-hotel.com/info/hotel-basic-info.json" },
    { "type": "VideoObject", "description": "Hotel virtual tour showcasing rooms, facilities, dining areas, and recreational amenities.", "url": "https://grand-hotel.com/media/hotel-tour-video.mp4" }
  ],
  "interfaces": [
    { "type": "NaturalLanguageInterface", "protocol": "YAML", "version": "1.2.2", "url": "https://grand-hotel.com/api/nl-interface.yaml", "description": "Natural language interface for conversational hotel services and guest assistance." },
    { "type": "StructuredInterface", "protocol": "YAML", "humanAuthorization": true, "version": "1.1", "url": "https://grand-hotel.com/api/booking-interface.yaml", "description": "Structured interface for hotel room booking and reservation management." },
    { "type": "StructuredInterface", "protocol": "openrpc", "url": "https://grand-hotel.com/api/services-interface.json", "description": "openrpc interface for accessing hotel services and amenities." },
    { "type": "StructuredInterface", "protocol": "openrpc", "description": "OpenRPC interface for accessing hotel services.", "content": {} },
    { "type": "StructuredInterface", "protocol": "MCP", "version": "1.0", "url": "https://grand-hotel.com/api/mcp-interface.json", "description": "MCP-compatible interface for seamless integration with MCP-based systems." },
    { "type": "StructuredInterface", "protocol": "WebRTC", "version": "1.0", "url": "https://grand-hotel.com/api/webrtc-interface.yaml", "description": "WebRTC interface for real-time video communication and streaming services." }
  ],
  "proof": {
    "type": "EcdsaSecp256r1Signature2019",
    "created": "2024-12-31T15:00:00Z",
    "proofPurpose": "assertionMethod",
    "verificationMethod": "did:wba:grand-hotel.com:service:hotel-assistant#keys-1",
    "challenge": "1235abcd6789",
    "proofValue": "z58DAdFfa9SkqZMVPxAQpic7ndSayn1PzZs6ZjWp1CktyGesjuTSwRdoWhAfGFCF5bppETSTojQCrfFPP2oumHKtz"
  }
}
```

**Top-level fields (ANP-07 table, verbatim requirement levels):**
| Field | Type | Required | Meaning |
|---|---|---|---|
| `protocolType` | string | **Required** | Fixed `"ANP"` |
| `protocolVersion` | string | **Required** | ANP protocol version; "currently `1.0.0`" |
| `type` | string | **Required** | `"AgentDescription"` |
| `url` | string | Optional | Network address of the agent / AD |
| `name` | string | **Required** | Human-readable name |
| `did` | string | Optional | Agent DID |
| `owner` | object | Optional | `{type, name, url}` — e.g. `"type":"Organization"` |
| `description` | string | Optional | Functional description |
| `created` | string | Optional | ISO 8601 |
| `securityDefinitions` | object | **Required** | Map of named security schemes |
| `security` | string | **Required** | Name of the active entry in `securityDefinitions` |
| `Infomations` | array | Optional | Information resources (spelling is literal — keep it) |
| `interfaces` | array | Optional | Interfaces |
| `proof` | object | Optional | Integrity proof |

**Information object:** `type` (e.g. `Product`, `Information`, `VideoObject`), `description`, `url`. Examples also add `name` (lkcoffe). Keep detail in the linked document, not in the AD (guide).

**Interface object:**
| Field | Type | Meaning |
|---|---|---|
| `type` | string | `NaturalLanguageInterface` / `StructuredInterface` (ANP-06 adds `MetaProtocolInterface`) |
| `protocol` | string | `YAML`, `openrpc`, `MCP`, `WebRTC` (others seen: `ANP`, `AP2/ANP`) |
| `version` | string | Interface version |
| `url` | string | Interface definition document URL |
| `description` | string | Purpose |
| `humanAuthorization` | boolean | Requires human authorization (e.g. booking/payment) |
| `content` | object | (used in examples, not in the table) inline interface definition instead of `url` |

ANP-06 extension fields on interfaces (optional, draft): `id`, `profile`, `binding`, `methods`, `security` (array/string), `securityProfiles`, `negotiates`, `capabilityRefs`, `inputSchema`, `outputSchema`.

**[GAP] items in ANP-07:**
- `Infomations` misspelled; guide explicitly says keep it for compatibility. Parsers should accept `Infomations` (and tolerantly `Informations`/`informations`).
- `protocolVersion` "currently 1.0.0" (ANP-07) vs `"1.1"` in ANP-06's AD fragment. `Version: 1.2` in headers is the *document* version, not wire.
- `content` inline interface is used but not in the field table.
- `interfaces[].url` is "Address of the interface definition document" — not the endpoint.
- No `id` on interfaces in ANP-07 (ANP-06 needs it for `candidateInterfaceRefs`). Add `id` anyway; extra fields are tolerated.
- "MCP Server Interface Document Description: **To be supplemented**." WebRTC has no doc format.
- `protocol: "YAML"` is ambiguous: in examples it means either an **OpenAPI 3.0 YAML** (`search-interface.yaml`) or a **custom ANP YAML** (`interface: {type, endpoints:[...]}` in booking/purchase/nl-interface.yaml).

### 2.3 JSON-LD context
- ANP-07 v1.1+ is **plain JSON** — no `@context`, uses `type`/`url` not `@type`/`@id`. The extended-fields guide: "ANP-07 v1.1 uses standard JSON. Agent Description and Product documents use ordinary field names such as `type` and `url`." vNext WP: "draws on Linked Data's resource-and-link organization without requiring a full RDF or OWL Semantic Web stack."
- The release WP §3.4.1 and older blogs still say ADP is JSON-LD with schema.org vocabulary. Value names like `Product`, `Offer`, `PostalAddress`, `ImageObject`, `LocationFeatureSpecification`, `https://schema.org/InStock` are schema.org terms used without a context.
- **Discovery documents (ANP-08) remain JSON-LD**:
```json
{
  "@context": { "@vocab": "https://schema.org/", "did": "https://w3id.org/did#", "ad": "https://agent-network-protocol.com/ad#" },
  "@type": "CollectionPage",
  "url": "https://agent-network-protocol.com/.well-known/agent-descriptions",
  "items": [
    { "@type": "ad:AgentDescription", "name": "Smart Assistant", "@id": "https://agent-network-protocol.com/agents/smartassistant/ad.json" },
    { "@type": "ad:AgentDescription", "name": "Customer Support Agent", "@id": "https://agent-network-protocol.com/agents/customersupport/ad.json" }
  ],
  "next": "https://agent-network-protocol.com/.well-known/agent-descriptions?page=2"
}
```
- Legacy live AD (weather agent) uses JSON-LD-prefixed keys: `"@type": "ad:AgentDescription"`, `"@id"`, `"ad:securityDefinitions"`, `"ad:security"`, `"ad:interfaces"` with `"@type": "ad:StructuredInterface"`, plus `version`, `status_code`. **A production crawler should normalize both shapes** (`type`|`@type`, `interfaces`|`ad:interfaces`, strip `ad:` prefix).

### 2.4 Security: `securityDefinitions` / `security`
Spec text (ANP-07 §Security Mechanism):
- DID request auth follows ANP-02; `did:wba` and native `did:web` share the flow; other methods via ANP-02 method-binding extensions.
- `DIDWBASecurityScheme` retains WBA vocabulary; it "neither defines a new generic scheme identifier nor makes a WBA configuration a capability declaration for other DID methods."
- Secrets MUST NOT be stored in the AD. "The purpose of the AD is to describe how to access the agent (if the consumer has already been authorized), not to grant that authorization."
- `in` values: `header`, `query`, `body`, `cookie`, `uri`, `auto` (if `auto`, `name` should not be set).
- "Initial ANP-02 signatures use `Signature-Input` and `Signature`, plus `Content-Digest` when a body is present. `Authorization` carries an optional subsequent Bearer Access Token; it does not replace the initial signature."

Security scheme vocabulary:
| Term | Required | Type |
|---|---|---|
| `type` | Optional | string |
| `description` | Optional | string |
| `scheme` | **Required** | string (e.g. `didwba`) |
| `in` | **Required** | string |
| `name` | **Required** | string |

Scope/precedence: "Security configuration in the AD is required." Top-level `security` applies to all resources; resource-level `security` applies to that resource; **resource-level wins** on conflict.

[GAP] The Product example uses `security` as an **object map** (`{"didwba": {"scheme": ..., "in": ..., "name": ...}}`) rather than a string reference; ANP-06 uses `security: ["didwba_sc"]` (array). Accept string | array | object.

**ANP-02 wire mechanics the AD points to** (from `02-anp-did-authentication-protocol-specification.md`):
```
Content-Digest: sha-256=:BASE64_SHA256_DIGEST:
Signature-Input: sig1=("@method" "@target-uri" "@authority" "content-digest");created=1733402096;expires=1733402156;nonce="abc123";keyid="did:web:identity.example:alice#key-1"
Signature: sig1=:...:
```
- Must cover at least `@method` and `@target-uri` (+ `content-digest` if body).
- Server returns token in **`Authentication-Info`** (not `Authorization`): `Authentication-Info: access_token="eyJhbGciOi...", token_type="Bearer", expires_in=3600, scope="orders.read orders.write"`.
- Client then sends `Authorization: Bearer <access_token>`.
- Failures: `401` with `WWW-Authenticate: DIDWba realm="api.example.com", error="invalid_signature", error_description="...", nonce="xyz987"`; may include `Accept-Signature`. Error codes include `invalid_signature`, `invalid_content_digest`, ...

### 2.5 `humanAuthorization`
- Boolean on an interface. `true` = calling it requires human manual authorization (e.g. purchase).
- "It is not a DID verification relationship, an authorization credential, or proof that authorization has been completed." How it's obtained/evidenced = business protocol + authorization policy (ANP-05 draft, ANP-10 draft).
- Implementation implication: the **caller** must gate the call behind a user confirmation step; the **server** must enforce whatever evidence its business protocol demands (it cannot rely on the flag).

### 2.6 `proof` (integrity)
Spec text: refers to W3C VC Data Integrity (`#defn-domain`). Defined members:
- `domain` — domain where the AD is stored; consumer MUST check retrieval domain == `domain`; mismatch ⇒ possibly forged.
- `challenge` — required when `domain` is specified.
- `verificationMethod` — a verification method in the `did:wba` DID document.
- `proofValue` — signature. Generation:
  1. Build the AD without `proofValue`.
  2. Canonicalize with **JCS (RFC 8785)**.
  3. SHA-256 the canonical string.
  4. Sign the hash with the (agent's) private key; **URL-safe Base64** encode.
  5. Verify = reverse.
- Example also uses `type: "EcdsaSecp256r1Signature2019"`, `created`, `proofPurpose: "assertionMethod"`.

[GAP]
- **No `cryptosuite` field** in ANP-07. Contrast ANP-03 DID Document proofs: `type: "DataIntegrityProof"`, `cryptosuite: "eddsa-jcs-2022"`, `proofPurpose: "assertionMethod"` (mandatory for `did:wba` e1 profile). For a new deployment, using `DataIntegrityProof` + `eddsa-jcs-2022` with the DID's Ed25519 key is the most consistent choice, but ANP-07 does not mandate it; verifiers should dispatch on `type`/`cryptosuite`.
- Example `proofValue` starts with `z` (multibase base58btc style) while text says URL-safe Base64.
- Example has no `domain` despite the text.
- Text says "client's private key" — should be the AD publisher's key.
- `proof` is optional ⇒ most consumers will see unsigned ADs; TLS + DID binding are the practical integrity basis.

### 2.7 Product document (Information target)
Example `type: "Product"` with fields:
| Field | Required |
|---|---|
| `protocolType`, `protocolVersion`, `type`, `name`, `description` | Required |
| `url`, `identifier`, `brand`, `additionalProperty[]` (`PropertyValue`), `offers` (`Offer`: `price`, `priceCurrency`, `availability`, `priceValidUntil`), `amenityFeature[]` (`LocationFeatureSpecification`), `category`, `sku`, `image[]` (`ImageObject`: `url`, `caption`, `description`), `audience` (`Audience`: `audienceType`, `geographicArea`), `manufacturer` (`Organization`) | Optional |

"Common Definition Standardization": use a schema.org Product subset per product type; similarly define a unified purchase interface spec for interop. (Not yet published.)

### 2.8 OpenRPC interface document
```json
{
  "openrpc": "1.3.2",
  "info": {
    "title": "Grand Hotel Services API",
    "version": "1.0.0",
    "description": "JSON-RPC 2.0 API for hotel services including room management, booking, and guest services",
    "x-anp-protocol-type": "ANP",
    "x-anp-protocol-version": "1.0.0"
  },
  "security": [ { "didwba": [] } ],
  "servers": [ { "name": "Production Server", "url": "https://grand-hotel.com/api/v1/hotel/jsonrpc", "description": "Production server for Grand Hotel API" } ],
  "methods": [
    {
      "name": "searchRooms",
      "summary": "Search available hotel rooms",
      "params": [ { "name": "searchCriteria", "required": true, "schema": { "type": "object",
        "properties": { "checkIn": {"type":"string","format":"date"}, "checkOut": {"type":"string","format":"date"},
                        "guests": {"type":"integer","minimum":1,"maximum":8},
                        "roomType": {"type":"string","enum":["standard","deluxe","suite","presidential"]} },
        "required": ["checkIn","checkOut","guests"] } } ],
      "result": { "name": "searchResult", "schema": { "type": "object", "properties": {
        "rooms": {"type":"array","items":{"$ref":"#/components/schemas/Room"}}, "total": {"type":"integer"} } } }
    },
    { "name": "makeReservation", "params": [ { "name": "reservationData", "required": true, "schema": { "...": "roomId, guestInfo($ref GuestInfo), checkIn, checkOut, specialRequests; required roomId/guestInfo/checkIn/checkOut" } } ],
      "result": { "name": "reservationResult", "schema": { "properties": { "reservationId": {}, "confirmationNumber": {}, "totalAmount": {"type":"number"} } } } }
  ],
  "components": {
    "securitySchemes": { "didwba": { "type": "http", "scheme": "bearer", "bearerFormat": "DID-WBA", "description": "DID-WBA authentication scheme" } },
    "schemas": { "Room": { "...": "id, type, price, amenities[], availability" }, "GuestInfo": { "...": "firstName, lastName, email(format email), phone; required firstName/lastName/email" } }
  }
}
```
Required OpenRPC fields: `openrpc`, `info`, `methods`. Optional: `servers`, `components`, `security`. ANP extensions: `info.x-anp-protocol-type`, `info.x-anp-protocol-version`.
[GAP] OpenRPC example uses `securitySchemes.didwba = {type: http, scheme: bearer, bearerFormat: DID-WBA}`; the hotel OpenAPI example uses `didwba_sc = {type: http, scheme: didwba}`. Neither expresses RFC 9421 signatures accurately — pick one consistently and document it.

JSON-RPC: ANP-07 lists "JSON-RPC" interop via OpenRPC; no separate `protocol: "jsonrpc"` value is defined. ANP-06/P1 runtime messages are JSON-RPC 2.0.

### 2.9 Versioning
- Spec headers `Version: 1.2` = document release, **not** wire version (README "Versioning note").
- AD `protocolVersion` = ANP protocol version used by the document (examples `1.0.0`; ANP-06 example `1.1`).
- Interface `version` per interface; OpenRPC `info.version` + `x-anp-protocol-version`.
- Messaging/negotiation Profiles carry versions in their identifiers (`anp.core.binding.v1`, `anp.group.base.v2`, `anp.meta.negotiation.v1`).
- No AD content-negotiation, deprecation, or compatibility rules are defined. Recommendation: treat unknown fields as ignorable; reject only on missing required fields or `protocolType != "ANP"`.

### 2.10 Extended fields guide (informative; "does not add new protocol requirements")
- `domainEntity` (object, optional) — entity the agent represents; `type` e.g. `Hotel`, `CafeOrCoffeeShop`; hotel example adds `hotelID`, `address` (`PostalAddress`), `telephone`, `openingDate`, `starRating` (`Rating`), `geo` (`GeoCoordinates`), `image[]`, `amenityFeature[]`, `makesOffer[]` (`Offer` → `itemOffered: Service`); coffee example adds `openingHours: "Mo-Su 07:00-22:00"`.
- `customizationOptions` (Product, optional): `{ "type": "CustomizationOptions", "options": [ { "type": "PropertyValue", "name": "Size", "isRequired": true, "value": ["Small","Medium","Large"] } ] }`. `isRequired` is per option. Purchase interface should accept the same option names/values.
- Hotel-room Product extension fields: `roomName`, `useableArea`, `capacity`, `floor`, `bedType`, `windowType`, `pricePerDay[]`, `stockPerDay[]` (same ordered date set), `instantConfirmation`, `containedInPlace`, `smokingAllowed`, `petsAllowed`.
- Process for adding a field: check ANP-07; check the public schema (schema.org); concise non-conflicting name; document JSON type + optional/required; add example + update interface contract. Extensions stay optional; consumers that ignore them must still read identity, security, Information links, interfaces.

---

## 3. ANP-06 Agent Communication Meta-Protocol (Draft)

Header: `Document ID: ANP-06`, `Status: Draft`, `Version: 1.2`. README: "Draft; document version 1.2"; not part of the released architecture; release gated on stabilization. Wire id remains `anp.meta.negotiation.v1`.

### 3.1 Position
- **Optional.** "In normal cases, agent identity, messaging, discovery, and description protocols are sufficient." Use when agents need a pair-specific interface, temporary protocol, or special execution constraints.
- A **semantic negotiation control plane**; carries no business data.
- Does **not** define transport, session, binary headers, DID methods, auth, E2EE, the full `anp.get_capabilities` (owned by P1 Core Binding), business state machines, mandatory AI code generation / remote code loading, global registry, consensus or incentives.
- Pipeline:
```
Agent Discovery -> Agent Description -> MetaProtocolInterface -> anp.get_capabilities
  -> anp.negotiate -> selected interface / profile / security profile / schema -> business call or message exchange
```
- Problems addressed: static description can't reflect runtime changes (throttling, disabled interfaces, auth state); one intent ↔ many interfaces; caller capability affects choice; NL negotiation is expensive; old PT-header model misaligned with current stack.

### 3.2 Relationship / precedence rules [DRAFT, normative wording]
- Runs as ordinary **ANP JSON-RPC 2.0** on existing ANP endpoints with P1 conventions: `params.meta`, `params.auth`, `params.body`; `meta.profile`, `meta.security_profile`, `meta.target`; JSON-RPC `error`.
- For `anp.negotiate`, `params.meta.profile` **MUST** be exactly `anp.meta.negotiation.v1`.
- Conflict resolution order: (1) DID Document + resolution for identity and service endpoints (`ANPMessageService`); (2) `anp.get_capabilities` for runtime capability; (3) AD `MetaProtocolInterface` = hints only; (4) if static conflicts with runtime, caller **MUST** use runtime and refresh cache.
- The negotiation result is **not** an identity credential, authorization credential, access token, VC, or human-authorization result.

### 3.3 Minimum interoperability (MUST)
1. Declare `anp.meta.negotiation.v1` in runtime capabilities.
2. Handle `anp.negotiate` on negotiation-capable endpoints.
3. Recognize `MetaProtocolInterface` basic fields `type`, `profile`, `binding`, `url`, `methods`.
4. Support negotiation under `transport-protected`.
5. Return a structured `NegotiationResult`.
6. Return explicit errors for unsupported Profiles, interfaces, security profiles, content types.
7. Never treat a negotiation result as authorization for business execution.

### 3.4 `MetaProtocolInterface`
| Field | Type | Req | Description |
|---|---|---|---|
| `id` | string | SHOULD | Stable interface id (referenced by results) |
| `type` | string | MUST | `MetaProtocolInterface` |
| `protocol` | string | SHOULD | `ANP` |
| `version` | string | SHOULD | Declaration version |
| `profile` | string | MUST | `anp.meta.negotiation.v1` |
| `binding` | string | MUST | `jsonrpc-2.0` |
| `url` | string | MUST | Negotiation endpoint (static hint) |
| `methods` | array | MUST | ≥ `anp.negotiate`; usually `anp.get_capabilities` |
| `security` | array/string | MAY | Refs into `securityDefinitions` |
| `securityProfiles` | array | SHOULD | e.g. `transport-protected`, `direct-e2ee` |
| `negotiates` | array | SHOULD | Negotiable object types |
| `inputSchema` / `outputSchema` | string | MAY | Schema URIs |
| `description` | string | SHOULD | Human-readable |

`negotiates` values: `profiles`, `interfaces`, `schemas`, `security_profiles`, `content_types`, `execution_modes`, `protocol_artifacts`.

```json
{
  "id": "interface.negotiation.default",
  "type": "MetaProtocolInterface",
  "protocol": "ANP",
  "version": "1.0",
  "profile": "anp.meta.negotiation.v1",
  "binding": "jsonrpc-2.0",
  "url": "https://grand-hotel.com/anp",
  "methods": ["anp.get_capabilities", "anp.negotiate"],
  "security": ["didwba_sc"],
  "securityProfiles": ["transport-protected"],
  "negotiates": ["profiles", "interfaces", "schemas", "security_profiles", "content_types", "execution_modes"],
  "description": "Semantic meta-protocol negotiation interface for selecting the best execution interface."
}
```
Endpoint: SHOULD reuse one ANP endpoint (`https://example.com/anp`) serving `anp.get_capabilities`, `anp.negotiate`, `direct.send`, `group.send`, ...; MAY use `/anp/negotiation`.

Optional AD `capabilities` extension (ANP-06 example only; "should not be treated as a required top-level field of ANP-07"):
```json
"capabilities": [ { "id": "cap.hotel.booking", "name": "Hotel room booking",
  "description": "Book hotel rooms, modify reservations, and check room availability.",
  "intentTags": ["hotel.booking", "reservation.create", "reservation.modify"],
  "requiresHumanAuthorization": true } ]
```
Interfaces then reference them with `capabilityRefs: ["cap.hotel.booking"]`, plus `id` and `profile` (e.g. `anp.rpc.v1` for OpenRPC, `anp.direct.base.v1` for NL over messaging).

### 3.5 `anp.get_capabilities` (owned by P1 Core Binding, released)
Request:
```json
{ "jsonrpc": "2.0", "id": "req-cap-001", "method": "anp.get_capabilities",
  "params": { "meta": { "profile": "anp.core.binding.v1", "security_profile": "transport-protected",
                        "operation_id": "op-cap-001", "created_at": "2026-06-27T12:00:00Z" }, "body": {} } }
```
Response (ANP-06 fragment):
```json
{ "jsonrpc": "2.0", "id": "req-cap-001", "result": {
  "service_did": "did:wba:grand-hotel.com:e1_service",
  "supported_profiles": ["anp.core.binding.v1", "anp.meta.negotiation.v1", "anp.direct.base.v1", "anp.rpc.v1"],
  "supported_security_profiles": ["transport-protected"],
  "supported_content_types": ["application/json", "text/plain"],
  "limits": { "max_request_bytes": "1048576" } } }
```
P1 rules: MAY be anonymous (`sender_did` omitted); MAY re-call authenticated for a different subset; runtime result is authoritative; unsupported `profile`/`security_profile` MUST produce explicit error (P1 code 1002 `anp.unsupported_security_profile`); caller MUST NOT assume base profile ⇒ E2EE overlay support. P1 security profiles: `transport-protected`, `direct-e2ee`, `group-e2ee`.

### 3.6 `anp.negotiate` request
```json
{
  "jsonrpc": "2.0",
  "id": "req-neg-001",
  "method": "anp.negotiate",
  "params": {
    "meta": {
      "profile": "anp.meta.negotiation.v1",
      "security_profile": "transport-protected",
      "sender_did": "did:wba:user.example.com:agents:personal-assistant:e1_example",
      "target": { "kind": "agent", "did": "did:wba:grand-hotel.com:service:hotel-assistant:e1_example" },
      "operation_id": "op-neg-001",
      "created_at": "2026-06-27T12:00:05Z",
      "content_type": "application/json"
    },
    "auth": {
      "origin_proof": {
        "type": "anp-rfc9421-origin-proof-v1",
        "keyid": "did:wba:user.example.com:agents:personal-assistant:e1_example#key-1",
        "contentDigest": "sha-256=:BASE64URL_DIGEST:",
        "signature": "BASE64URL_SIGNATURE"
      }
    },
    "body": {
      "negotiation_id": "neg-20260627-001",
      "mode": "structured_selection",
      "intent": { "name": "book_hotel_room", "description": "Book a hotel room for two people next Friday.",
                  "intentTags": ["hotel.booking", "reservation.create"] },
      "requiredCapabilities": ["cap.hotel.booking"],
      "callerCapabilities": {
        "supportedProfiles": ["anp.core.binding.v1", "anp.direct.base.v1", "anp.rpc.v1"],
        "supportedSecurityProfiles": ["transport-protected", "direct-e2ee"],
        "supportedContentTypes": ["application/json", "text/plain"]
      },
      "constraints": { "preferredInterfaceTypes": ["StructuredInterface", "NaturalLanguageInterface"],
                       "requiresHumanAuthorization": true, "maxLatencyMs": 3000, "allowNaturalLanguageFallback": true },
      "candidateInterfaceRefs": ["interface.booking.structured.v1", "interface.conversation.nl.v1"]
    }
  }
}
```
`body` fields: `negotiation_id` (SHOULD), `mode` (SHOULD; default `structured_selection`; alt `natural_language_protocol_drafting`), `intent` (**MUST**; `name`, `description`, `intentTags` SHOULD, optional `inputSummary` e.g. `{"city":"Hangzhou","guests":2,"date":"2026-07-03"}`), `requiredCapabilities` (MAY), `callerCapabilities` (SHOULD; `supportedProfiles`, `supportedSecurityProfiles`, `supportedContentTypes`, `supportedExecutionModes`, `limits`), `constraints` (MAY; `preferredInterfaceTypes`, `requiresHumanAuthorization`, `maxLatencyMs`, `allowNaturalLanguageFallback`, `requiredSecurityProfile`, `preferredContentTypes`), `candidateInterfaceRefs` (MAY), `candidateProtocols` (MAY; NL text should not be the only machine-processable content).
Target modeling usually `agent-addressed`; service-scoped deployments MUST define target-binding rules.

[GAP] `auth.origin_proof` shape here (`type`, `keyid`, `contentDigest`, `signature`) does **not** match released P1 Core Binding, which uses `auth.scheme: "anp-rfc9421-origin-proof-v1"` and `auth.origin_proof: { contentDigest, signatureInput, signature }`. Implement P1's shape; accept ANP-06's for leniency if needed.
[GAP] Mixed casing: request `negotiation_id` (snake) vs result `negotiationId` (camel); `callerCapabilities.supportedProfiles` (camel) vs `get_capabilities` result `supported_profiles` (snake). Match exactly.
[GAP] Profile `anp.rpc.v1` is referenced in ANP-06 examples but **not defined anywhere in the repo**.

### 3.7 `NegotiationResult`
```json
{
  "jsonrpc": "2.0",
  "id": "req-neg-001",
  "result": {
    "negotiationId": "neg-20260627-001",
    "status": "accepted",
    "selected": {
      "capability": "cap.hotel.booking",
      "interface": "interface.booking.structured.v1",
      "protocol": "openrpc",
      "profile": "anp.rpc.v1",
      "securityProfile": "transport-protected",
      "contentType": "application/json",
      "url": "https://grand-hotel.com/api/booking.openrpc.json"
    },
    "execution": { "mode": "direct_structured_call", "requiresHumanAuthorization": true, "timeoutMs": 3000 },
    "schemas": {
      "requestSchema": "https://grand-hotel.com/schemas/create-booking-request.schema.json",
      "responseSchema": "https://grand-hotel.com/schemas/create-booking-response.schema.json"
    },
    "validUntil": "2026-06-27T12:10:05Z",
    "negotiationDigest": "sha-256:BASE64URL_DIGEST"
  }
}
```
| Field | Req | Notes |
|---|---|---|
| `negotiationId` | MUST | |
| `status` | MUST | `accepted` \| `rejected` \| `needs_more_information` |
| `selected` | MUST if accepted | `capability`, `interface`, `protocol` (`openrpc`/`ANP`/`MCP`), `profile`, `securityProfile`, `contentType`, `url`, optional `protocolArtifact` |
| `execution` | SHOULD | `mode` ∈ `direct_structured_call`, `direct_message`, `group_message`, `async_task`, `stream`, `natural_language`, `natural_language_protocol_drafting`; plus constraints like `requiresHumanAuthorization`, `timeoutMs` |
| `schemas` | MAY | `requestSchema`, `responseSchema` |
| `validUntil` | MAY | expiry |
| `negotiationDigest` | SHOULD | for caching/reuse/audit |
| `alternatives` | MAY | unselected options |
| `reason` | MAY | human-readable for reject/needs-more-info |

### 3.8 Negotiation state machine (derived; spec does not draw one)
```
[NoMetaInterface] --(AD lacks MetaProtocolInterface)--> use structured iface | NL iface | human | cached artifact
[Discovered] --parse AD--> [HasMetaInterface]
[HasMetaInterface] --anp.get_capabilities--> [CapabilitiesKnown]   (anonymous ok; re-call after auth)
[CapabilitiesKnown] --anp.negotiate--> one of:
    result.status=accepted            -> [Agreed] (cache keyed by target DID, caller DID/cap digest, intent digest,
                                                   interface id, selected.profile, selected.securityProfile, negotiationDigest)
    result.status=needs_more_information / error 1606 -> add info -> anp.negotiate again
    result.status=rejected / error 1600,1601 -> fallback (NL interface, natural_language_protocol_drafting if allowed, human)
    error 1607 authorization_required -> authenticate (auth.origin_proof) -> retry
    error 1603/1604/1605 -> adjust candidates -> retry (never silently weaken security)
[Agreed] --business call per selected/execution--> [Executing]
[Agreed] --validUntil passed | capabilities changed | DID doc/ANPMessageService changed |
           business call returns unsupported profile/interface/security/content type |
           policy/security/user-auth state changed--> [CapabilitiesKnown] (renegotiate)
```
Error model (JSON-RPC `error`, machine code in `error.data.anp_code`):
| code | anp_code |
|---|---|
| 1600 | `meta.negotiation_rejected` |
| 1601 | `meta.no_matching_interface` |
| 1602 | `meta.unsupported_negotiation_mode` |
| 1603 | `meta.unsupported_candidate_profile` |
| 1604 | `meta.unsupported_security_profile` |
| 1605 | `meta.unsupported_content_type` |
| 1606 | `meta.more_information_required` |
| 1607 | `meta.authorization_required` |
| 1608 | `meta.negotiation_expired` |
```json
{ "jsonrpc": "2.0", "id": "req-neg-001", "error": { "code": 1601, "message": "No matching interface",
  "data": { "anp_code": "meta.no_matching_interface", "retryable": false,
            "details": { "unsupportedConstraints": ["requiredSecurityProfile"] } } } }
```

### 3.9 How an agreed protocol is selected or generated
- **Primary path = selection**, not generation: the server picks from its own AD interfaces + runtime capabilities + local policy + auth state + caller capabilities, and returns `selected`.
- **Fallback = natural-language protocol drafting** (`mode: "natural_language_protocol_drafting"`, `constraints.allowNaturalLanguageFallback: true`) when: no structured interface satisfies intent; no shared Profile/schema; experimental temporary protocol; low-frequency/one-off/personalized task. Drafts are not stable until both accept; SHOULD convert to structured fields, schemas, examples, test cases.
- **Protocol artifacts** (reusable): `protocol_id`, `protocol_uri`, `version`, `description`, `depends_on_profiles`, `methods[]` (`name`, `request_schema_uri`, `response_schema_uri`), `content_types`, `security_profiles`, examples, test cases, `digest`, signature/publisher. Example `example.product-info.v1` with method `product.get_info`. No global registry defined.
- **0-RTT equivalent**: cache `NegotiationResult`/artifact → call directly → on explicit unsupported error → `get_capabilities` + `negotiate` again. (Old `usedProtocolHash` handshake removed.)
- Any code generation/loading is local, sandboxed, least-privilege; spec "does not require executing remote code".
- Legacy deprecated: binary `PT=00` header, `sourceHello`, `destinationHello`, `candidateProtocols`, `codeGeneration`, `testCasesNegotiation`, `fixErrorNegotiation`. New implementations **MUST NOT** implement/depend on them; no compatibility mapping.

### 3.10 Security considerations
- `anp.get_capabilities` MAY be anonymous.
- `anp.negotiate` SHOULD carry `auth.origin_proof` (or equivalent DID auth) if it includes `sender_did`, sensitive intent, user context, restricted capabilities, payment/booking/transaction/authorization/identity/privacy capabilities, non-public candidate interfaces, or identity-dependent results. Server MAY return a subset to anonymous callers, reject, or require auth.
- Results are not authorization (no user approval, no access grant, no transaction created, no long-term credential, cannot omit business-profile proofs). If selected interface has `humanAuthorization`, business flow **MUST** still complete authorization.
- Minimal disclosure: summaries only; no full payment info, identity docs, private messages, large objects; trim `callerCapabilities`; redact logs.
- **Downgrade**: MUST NOT silently downgrade security profile (e.g. requested `direct-e2ee` → must not return `transport-protected`; return explicit error).
- Artifact checks: digest, publisher/signature, schema integrity, version/deps, unsafe code/remote execution/excess permissions.
- Future: artifact JSON Schema, registries, signed negotiation results, test-case negotiation, fix-negotiation, mappings to MCP/OpenAPI/OpenRPC/A2A, multi-party negotiation, privacy profiles, governance.

---

## 4. ANP-10 Agent Payment Protocol — AP2 adaptation (Draft)

Header: `Document ID: ANP-10`, `Status: Draft / not released`, `Version: 1.1` (document revision; independent of core set). EN and CN drafts not synchronized (CN v0.1). Editorial note: metadata previously said Released; corrected to Draft. "Its presence does not establish stable interoperability, implementation conformance, or production readiness."

### 4.1 Relation to Google AP2 (Sept 2025, ap2-protocol.org)
| Aspect | Google AP2 | ANP/AP2 |
|---|---|---|
| Identity | Payment-network identity | `did:wba` |
| Comms | A2A/MCP extensions | ANP meta-protocol & message format |
| Credentials | W3C VC | **JWT/JWS** (lighter) |
| Payment methods | Cards (pull) | **QR code (Alipay/WeChat)** first |
| IntentMandate (human-not-present) | Supported | **Not supported** (planned M2) |
| Roles | 4-party (user, merchant, PP, issuer) | Merged roles allowed (M1: SA may embed CP+PP) |
| Discovery | Not defined | Via ADP |
Retained: non-repudiation via signatures, explicit user authorization, merchant signature over cart, auditable chain, minimal disclosure. Future: IntentMandate (M2), SD-JWT, W3C VC alignment, crypto/CBDC.

### 4.2 Actors
- **Shopper Agent (SA)** — buyer side; shows order; obtains user authorization; sends PaymentMandate.
- **Merchant Agent (MA)** — builds cart, creates order + QR, signs CartMandate; receives PaymentMandate; issues DeliveryReceipt.
- **Credentials Provider (CP)** — user credentials, authentication, authorization signature generation.
- **Payment Processor (PP)** — interfaces with Alipay/WeChat/bank; returns payment result.

### 4.3 Credentials ("mandates")
- **CartMandate** (MA → SA): `contents` + `merchant_authorization` (JWS) + `timestamp`.
- **PaymentMandate** (SA → MA): `payment_mandate_contents` + `user_authorization` (JWS).
- **DeliveryReceipt** (MA → SA): confirms delivery/service; **no schema defined** [GAP].
- **IntentMandate**: not supported.

CartMandate:
```json
{
  "contents": {
    "id": "cart_shoes_123",
    "user_signature_required": false,
    "payment_request": {
      "method_data": [
        { "supported_methods": "QR_CODE",
          "data": { "channel": "ALIPAY", "qr_url": "https://pay.example.com/qrcode/abc123",
                    "out_trade_no": "order_20250117_123456", "expires_at": "2025-01-17T09:15:00Z" } },
        { "supported_methods": "QR_CODE",
          "data": { "channel": "WECHAT", "qr_url": "https://pay.example.com/qrcode/abc123",
                    "out_trade_no": "order_20250117_123456", "expires_at": "2025-01-17T09:15:00Z" } }
      ],
      "details": {
        "id": "order_shoes_123",
        "displayItems": [ { "id": "sku-id-123", "sku": "Nike-Air-Max-90", "label": "Nike Air Max 90", "quantity": 1,
                            "options": {"color": "red", "size": "42"}, "amount": {"currency": "CNY", "value": 120.0},
                            "pending": null, "remark": "Please ship as soon as possible" } ],
        "shipping_address": { "recipient_name": "Zhang San", "phone": "13800138000", "region": "Beijing", "city": "Beijing",
                              "address_line": "Chaoyang District, Street 123", "postal_code": "100000" },
        "shipping_options": null,
        "modifiers": null,
        "total": { "label": "Total", "amount": {"currency": "CNY", "value": 120.0}, "pending": null }
      },
      "options": { "requestPayerName": false, "requestPayerEmail": false, "requestPayerPhone": false,
                   "requestShipping": true, "shippingType": null }
    }
  },
  "merchant_authorization": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "timestamp": "2025-08-26T19:36:36.377022Z"
}
```
(Shape mirrors W3C Payment Request API: `method_data`, `details`, `displayItems`, `total`, `options`.)

`merchant_authorization` (compact JWS, replaces legacy `merchant_signature`):
- Header: `{"alg":"RS256","kid":"MA-key-001","typ":"JWT"}` or `{"alg":"ES256K","kid":"MA-es256k-key-001","typ":"JWT"}`.
- Payload:
```json
{ "iss": "did:wba:a.com:MA", "sub": "did:wba:a.com:MA", "aud": "did:wba:a.com:TA",
  "iat": 1730000000, "exp": 1730000900, "jti": "uuid", "cart_hash": "<b64url>",
  "cnf": {"kid": "did:wba:a.com:TA#keys-1"}, "extensions": ["anp.ap2.qr.v1", "anp.human_presence.v1"] }
```
- `cart_hash = Base64URL(SHA-256(JCS(CartMandate.contents)))`, no `=` padding.
- MA signing: compute `cart_hash` → payload → header → sign → write JWS.
- Verifier: recompute `cart_hash'`; read `kid` → get MA public key "through DID document or registry"; verify JWS; check `iss/aud/iat/exp/jti`, time in `[iat, exp]`, `jti` unused; `payload.cart_hash == cart_hash'`; use `cnf` for holder verification.

PaymentMandate:
```json
{
  "payment_mandate_contents": {
    "payment_mandate_id": "pm_12345",
    "payment_details_id": "order_shoes_123",
    "payment_details_total": { "label": "Total", "amount": {"currency": "CNY", "value": 120.0}, "pending": null, "refund_period": 30 },
    "payment_response": { "request_id": "order_shoes_123", "method_name": "QR_CODE",
                          "details": { "channel": "ALIPAY", "out_trade_no": "order_20250117_123456" },
                          "shipping_address": null, "shipping_option": null, "payer_name": null, "payer_email": null, "payer_phone": null },
    "merchant_agent": "MerchantAgent",
    "timestamp": "2025-08-26T19:36:36.377022Z"
  },
  "user_authorization": "eyJhbGciOiJFUzI1NksiLCJraWQiOiJkaWQ6ZXhhbXBsZ..."
}
```
`user_authorization` payload:
```json
{ "iss": "did:wba:a.com:user", "sub": "did:wba:a.com:user", "aud": "did:wba:a.com:MA",
  "iat": 1730000000, "exp": 1730000900, "jti": "uuid",
  "transaction_data": ["<cart_hash>", "<pmt_hash>"], "cnf": {"kid": "did:wba:a.com:MA#keys-1"} }
```
`pmt_hash = Base64URL(SHA-256(JCS(PaymentMandate.payment_mandate_contents)))`.

### 4.4 Flow (4 phases, 21 steps)
1. **Cart creation**: user selects → SA `create_cart_mandate` (SKU, qty, address) → MA builds order, total, QR, computes `cart_hash`, signs → returns CartMandate.
2. **User authorization**: SA displays order + QR → user scans and pays on Alipay/WeChat → user gives SA payment proof (authorizes).
3. **Payment processing**: SA computes `transaction_data` → signs with **user private key** → `send_payment_mandate` → MA verifies both JWS + hashes → asks PP to confirm payment proof → PP result.
4. **Delivery**: success → ship/provide service, return `transaction_id`, optionally send DeliveryReceipt; failure → error.

Security table: integrity (`cart_hash`), merchant auth (RS256/ES256K), user auth (`transaction_data`), replay (`jti`), time (`iat/exp`, recommended 15 min), identity binding (`cnf` binds holder DID).

### 4.5 Message formats (HTTP POST JSON envelopes, not JSON-RPC)
`POST /ap2/merchant/create_cart_mandate` request:
```json
{ "messageId": "cart-request-001", "from": "did:wba:a.com:shopper", "to": "did:wba:a.com:merchant",
  "data": { "cart_mandate_id": "cart-mandate-id-123",
            "items": [ { "id": "sku-id-123", "sku": "Nike-Air-Max-90", "quantity": 1, "options": {"color":"red","size":"42"}, "remark": "Please ship as soon as possible" } ],
            "shipping_address": { "recipient_name": "Zhang San", "phone": "13800138000", "region": "Beijing", "city": "Beijing", "address_line": "Chaoyang District, Street 123", "postal_code": "100000" },
            "remark": "Please ship as soon as possible" } }
```
Response: `{ "messageId": "cart-response-001", "from": "<merchant DID>", "to": "<shopper DID>", "data": { "contents": {...}, "merchant_authorization": "...", "timestamp": "..." } }`.

`POST /ap2/merchant/send_payment_mandate` request: `{ messageId, from, to, data: { payment_mandate_contents, user_authorization } }`; response:
```json
{ "messageId": "payment-response-001", "from": "did:wba:a.com:merchant", "to": "did:wba:a.com:shopper",
  "data": { "status": "success", "payment_mandate_id": "pm_12345", "transaction_id": "txn_67890", "message": "Payment processed successfully" } }
```
Shopper endpoint declared: `/ap2/shopper/receive_delivery_receipt`.

### 4.6 AD binding
```json
{ "type": "NaturalLanguageInterface", "protocol": "AP2/ANP", "version": "0.0.1",
  "url": "https://grand-hotel.com/api/ap2.json",
  "description": "An implementation of the AP2 protocol based on the ANP protocol, used for payment and transactions between agents." }
```
`ap2.json`:
```json
{ "ap2/anp": "0.0.1",
  "roles": {
    "merchant": { "description": "Merchant Agent - generates cart, creates QR orders, issues delivery receipts",
                  "endpoints": { "create_cart_mandate": "/ap2/merchant/create_cart_mandate", "send_payment_mandate": "/ap2/merchant/send_payment_mandate" } },
    "shopper":  { "description": "Shopper Agent - handles user interaction, PIN validation, QR code display",
                  "endpoints": { "receive_delivery_receipt": "/ap2/shopper/receive_delivery_receipt" } } } }
```
Inline alternative: `content.roles.merchant.create_cart_mandate = { description, endpoint, item_schema }` (hotel example `item_schema` requires `hotel_id`, `rate_plan_id`, `room_num`, `check_in_date`, `check_out_date`).

### 4.7 Binding to DID auth
- Participants identified by `did:wba` DIDs (`iss`, `sub`, `aud`, `from`, `to`); public keys obtained from DID documents to verify JWS; `cnf.kid` binds holder key.
- Transport: HTTPS mandatory; DID:WBA identity authentication listed in M1 (by implication ANP-02 request signing on these POSTs).
- User private key must stay on device; HSM/secure enclave recommended.
- Extensions: `supported_methods` ∈ `QR_CODE`, `CARD`, `CRYPTO`, custom; JWT `extensions` e.g. `anp.ap2.qr.v1`, `anp.human_presence.v1`, `anp.ap2.subscription.v1`.
- M1: QR (Alipay or WeChat), CartMandate + PaymentMandate, basic sign/verify, DID:WBA. Full: multiple methods, DeliveryReceipt, role separation, refunds/disputes.
- Libraries suggested: PyJWT / jsonwebtoken, jcs, Universal Resolver, `cryptography` / WebCrypto.

### 4.8 ANP-10 [GAP] list (must resolve before production)
1. **Algorithm mismatch**: JWS algs are RS256/ES256K, but `did:wba` default `e1_` keys are Ed25519 (EdDSA, `eddsa-jcs-2022`). Either add `EdDSA` or require secp256k1/RSA verification methods in the DID doc.
2. `kid` examples (`MA-key-001`) are not DID URLs, yet verification resolves keys via DID document. Use `kid = <DID>#<key-id>`.
3. `exp` "recommended 180 days" (merchant field list) vs 15 minutes (security table, §7.2, reference code `ttl_seconds=900`).
4. `aud: did:wba:a.com:TA` — "Transaction Agent/TA" is not a defined role.
5. User `cnf.kid` points at the **merchant** key, which is semantically odd for holder binding.
6. Reference "JCS" in Python is `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False)` — **not RFC 8785** (number formatting, e.g. `120.0`, differs). Use a real JCS library on both sides.
7. DeliveryReceipt has no schema; refunds/disputes undefined.
8. Interface `type` is `NaturalLanguageInterface` although endpoints are structured.
9. Envelope (`messageId/from/to/data` over POST) is unrelated to P1 JSON-RPC Core Binding and ANP-06; "meta-protocol layer" positioning is aspirational.
10. User pays by QR before PaymentMandate: PaymentMandate is effectively an attestation of a completed push payment; MA must verify with PP (`out_trade_no`). `user_signature_required` semantics undefined.
11. White paper vNext says ANP "integrates with payment protocols such as AP2 and x402 rather than defining a complete payment system".
Blog context: the ANP community's earlier (May 2025) transaction design used **W3C VCs linked by hash chain**, an **escrow payment agent** (Alipay-style), notary/arbitration agents for disputes; AP2 instead uses a user-side Credentials Provider.

---

## 5. Example ADs in `examples/adp/`

Tree:
```
hotel/examples/ad.json
hotel/examples/hotel_room.json
hotel/examples/api/booking-interface.yaml   (custom ANP YAML)
hotel/examples/api/nl-interface.yaml        (custom ANP YAML, SSE)
hotel/examples/api/search-interface.yaml    (OpenAPI 3.0.0)
lkcoffe/ad.json
lkcoffe/api/purchase-interface.yaml         (custom ANP YAML)
lkcoffe/api/nl-interface.yaml               (custom ANP YAML, SSE)
lkcoffe/{silk-latte,orange-americano,roasted-coconut-latte}/*.json  (Product docs) + instruction.jp(e)g images
```
No OpenRPC example file exists in `examples/adp` (OpenRPC is only in ANP-07 text).

### 5.1 Hotel AD (`hotel/examples/ad.json`) — structure
```json
{
  "protocolType": "ANP", "protocolVersion": "1.0.0", "type": "AgentDescription",
  "url": "https://service.agent-network-protocol.com/agents/sheraton-chuzhou-hotel/ad.json",
  "name": "Hotel Booking Agent",
  "did": "did:wba:service.agent-network-protocol.com:wba:hotel",
  "owner": { "type": "Organization", "name": "Hotel Chain Group", "url": "https://example-hotel-group.com" },
  "description": "An intelligent hotel booking agent providing comprehensive hotel information, room availability, and booking services.",
  "created": "2025-01-29T09:08:44Z",
  "securityDefinitions": { "didwba_sc": { "scheme": "didwba", "in": "header", "name": "Authorization" } },
  "security": "didwba_sc",
  "domainEntity": { "type": "Hotel", "hotelID": 372505161, "name": "滁州港汇喜来登酒店", "description": "...",
    "url": ".../hotel.json", "address": { "type": "PostalAddress", "streetAddress": "中都大道1599号", "addressLocality": "滁州", "addressRegion": "安徽省", "addressCountry": "CN" },
    "telephone": "0550-2201888", "openingDate": "2015",
    "starRating": { "type": "Rating", "ratingValue": 5, "alternateName": "豪华型", "isRelatedTo": true },
    "geo": { "type": "GeoCoordinates", "latitude": 32.242098, "longitude": 118.332009 },
    "image": [ { "type": "ImageObject", "url": "...", "caption": "...", "description": "..." } ],
    "amenityFeature": [ { "type": "LocationFeatureSpecification", "name": "健身室", "value": true } ],
    "makesOffer": [ { "type": "Offer", "itemOffered": { "type": "Service", "name": "24小时前台服务" } } ] },
  "Infomations": [ { "type": "Product", "description": "Hotel room details, rates, availability, and booking conditions.",
                     "url": "https://service.agent-network-protocol.com/agents/hotel/examples/hotel_room.json" } ],
  "interfaces": [
    { "type": "StructuredInterface", "protocol": "YAML", "version": "1.0.0", "url": ".../api/search-interface.yaml",
      "description": "A YAML file for searching and filtering hotel information, such as room information, price information, etc." },
    { "type": "StructuredInterface", "protocol": "YAML", "version": "1.0", "humanAuthorization": true, "url": ".../api/booking-interface.yaml",
      "description": "A YAML file for hotel room booking and reservation management." },
    { "type": "NaturalLanguageInterface", "protocol": "YAML", "version": "1.0", "url": ".../api/nl-interface.yaml",
      "description": "A YAML file for interacting with the intelligent agent through natural language." }
  ]
}
```
No `proof`. Note interface URLs use path `/agents/sheraton-chuzhou-hotel/api/...` but endpoint paths inside YAMLs use `/agents/hotel/api/...` [EX inconsistency].

Hotel room Product (`hotel_room.json`): `identifier: "room-deluxe-001"`, `roomName`, `name`, `description`, `category: "Hotel Room"`, `useableArea`, `capacity: "3"`, `floor: "15-20"`, `bedType`, `windowType`, `image[]`, `offers` = `{ type: Offer, identifier: "RP20250204001", name: "标准价", priceSpecification: { type: UnitPriceSpecification, price: 1280.00, priceCurrency: CNY, unitCode: DAY, priceType: https://schema.org/InvoicePrice, valueAddedTaxIncluded: true }, pricePerDay: [1280,1280,1280], stockPerDay: [5,4,3], paymentMethod: { type: PaymentMethod, name: "Prepayment required" }, instantConfirmation: true, addOn: { type: Offer, name: Breakfast }, priceValidUntil, eligibleCustomerType, availability, businessFunction: http://purl.org/goodrelations/v1#LeaseOut, seller, termsOfService: { cancelationPolicy: { type: CancellationPolicy, refundType: "Full refund", validUntil } } }`, `amenityFeature[]`, `containedInPlace` (Hotel + PostalAddress), `smokingAllowed: false`, `petsAllowed: false`.

`search-interface.yaml` (OpenAPI 3.0.0):
```yaml
openapi: 3.0.0
info: { title: Hotel Room Search Interface, version: "1.0.0", license: { name: Apache-2.0 } }
servers: [ { url: https://service.agent-network-protocol.com } ]
security: [ { didwba_sc: [] } ]
paths:
  /agents/hotel/api/search:
    post:
      operationId: searchHotelRooms
      requestBody: { required: true, content: { application/json: { schema: { type: object,
        properties: { checkInDate: {type: string, format: date}, checkOutDate: {type: string, format: date} },
        required: [checkInDate, checkOutDate] } } } }
      responses:
        '200': { content: { application/json: { schema: { type: object, properties: {
                   urls: { type: array, items: {type: string, format: uri} },        # URLs to ANP Product docs
                   data: { type: array, items: { $ref: '#/components/schemas/HotelRoom' } } },
                 anyOf: [ {required: [urls]}, {required: [data]} ] } } } }
        '400': { description: The check-in or check-out date is missing or invalid. }
components:
  securitySchemes: { didwba_sc: { type: http, scheme: didwba, description: DID-WBA authentication using the Authorization header. } }
  schemas: { HotelRoom: { required: [protocolType, protocolVersion, type, url, identifier, name, description, offers], ... } }
```
Pattern worth reusing: **search returns either Product URLs (link-following) or inline Product objects.**

`booking-interface.yaml` (custom):
```yaml
interface:
  type: Booking
  description: "用于预订指定的商品或服务"        # book a specified product/service
  version: "1.0"
  endpoints:
    - name: "Booking"
      method: "POST"
      path: "/agents/hotel/api/booking"
      parameters:
        - { name: "identifier", type: "string", required: true, description: "identifier of the product in its description doc" }
```
`nl-interface.yaml` (custom; same shape for lkcoffe at `/agents/lkcoffe/api/ask`):
```yaml
interface:
  type: NaturalLanguage
  version: "1.0"
  endpoints:
    - name: "askQuestion"
      method: "POST"
      path: "/agents/hotel/api/ask"
      parameters: [ { name: "question", type: "string", required: true } ]
      response: { type: "string", description: "natural-language answer, SSE supported" }
      sseSupport: true
      sseDescription: "Supports Server-Sent Events for real-time NL streaming."
```

### 5.2 Coffee AD (`lkcoffe/ad.json`)
- `name: "Luckin Coffee Agent"`, `did: "did:wba:service.agent-network-protocol.com:wba:lkcoffe"`, `created: "2025-01-03T10:56:57Z"`, same `securityDefinitions`.
- `domainEntity`: `CafeOrCoffeeShop`, `PostalAddress`, `telephone`, `url`, `openingHours: "Mo-Su 07:00-22:00"`, `geo`.
- `Infomations`: 3 Products each with `type`, `name`, `description`, `url` (silk-latte, orange-americano, roasted-coconut-latte).
- `interfaces`: `NaturalLanguageInterface` (YAML, nl-interface.yaml) + `StructuredInterface` (YAML, `humanAuthorization: true`, purchase-interface.yaml).

`purchase-interface.yaml`:
```yaml
interface:
  type: Purchase
  description: "购买指定的商品或服务"            # purchase a specified product/service
  version: "1.0"
  endpoints:
    - name: "purchase"
      method: "POST"
      path: "/agents/lkcoffe/api/purchase"
      parameters:
        - { name: "identifier", type: "string", required: true, description: "product identifier from the description doc" }
        - name: "customizationOptions"
          type: "object"
          required: true
          description: "user's chosen customization options"
          additionalProperties: { type: "string", description: "key = option name, value = chosen value" }
```
Product (silk-latte): `identifier: "sl-29ab8cf9"`, `brand`, `additionalProperty[]`, `offers: {type: Offer, price: "20", priceCurrency: CNY, availability: InStock}`, `image[]`, `audience`, `manufacturer`, `customizationOptions.options[]` (`杯型` size, `咖啡豆` bean, `温度` temp, `糖度` sweetness; each `isRequired: true`, `value: [...]`). Roasted coconut latte adds `nutrition` (`NutritionInformation`), `ingredients`, `category`, `sku: "LK-COCONUT-LATTE"`.
Purchase request implied by the docs: `{"identifier": "sl-29ab8cf9", "customizationOptions": {"杯型": "大杯", "咖啡豆": "IIAC金奖豆", "温度": "冰", "糖度": "少甜"}}`.

### 5.3 Legacy weather AD (docs) — JSON-LD variant
```json
{ "@context": { "@vocab": "https://schema.org/", "did": "https://w3id.org/did#", "ad": "https://agent-network-protocol.com/ad#" },
  "@type": "ad:AgentDescription", "@id": "https://agent-connect.ai/agents/travel/weather/ad.json",
  "name": "Weather Agent", "version": "1.0.0",
  "owner": { "@type": "Organization", "name": "agent-connect.ai", "@id": "https://agent-connect.ai" },
  "ad:securityDefinitions": { "didwba_sc": { "scheme": "didwba", "in": "header", "name": "Authorization" } },
  "ad:security": "didwba_sc",
  "ad:interfaces": [ { "@type": "ad:StructuredInterface", "protocol": "YAML", "url": ".../weather-info.yaml", "description": "OpenAPI YAML file providing weather query services." },
                     { "@type": "ad:NaturalLanguageInterface", "protocol": "YAML", "url": ".../nl-interface.yaml" } ],
  "status_code": 200, "url": "https://agent-connect.ai/agents/travel/weather/ad.json" }
```

---

## 6. IETF draft `draft-zyyhl-agent-networks-framework-00` ("Framework for AI Agent Networks")

- Category: info; Network Working Group. Authors: Y. Zhou (ANP Open Source Community), K. Yao (China Mobile), M. Yu (China Telecom), M. Han (China Unicom), C. Li (Huawei). Repo has `-00` source; IETF124 deck shows **`-01` published 20 Oct 2025, expires 23 Apr 2026, Informational**. Baseline: ANP.
- References `I-D.stephan-ai-agent-6g`, W3C DID 1.1, VC Data Integrity.

### 6.1 Problem statement & scope
- Multi-agent collaboration needs standardized protocols for wide-area interconnection, cross-domain interoperability, secure collaboration.
- Agent types by deployment: **terminal-side**, **network-side**, **outside the network**. Scope = agents managed **within an operator's network / single trust domain**: terminal↔terminal, terminal↔network, network↔network in the same network service domain. **Cross-domain is out of scope.**

### 6.2 Terms and roles
- Task, Task chain (ordered set of tasks, may branch), Coordinator Agent, Execution Agent.
- Roles: **AI Agent**; **Agent Registration Server (ARS)** — register capabilities, discover by intent/task; **Agent Communication Server (ACS)** — session management and routing.
- Flow: (A) B registers capabilities at ARS; (B) ARS authenticates/stores; (C) A sends discovery with intent/task; (D) ARS returns matched agents. Option 1: (E–H) via ACS (session establishment + routing). Option 2: (E'/F') direct.

### 6.3 Requirements / functions
- **Digital identifier** used across registration, discovery, communication, authentication, authorization ("AI agent communication needs to be explicitly authorized at all time"; attribute-based authZ supports direct, delegated, and user authorization). Suggests **W3C DID + VC** (VC as container of agent attributes from multiple sources).
- **Agent Description**: NL format or structured (JSON, JSON-LD, others). Information (text/image/video/audio/other files) and Interface (NL / Structured). Security **mandatory**, global vs resource scope, resource-level precedence. Integrity **Proof** per VC Data Integrity.
- **Registration**: *Self-Declaration Mode* (linked data ADs; same three advantages as ANP-07) and *Centralized Registration Mode* with params: Name, Digital Identifier (global unique, network-provider configured), Description, Address (URL/FQDN), Version, Capabilities (communication protocols e.g. http/2, http/3, A2A, ANP, MCP; interaction modes request-response, subscription-notification; multimodal: text, images, video, real-time audio), Services (AI, sensing, computing), Skills (name, ID, services, abstract, required input), Interfaces, Security info (licenses, credentials, keys).
- **Discovery**: *Proactive* (crawl ADs via search engines, ethical crawling) and *Centralized Query* (query matching + result feedback). Structured query examples: "Medical image analysis", "Within 1 kilometer of base station BS-001", "Latency ≤ 100ms", "Medical qualification VC is required". Result list has Digital Identifier, Address, Capabilities.
- **Tasks**: agree "what to do"; global unique task ID created by assigner; task chains across agents; short-term vs long-term tasks; states maintained by execution agent and synced; protocol MUST consider ACS forwarding; ACS SHOULD prioritize per task QoS; context sharing (contact info, history preferences, recent dialog) with standardized context types, length, encoding.
- **Message modes**: P2P direct / indirect (ACS does access control, application-layer proxy for audit/identity hiding, relay for cross-domain, traffic aggregation, auth + relaying); Group; PUB/SUB.
- **Multimodality**: text, file, document, image, structured data, real-time A/V; modality-aware differentiated policies (separate transport streams or priorities).
- **Session management**: authenticate to ACS; ACS keeps agent states; globally unique Session ID; session table; or direct after authN/Z (control/data plane split); QoS requirements at session setup.
- **Routing**: ID-based lookup (direct: ID→IP; indirect: ACS; group: ACS) and semantic-based resolution (semantic search for capability/attribute → IDs).
- **Protocol stack**: AI Agent Comm Protocol Layer (JSON-RPC, JSON-LD) over application layer (HTTP, SIP) over transport (UDP, TCP, QUIC). App layer SHALL: full-duplex bidirectional multimodal; decoupled from presentation (JSON-RPC MUST be carriable over HTTP, WebTransport, etc.); flexible routing (URL/DNS and DID-segment routing); extension mechanism. Transport SHALL: mobile QoS adaptation; multipath (MPTCP, MPQUIC); mobility (move unfinished packets / backup link).
- **Security considerations** (not detailed): identity (SIM-based robots vs certificate-based assistants), reuse trusted-domain primary authentication (agent ↔ core network), authorization (OAuth today; direct/delegated/user), cross-domain security next, discovery privacy (owner approval to publish), task privacy (task description minimization, context-sharing limits for name/age/address).
- IANA: TBD. Conclusion: single-trust-domain framework; cross-domain needs further work.

### 6.4 Telecom use cases (IETF124 materials in `standard/IETF124/`)
**China Telecom — "AI Agents Communication Use Cases and Requirements (v3)":**
- 3GPP SA1 TR 22.870: 21+ agreed AI-agent use cases, 63+ potential requirements; agent types On-device, Application, Network AI Agents. Four categories:
  1. *Intent-based 6G services by network AI agents*: on-demand networking, intelligent calling, disaster-rescue planning, network performance assurance, customized service provisioning, network-native assistance for autonomous driving, AI-optimized smart call assistance. Worked example: "Concert AR Smart Interaction" app declares intent → capability-exposure agent parses/decomposes → service-customization agent collects data (user profiling, network quality) → results to app.
  2. *Device-network collaboration*: 6G-assisted agent service, smart housekeeping, child health assistant, UE-network coordination, proactive personal-safety agent, shared embodied agents.
  3. *Multiple devices collaboration*: collaborative agents, agent communication, authN/authZ for agents, data collection/fusion.
  4. *Network-application collaboration*: intelligent communication assistant, 6G agent + third-party LLM, network knowledge as RAG, agent management.
- **Semantic Routing (SemR)**: route by service identity, API version, user context, intent; components Identity / Policy / Telemetry; control plane (Agent Capability Registration, Intent Discovery Service, Global Policy Engine), data plane (Service Router, Local Routing Decision Unit), feedback (Task Success Monitoring, RL Module). Requirements summary: framework, agent identity, efficient collaboration, registration/discovery, semantic routing, security (data protection, user consent). Refs: draft-yu-ai-agent-use-cases-in-6g, draft-tong-network-agent-use-cases-in-6g, draft-li-semantic-routing-architecture.

**China Mobile — "Telecom AI Agent Use cases and Requirements":**
- Agent types: in Apps (OTT/operator/third party), in UEs (phone/robot vendors), in network (operator/OTT); tool types: application tools, network tools.
- Ownership roles: **OBO user**, **OBO agent itself**, **OBO other agent(s)**. Domains: task-wise (temporary, e.g. created by 6G) vs application (durable).
- Use cases: **Trip planning (OBO user)** with payment — MUST support HITL; MUST define risk levels (HITL required / whitelist / confirm-then-whitelist). **Health care (OBO other agent)** — wards' smart watches → guardian agent → hospital APIs; MUST define scope/boundaries for delegated authorization. **Remote rescue (OBO itself)** — robot dog, robot arm, UAV in task-wise domain over mobile core; MUST support real-time + reliability, dynamic groups, group life-cycle.
- Core-network applicability: identity registration/issue/discovery (UDM, UDR, SMF); authN/Z (AUSF, SMF); HITL redirection (PCF, NEF, UPF); dynamic group & real-time (AMF, SMF). "Not limited to A2A, also open to MCP, ANP."

**China Unicom — "Multi-Access Collaboration Requirements for AI Agent Protocol" (draft-liu-access-collaboration-agent):**
- Scenarios: **Home security** (UE agent ↔ home cameras/NAS/printers/pet sensors via agent gateway), **Remote work** (terminal agents ↔ cloud desktop, printers, video conferencing, file servers), **Fixed-mobile hybrid access** (handover between home ONT/enterprise router agents and mobile network).
- Requirements: identity authentication + request verification (certificates, mutual auth); **agent discovery and automatic negotiation** on joining a network; connection stability + seamless handover (session persistence, possible identity transformation); local disaster recovery / offline processing with later sync.

---

## 7. Status summary: Released vs Draft, and what's safe to depend on

| Document | Status (per header/README) | Wire identifiers / versions | Safe for production? |
|---|---|---|---|
| ANP-01 White Paper (release path) | Informative v1.2 | — | Context only; not normative |
| ANP-01 vNext revision | Draft / not released (rev 2026-09-27) | — | Context; best current architecture narrative |
| ANP-02 DID Authentication | **Released v1.2** | RFC 9421 `Signature-Input`/`Signature`, RFC 9530 `Content-Digest`, `Authentication-Info`, `WWW-Authenticate: DIDWba` | **Yes** — foundation for all protected interfaces |
| ANP-03 did:wba method | **Released v1.2** | `e1_` Ed25519, `DataIntegrityProof` + `eddsa-jcs-2022` | **Yes** |
| ANP-04 WNS naming | **Released v1.2** | Handles | Yes if naming needed |
| ANP-05 DID-based authorization (OAuth CIMD / VC) | Draft v0.7, outside 1.2 | — | No; design against it but isolate |
| ANP-06 Meta-protocol | **Draft** (doc v1.2) | `anp.meta.negotiation.v1`, `anp.negotiate`, `MetaProtocolInterface`, errors 1600–1608 | **No** — optional; known inconsistencies (origin_proof shape, `anp.rpc.v1` undefined, casing). Implement behind a feature flag if at all |
| ANP-07 Agent Description | **Released v1.2** | `protocolType: "ANP"`, `protocolVersion` (e.g. `1.0.0`), `type: AgentDescription` | **Yes** — required fields, Information/Interface model, `securityDefinitions`/`security`, `humanAuthorization` semantics. Treat `proof` format, MCP/WebRTC interface docs, and the custom YAML interface format as under-specified |
| ANP-08 Agent Discovery | **Released v1.2** | `/.well-known/agent-descriptions`, JSON-LD `CollectionPage`, `items[].@id`, `next` | **Yes**. Passive registration API is search-service-defined (not standardized) |
| ANP-09 Messaging (P1–P9) | Published v1.2 catalog; **P6 Group E2EE candidate** (MLS code point `0xF0A1` provisional) | `anp.core.binding.v1`, `anp.direct.base.v1`, `anp.group.base.v2`, `anp.direct.e2ee.v2`, ... | Yes except P6. `anp.get_capabilities` (P1) is released and usable independently of ANP-06 |
| ANP-10 AP2 Payment adaptation | **Draft / not released** (EN v1.1, CN v0.1) | `AP2/ANP` `0.0.1`; `/ap2/merchant/create_cart_mandate`, `/ap2/merchant/send_payment_mandate` | **No** — internally inconsistent (algs, exp, JCS, DeliveryReceipt). Use as a design reference; consider upstream AP2 or x402 adapters |
| Extended-fields guide | Informative; "does not add new protocol requirements" | `domainEntity`, `customizationOptions`, hotel-room fields | Optional conventions; fine to adopt |
| `examples/adp/*` | Illustrative | — | Patterns only (some path inconsistencies) |
| IETF `draft-zyyhl-agent-networks-framework` | Individual I-D, Informational (-00 in repo; -01 Oct 2025) | — | Requirements/context only |

### 7.1 Practical recommendations for a production ANP project
1. **Publish**: `/.well-known/agent-descriptions` (JSON-LD CollectionPage, paginate with `next`) → per-agent `ad.json` (plain JSON, all required fields; add `id` to every interface; prefer OpenAPI 3 or OpenRPC for structured interfaces; always include a NaturalLanguageInterface; mark booking/payment interfaces `humanAuthorization: true`).
2. **Auth**: implement ANP-02 server middleware (RFC 9421 verify, `Content-Digest`, nonce/`created`/`expires` replay window, DID resolution with caching, `Authentication-Info` token issuance, `WWW-Authenticate: DIDWba` errors). Keep `securityDefinitions` as the WBA example for compatibility.
3. **Crawler/client**: tolerant AD parser (plain JSON + legacy JSON-LD `ad:` keys; `Infomations` spelling; `security` as string/array/object); bounded traversal (depth, bytes, time); domain checks (AD URL vs `did` domain vs `proof.domain`); treat all fetched text as untrusted data (prompt-injection defenses); prefer structured interface, fall back to NL.
4. **Human authorization**: caller-side confirmation UX + server-side evidence check defined by your business protocol (ANP gives only the flag).
5. **Integrity**: if signing ADs, pick a single documented scheme (recommend `DataIntegrityProof` + `eddsa-jcs-2022` with the agent DID key, plus `domain` and `challenge`), and verify by `type`/`cryptosuite` dispatch.
6. **Meta-protocol**: if needed, implement P1 `anp.get_capabilities` first; add `anp.negotiate` as a pure selection service over your AD interfaces with cached `NegotiationResult` (`validUntil`, `negotiationDigest`); no remote code execution; refuse silent security downgrades.
7. **Payments**: isolate behind a payment adapter; if following ANP-10, fix the gaps (EdDSA support or DID keys matching JWS alg; DID-URL `kid`; 15-minute `exp`; real RFC 8785 JCS; persistent `jti` store; PP verification of `out_trade_no`; define DeliveryReceipt).
8. **Versioning**: emit `protocolVersion` deliberately (examples use `1.0.0`); version each interface; never infer wire versions from document `Version: 1.2`.
