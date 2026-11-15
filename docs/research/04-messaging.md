# ANP Messaging 1.2 — Implementation Notes (End-to-End Instant Messaging Suite)

Source: `/tmp/anp-research/AgentNetworkProtocol` (ANP-09 overview + `message/01..09` + `message/README.md` + `examples/message-vnext/`).
Purpose: implementation-grade reference for building a spec-conformant `ANPMessageService`.
Conventions in these notes: "§" refers to the section numbering of the cited Profile document. Quoted JSON is copied from the spec unless marked "(derived)".

---

## 0. Spec set / Profile map

| Profile | Wire identifier | Doc | Status | Responsibility |
|---|---|---|---|---|
| P1 | `anp.core.binding.v1` | 01-core-binding.md | Released | JSON-RPC envelope, `meta/auth/body`, capability negotiation, idempotence, shared errors, Origin Proof (App. A), Object Proof (App. B) |
| P2 | `anp.identity.discovery.v1` | 02-identity-and-discovery.md | | DID semantics, `ANPMessageService`, `deviceManifest`, discovery |
| P3 | `anp.direct.base.v1` | 03-direct-messaging-base-semantics.md | | DID-to-DID ordinary direct message (`direct.send`) |
| P4 | `anp.group.base.v2` | 04-group-messaging-base-semantics.md | | DID-only group membership, governance, `group.send`, Host ordering |
| P5 | `anp.direct.e2ee.v2` | 05-direct-end-to-end-encryption.md | | Device-bound PreKey / X3DH-like / Double-Ratchet-like |
| P6 | `anp.group.e2ee.v2` | 06-group-end-to-end-encryption.md | **Candidate** (gated on registered MLS ExtensionType; provisional `0xF0A1`) | MLS group E2EE, per-device leaves |
| P7 | `anp.attachment.v1` | 07-attachments-and-object-transfer.md | | Attachment manifest, Object Service, tickets, object-e2ee |
| P8 | `anp.federation.relay.v1` | 08-federation-and-cross-domain.md | | Cross-domain direct service-to-service calls, Host ordering, success semantics |
| P9 | "v1 binding extension" (mentions) | 09-message-mentions.md | | Structured mentions / selectors for group messages |

Dependency chains (README §2):
```text
anp.direct.e2ee.v2 -> anp.core.binding.v1 -> anp.identity.discovery.v1 -> anp.direct.base.v1
anp.group.e2ee.v2  -> anp.core.binding.v1 -> anp.identity.discovery.v1 -> anp.group.base.v2
```

Key shared decisions (README §5), paraphrased:
1. Agent DID = wire identity and address for Base messaging. `device_id` is an opaque, Profile-owned cryptographic endpoint selector (P5/P6 only); never a Device DID, member, role, hardware ID, or `target.kind`.
2. `deviceManifest` = complete current public device set, embedded in the method-validated DID Document; no separate endpoint/proof/epoch/hash/CAS. Required only for DIDs advertising device-addressed security Profiles.
3. Manifest entry contains only `device_id`, `signing_key_id`, `e2ee_key_id`, `profiles[]`.
4. P3, P4, P7 ordinary flows, P9 payloads **MUST NOT** require or carry `sender_device_id`, `recipient_device_id`, `requester_device_id`.
5. Proof schemes unchanged: `anp-rfc9421-origin-proof-v1` + W3C Data Integrity (`eddsa-jcs-2022`).
6. No `document_version` / `document_hash` / checkpoint on the wire — re-resolve DID Document when eligibility may have changed.
7. Per-device private keys / PreKeys / ratchet / MLS state / replay state never copied between devices.
8. A device removed from `deviceManifest` can never be restored with the same `device_id` or keys (re-enroll with new ID + keys).
9. P6 uses provisional private-use MLS ExtensionType `0xF0A1` (not IANA); stable code point is a release gate.
10. New requests omit deprecated `meta.anp_version`; receivers MUST NOT use it to select a Profile.
11. Wire identities are complete DIDs; human-readable names are out of scope.
12. DID transitions: start from previously trusted DID, verify the registered transition chain; `alsoKnownAs` alone does not authorize continuity.
13. P4 v2 stores only current member DID; accepted DID transitions update the record and emit `member-did-updated`; history not rewritten.
14. DID request auth follows ANP-02; message binding follows P1; DID method validation follows P2. `did:wba` and `did:web` use identical message rules.

Versioning (README §4, P1 §11-12): Profile wire IDs carry **major only** (`.v1`, `.v2`), never `.v1.2`. Major bump on: new required wire field, field removal/rename, changed meaning, changed signature/AAD coverage, changed idempotency key or state machine, changed security-mode semantics. MUST NOT infer P5/P6 v2 from v1, synthesize a device for a v1 peer, or silently downgrade v2 E2EE to v1 or to transport-protected Base.

---

## 1. Overall architecture (ANP-09 + P1 + P2 + P8)

- **Federated** (email-like). Each Agent / group may live in different domains. Services discover each other via DID Documents and call each other **directly** with the original business method (no separate relay wrapper protocol).
- **Direct**: the ingress service of the *target Agent's domain* receives; cross-domain success = acceptance by target Agent ingress service.
- **Group**: the **Group Host Service** orders group state and serializes group events; cross-domain success = Group Host acceptance and sequencing.
- **Control plane vs data plane**: control = group create/join/add/remove, capability negotiation, ticket issuance, cross-domain invocation; data = direct/group messages and attachment bytes. Attachment bytes travel over a separate HTTP(S) channel; messages carry only a manifest; the cross-domain JSON-RPC path never forwards object bytes.
- **Single service type**: DID Documents expose one service type `ANPMessageService`; direct, group, key-material and object-control capabilities are all carried behind it (details in §3 of these notes, from P2).
- **Security profiles** (`meta.security_profile`): `transport-protected`, `direct-e2ee`, `group-e2ee`. Base Profiles run alone; E2EE overlays sit on top. Object-level encryption mode `object-e2ee` is a P7 concept (see §8).
- Layering (P1 §3.1): Transport (HTTPS/WSS) → Binding (`anp.core.binding.v1`) → Business (Direct/Group Base) → Security Overlay (Direct/Group E2EE) → Media/Object (Attachment).


---

## 2. P1 Core Binding — `anp.core.binding.v1` (Status: Released)

### 2.1 Transport
- MUST run over authenticated secure transport: HTTPS, WSS, or other channel with confidentiality + integrity + peer auth. Raw unencrypted transport not allowed (§4.2).
- Logically transport-agnostic; HTTP(S) and WSS are *recommended* bindings. Other bindings = supplementary binding documents (§4.3). **Ambiguity:** P1 does not define the HTTP path, HTTP status code mapping, or the WSS framing; the `serviceEndpoint` URL from the DID Document is the POST target (see P2/P8 notes). Notifications (server push) need a channel — WSS or callback; P1 doesn't specify how notifications are physically delivered.

### 2.2 JSON-RPC tightening (§5)
| Rule | Requirement | Error on violation |
|---|---|---|
| `jsonrpc` | exactly `"2.0"` in every request and response | `-32600` |
| `params` | MUST be object; array form forbidden | `anp.invalid_params_shape` (1003) |
| `id` | MUST be non-empty **string**; no numbers; no `null` | `anp.invalid_request_id` (1000) |
| Batch | MUST NOT send; server MUST reject | `anp.batch_not_supported` (1004) |
| Notification (no `id`) | only for async push events / one-way prompts. MUST NOT be used for state-changing control ops, idempotently-confirmed sends, or anything needing success/failure | — |
| Method name | lowercase start, `.`-separated, MUST NOT start with `rpc.`; `<domain>.<action>` | `-32601` if unknown |
| Response | one per Request; success has `result` only; failure has `error` only; `id` echoes request | — |

Namespaces (§11.1): `anp.*`, `direct.*`, `group.*`, `attachment.*`, `federation.*`. Private extension methods MUST NOT collide with standard names, SHOULD use a private prefix.

### 2.3 `params` envelope (§6)
```json
{ "meta": { }, "auth": { }, "body": { } }
```
- `meta` = common metadata; `auth` = only when the Profile requires it (then MUST be present and validated); `body` = method-specific.
- Other top-level `params` members only if the Profile defines them.

#### `meta` fields (§6.2)
| Field | Type | Requirement | Notes |
|---|---|---|---|
| `anp_version` | string | **Deprecated**; new senders SHOULD NOT send | MUST NOT be used to select a Profile |
| `profile` | string | **MUST** | sole interpretation of body/result/errors; exactly one Profile (no unions) |
| `security_profile` | string | **MUST** | `transport-protected` \| `direct-e2ee` \| `group-e2ee` |
| `sender_did` | DID | MUST except anonymous public discovery | business origin DID; MUST NOT be equated with the one-hop transport caller |
| `sender_device_id` | string | Conditional — MUST NOT appear unless P5/P6 declares it | must be a current eligible `deviceManifest` entry of `sender_did` |
| `recipient_device_id` | string | Conditional — same | recipient DID stays in `meta.target.did`; no `target.kind="device"` |
| `target` | `{kind, did}` | MUST when the method has a protocol-level target | `kind` ∈ `agent` \| `group` \| `service`; `did` never a URL |
| `operation_id` | string | MUST for every state-changing op | idempotency key |
| `message_id` | string | MUST for message-bearing ops & message-bearing notifications | SHOULD equal `operation_id` unless separate retry lifecycle needed |
| `created_at` | RFC 3339 | SHOULD | not the sole anti-replay mechanism |
| `trace_id` | — | **not** an interoperable field | use transport metadata or `x_trace_id`; never in security/authz/idempotency |
| `content_type` | string | MUST for message-bearing ops | type of the primary business payload (Base) or of the outer cipher envelope (Overlay) |

Unknown fields (§12.1): unknown core `meta` field → MUST reject; `x_`-prefixed `meta` fields MAY be ignored; unknown `auth` fields → MUST reject unless Profile allows; unknown `body` fields MAY be ignored only if Profile says so; anything affecting security/routing/permissions/idempotency/state machine → MUST reject.

Device selectors: relays MUST preserve them on declared P5/P6 operations and MUST NOT add/remove/infer/rewrite. In Base operations they are invalid params (not 1015–1018).

#### Target modeling modes (§6.2.5.1) — each method MUST declare one
1. **agent-addressed**: `target.kind="agent"`, `target.did` = Agent DID
2. **group-addressed**: `target.kind="group"`, `target.did` = Group DID
3. **service-scoped**: `target.kind="service"`, `target.did` = target `ANPMessageService.serviceDid` (server MUST verify equality)
4. **endpoint-local**: `meta.target` may be omitted only if explicitly declared

Not declared endpoint-local ⇒ explicit target required. Mismatch ⇒ `anp.invalid_target_binding` (1014). If a method requires `auth.origin_proof`, `meta.target` MUST be present with kind ∈ agent/group/service.

#### `content_type` rules (§6.2.10, §13.4)
- Base: describes the primary payload in the carrier (`text` / `payload` / `payload_b64u`), not the JSON carrier.
- Overlay: describes the outer ciphertext envelope; inner original type goes in `application_content_type`.
- Examples: Direct Base text `text/plain`; Group Base JSON `application/json`; Direct E2EE outer `application/anp-direct-cipher+json` with inner `application_content_type: "text/plain"`; Group E2EE outer `application/anp-group-cipher+json`; attachment list inner `application_content_type: "application/anp-attachment-manifest+json"`.
- Structured JSON MUST use `application/json`, carried as a JSON object directly in `body.payload` (no double serialization, no JSON string in `body.text`). MUST NOT invent content types to distinguish business meanings (commands/tasks/results).
- `payload` and `payload_b64u` mutually exclusive when a Profile defines both → reject both-present.

### 2.4 Payload representation (§7)
- JSON objects first; no "JSON within a JSON string".
- Binary = **unpadded base64url**, field names SHOULD end `_b64u` (`ciphertext_b64u`, `key_package_b64u`, `welcome_b64u`).
- Counters, serial numbers, logical clocks, epoch, generation, large lengths, anything > 2^53 → **decimal strings** (e.g. `"max_request_bytes": "1048576"`, `group_state_version: "43"`).
- Any Signed Payload MUST specify a unique normalization (ANP uses RFC 8785 JCS).

### 2.5 Capability negotiation (§8)
Every endpoint MUST expose `anp.get_capabilities`. Result MUST include at least: supported Profiles, supported Security Profiles, runtime service identity, implementation limits.

Request (copied):
```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "method": "anp.get_capabilities",
  "params": {
    "meta": {
      "profile": "anp.core.binding.v1",
      "security_profile": "transport-protected",
      "operation_id": "op-cap-001",
      "created_at": "2026-03-29T12:00:00Z"
    },
    "body": {}
  }
}
```
- MAY be anonymous (omit `sender_did`); server MAY return identity-dependent subsets, caller MAY re-call authenticated.
- **Ambiguity:** the example omits `meta.target` although P1 says non-endpoint-local methods need explicit target; the target mode of `anp.get_capabilities` is not declared in P1 (it behaves as endpoint-local / or service-scoped). Recommend accepting both omitted target and `{kind:"service", did: serviceDid}`.

Response (copied):
```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "service_did": "did:example:service",
    "supported_profiles": [
      "anp.core.binding.v1",
      "anp.identity.discovery.v1",
      "anp.direct.base.v1",
      "anp.group.base.v2",
      "anp.attachment.v1",
      "anp.federation.relay.v1",
      "anp.direct.e2ee.v2",
      "anp.group.e2ee.v2"
    ],
    "supported_security_profiles": ["transport-protected", "direct-e2ee", "group-e2ee"],
    "limits": { "max_request_bytes": "1048576", "max_message_bytes": "262144" },
    "supported_content_types": ["text/plain", "application/json", "application/anp-attachment-manifest+json"]
  }
}
```
Rules (§8.3): DID-Document static hints are cacheable hints only; runtime result wins and conflicts trigger cache refresh. Unsupported `profile` / `security_profile` → explicit error (1001/1002). Base support ≠ E2EE support. Base negotiation is DID-level (no Manifest). Before a device-addressed E2EE op, also verify device eligibility in current P2 `deviceManifest`. Cache results; renegotiate on capability change, auth failure, endpoint switch, cache invalidation (§14.3). `supported_content_types` is a SHOULD extension. Only advertise what you actually implement.

### 2.6 Idempotence (§9)
- All state-changing ops MUST be idempotent. Key = `(sender_did, target_scope, method, operation_id)`; `target_scope` defined per Profile (Direct: usually `target.did`; Group: usually `group_did`).
- Same key + semantically equivalent → same/equivalent result. Same key + semantic conflict → `anp.idempotency_conflict` (1008).
- Server MUST do idempotent-hit check **before** optimistic concurrency / version precondition checks.
- Base ops: device ID not part of scope. E2EE overlays MUST add every required device selector to scope.
- DID transition: exact retry of a request accepted under the earlier DID MUST be looked up *before* rejecting as superseded; return prior result. Successor-signed request is not an exact retry.
- Message retries: `message_id` AND `operation_id` unchanged on retry.
- Non-idempotent ops must be explicitly marked by the Profile; unmarked = idempotent.

### 2.7 Error model (§10)
Standard JSON-RPC codes kept: `-32700` parse, `-32600` invalid request, `-32601` method not found, `-32602` invalid params, `-32603` internal.
ANP error object:
```json
{ "code": 1001, "message": "Unsupported profile",
  "data": { "anp_code": "anp.unsupported_profile", "retryable": false, "details": {} } }
```
`error.data.anp_code` MUST exist for ANP codes; `retryable` SHOULD; no sensitive internal state leaks.

| code | anp_code | meaning |
|---|---|---|
| 1000 | `anp.invalid_request_id` | bad `id` |
| 1001 | `anp.unsupported_profile` | Profile unsupported |
| 1002 | `anp.unsupported_security_profile` | security profile unsupported |
| 1003 | `anp.invalid_params_shape` | params structure invalid |
| 1004 | `anp.batch_not_supported` | batch |
| 1005 | `anp.unauthorized` | authentication failed |
| 1006 | `anp.forbidden` | authenticated, not authorized |
| 1007 | `anp.target_not_found` | target DID missing/unreachable |
| 1008 | `anp.idempotency_conflict` | idempotency key conflict |
| 1009 | `anp.unsupported_content_type` | content type unsupported |
| 1010 | `anp.delivery_rejected` | target service refused |
| 1011 | `anp.rate_limited` | throttled |
| 1012 | `anp.temporarily_unavailable` | temporarily unavailable |
| 1013 | `anp.invalid_security_binding` | security profile vs payload mismatch |
| 1014 | `anp.invalid_target_binding` | target mode mismatch |
| 1015 | `anp.device_binding_required` | E2EE overlay selector missing |
| 1016 | `anp.device_binding_invalid` | selector / DID / key binding invalid |
| 1017 | `anp.device_not_eligible` | device not eligible for requested Profile |
| 1018 | `anp.device_state_changed` | previously resolved eligibility/key state stale |
| 1019 | `anp.did_superseded` | DID has successor; verify transition, rebuild, re-sign. `details` SHOULD include `requested_did`, `current_did` (unverified hint) |
| 1020 | `anp.did_transition_invalid` | invalid transition chain/proof/binding/path/Profile |
| 1021 | `anp.did_transition_conflict` | fork, cycle, ambiguous subject, collision, concurrent update |

1015–1018 only for P5/P6-declared device ops. 1019–1021 only for Profiles processing DID transitions. Never expose an internal stable-subject ID.

### 2.8 Security rules (§13)
- No silent security downgrade; unsupported → `anp.unsupported_security_profile`.
- `created_at` never sole anti-replay.
- tracing/log fields never in crypto binding or authz.
- Device selectors MUST be covered by Overlay's authenticated context (Origin Proof with keyid == Manifest `signing_key_id`, or session/AAD binding). Reject unprotected/mismatched selectors.
- Privacy (§14.2): selectors must not expose device names, hardware IDs, roles, online state, recovery state, topology.

### 2.9 Minimum interoperability (§15) — P1 conformance checklist
1 JSON-RPC 2.0; 2 object `params`; 3 string `id`; 4 `anp.get_capabilities`; 5 public error codes; 6 idempotent `operation_id`; 7 `meta`/`body` structure; 8 secure transport; 9 anonymous + authenticated `anp.get_capabilities`; 10 unified `content_type` semantics; 11 declare target mode per method; 12 enforce `target.kind="service"` + `target.did=serviceDid` for service-scoped; 13 reject ambiguous target omission; 14 reject device selectors in Base ops; 15 DID-transition errors 1019–1021 and old-DID exact-replay lookup before superseded rejection.

### 2.10 Example `direct.send` (P1 §16, copied)
```json
{
  "jsonrpc": "2.0",
  "id": "req-10001",
  "method": "direct.send",
  "params": {
    "meta": {
      "profile": "anp.direct.base.v1",
      "security_profile": "transport-protected",
      "sender_did": "did:example:agent-a",
      "target": { "kind": "agent", "did": "did:example:agent-b" },
      "operation_id": "msg-10001",
      "message_id": "msg-10001",
      "created_at": "2026-03-29T12:00:00Z",
      "content_type": "text/plain"
    },
    "auth": {
      "scheme": "anp-rfc9421-origin-proof-v1",
      "origin_proof": {
        "contentDigest": "sha-256=:BASE64_SHA256_OF_SIGNED_DIRECT_PAYLOAD:",
        "signatureInput": "sig1=(\"@method\" \"@target-uri\" \"content-digest\");created=1774785600;expires=1774785660;nonce=\"n-10001\";keyid=\"did:example:agent-a#key-1\"",
        "signature": "sig1=:BASE64_SIGNATURE:"
      }
    },
    "body": { "text": "hello" }
  }
}
```
Response:
```json
{ "jsonrpc": "2.0", "id": "req-10001",
  "result": { "accepted": true, "message_id": "msg-10001", "operation_id": "msg-10001",
              "target_did": "did:example:agent-b", "accepted_at": "2026-03-29T12:00:01Z" } }
```

### 2.11 Appendix A — Origin Proof (`anp-rfc9421-origin-proof-v1`), shared by P3, P4, P6
- `auth.scheme` MUST = `anp-rfc9421-origin-proof-v1`; `auth.origin_proof` MUST exist with `contentDigest` (RFC 9530 field value), `signatureInput` (RFC 9421 `Signature-Input` field value), `signature` (RFC 9421 `Signature` field value). `auth` itself never enters the digest.
- v1 fixed: digest alg `sha-256`; label `sig1`; covered components exactly `("@method" "@target-uri" "content-digest")`.
- **Signed Request Object** = `{ "method", "meta", "body" }` only (no `jsonrpc`, `id`, `auth`), RFC 8785 JCS canonicalized, default optional fields omitted, no routing/cache/tracing fields → SHA-256 → `contentDigest = "sha-256=:<b64>:"`.
- Component mapping: `@method` = SRO.method; `@target-uri` = `anp://{meta.target.kind}/{pct-encoded meta.target.did}` (RFC 3986 percent-encoding of UTF-8 DID); `content-digest` = contentDigest.
- Sign the RFC 9421 signature base (incl. `@signature-params`), never raw JSON or the `signatureInput` string.
- Signature params example: `created=...;expires=...;nonce="...";keyid="did:...#key-1"`.
- Verifier steps (A.6): read proof → rebuild SRO from `method`, `params.meta`, `params.body` → JCS → recompute digest → rebuild `@method`, `@target-uri` → rebuild/verify signature base → resolve + method-validate DID Doc (ANP-02/P2), check `keyid` exists and is in `authentication` → verify signature, time window, replay (ANP-02). Any failure → reject. If P5/P6 declares `meta.sender_device_id` and uses origin proof, `keyid` MUST equal the selected Manifest entry's `signing_key_id`.
- `keyid` DID MUST equal the business subject DID (normally `meta.sender_did`).
- Origin Proof ≠ hop auth. Intermediaries MUST forward `auth.origin_proof` unchanged, MUST NOT mint a new one or replace with service HTTP signature. Recipient MUST verify it independently.

### 2.12 Appendix B — Object Proof (W3C Data Integrity), shared by P4/P5/P6
- Applies to: `group_receipt.proof` (P4), `prekey_bundle.proof` (P5), `did_wba_binding.proof` (P6) (plus other objects that reference App. B).
```json
{ "proof": { "type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022",
  "verificationMethod": "did:example:issuer#key-1", "proofPurpose": "assertionMethod",
  "created": "2026-03-29T12:00:00Z", "proofValue": "z..." } }
```
- Fixed: `type=DataIntegrityProof`, `cryptosuite=eddsa-jcs-2022`, `proofPurpose=assertionMethod`, full DID URL `verificationMethod`, RFC 3339 `created`, base58-btc multibase `proofValue` (`z...`).
- Protected document = whole object minus top-level `proof`; omit default optional fields; never `null`/empty placeholders; never include JSON-RPC envelope/headers.
- JCS + UTF-8 then `eddsa-jcs-2022`. VM must belong to issuer DID (declared per object) and be in issuer's `assertionMethod`. Plus method-specific checks (e.g. did:wba `e1_` path fingerprint). After proof passes, still run object business checks.

---

## 3. P2 Identity and Discovery — `anp.identity.discovery.v1` (Released; depends on P1)

### 3.1 Identity model
- First-class identifiers: **Agent DID** (`agent_did`) and **Group DID** (`group_did`). No Device DIDs, terminal DIDs, session DIDs, replica DIDs.
- `device_id` is opaque, only for device-addressed E2EE Profiles; never a member/role/`target.kind`. Base Profiles MUST NOT require/carry it. Non-E2EE device fan-out is implementation-internal.
- Three DID layers that MUST NOT be auto-equated (§3.5):
  1. **Business Origin DID** — `meta.sender_did`
  2. **Logical Issuer DID** — e.g. `group_did` for receipts/governance objects
  3. **Service DID** — `ANPMessageService.serviceDid`, the one-hop service-to-service identity. Never replaces the business DID; never used for owner/admin/member decisions.
- Crypto-internal IDs (`crypto_group_id`, `session_id`, `channel_id`) MAY differ from DIDs but the overlay MUST define a verifiable binding to the DID (§3.4).
- DID method validation per ANP-02 + method binding; `did:wba`, `did:web`, etc. share identical discovery / key-purpose / device-eligibility rules (§4.1.1).

### 3.2 DID Document requirements (§4.2, §5, §6)
- `id` MUST. `service` MUST for actively discovered DIDs. `authentication` MUST if the DID appears as `meta.sender_did` or in an origin-proof `keyid`. `assertionMethod` SHOULD if signing declarative objects. `keyAgreement` SHOULD if any E2EE overlay is supported (keys there used only for key agreement). `capabilityInvocation` optional.
- `deviceManifest` MUST exist if the Agent advertises a device-addressed E2EE Profile; otherwise optional.
- DID Docs MUST NOT be used as: message-status DB, member list, presence store, high-frequency key rotation log, replica list.
- Group DID Doc MUST have `id`, `controller` (single or multiple), at least one `ANPMessageService`; for `anp.group.base.v2` `assertionMethod` MUST exist. MUST NOT embed: dynamic member list, online members, message seq number, group epoch, per-message status, one-time prekeys, MLS KeyPackages, invitation queues, replica lists. MAY include display name, icon ref, public description, public policy summary, doc version info, capability summary.
- `controller` ≠ group governance roles (§11.3).

### 3.3 `ANPMessageService` (§7, §8)
- Every service object MUST have `id`, `type`, `serviceEndpoint`. v1 standard static hints: `profiles` (SHOULD), `securityProfiles` (SHOULD), `serviceDid` (MUST if it participates in cross-domain s2s calls).
- Each DID Document **MUST expose only one** cross-domain-callable `ANPMessageService`. Internal splitting (Home / Key / Group / Join / Capability / Object roles) is invisible.
- Purposes: receive `direct.send`; receive `group.get_info`, `group.send`, `group.e2ee.send` and group management / E2EE actions; serve `anp.get_capabilities`; E2EE public material; receive/distribute `group.e2ee.notice`; `attachment.create_slot`, `attachment.commit_object`, `attachment.abort_object`, `attachment.get_download_ticket`; anchor for object download portal discovery.
- Not standard v1 DID hints (put into `anp.get_capabilities` instead): `acceptedContentTypes`, `acceptedObjectTypes`, `priority`, `authSchemes`, `supportedMethods`, `logicalRoles`.
- `serviceDid` rules (§8.7): a DID (not DID URL); outer HTTP Message Signature `keyid` MUST be in `serviceDid` doc's `authentication`; SHOULD be a bare-domain DID for did:web/did:wba; discovery hint only — trust only after P8 runtime verification; service-scoped methods SHOULD set `meta.target.did = serviceDid` (object control plane, key material, group-join material).

Agent DID Document example (P2 §15.1, abbreviated — see file for full JWKs):
```json
{
  "id": "did:example:agent-a",
  "authentication": ["did:example:agent-a#dev-a-sign", "did:example:agent-a#dev-a2-sign"],
  "assertionMethod": ["did:example:agent-a#dev-a-sign", "did:example:agent-a#dev-a2-sign"],
  "keyAgreement": ["did:example:agent-a#dev-a-e2ee", "did:example:agent-a#dev-a2-e2ee"],
  "service": [{
    "id": "did:example:agent-a#message",
    "type": "ANPMessageService",
    "serviceEndpoint": "https://agent-a.example.com/anp",
    "serviceDid": "did:example:domain-a",
    "profiles": ["anp.core.binding.v1", "anp.identity.discovery.v1", "anp.direct.base.v1", "anp.direct.e2ee.v2", "anp.attachment.v1"],
    "securityProfiles": ["transport-protected", "direct-e2ee"]
  }],
  "deviceManifest": {
    "type": "ANPDeviceManifest",
    "devices": [
      { "device_id": "dev-a-7N3KQ2", "signing_key_id": "did:example:agent-a#dev-a-sign",
        "e2ee_key_id": "did:example:agent-a#dev-a-e2ee",
        "profiles": ["anp.core.binding.v1", "anp.identity.discovery.v1", "anp.direct.base.v1", "anp.direct.e2ee.v2"] },
      { "device_id": "dev-a2-9R5TLM", "signing_key_id": "did:example:agent-a#dev-a2-sign",
        "e2ee_key_id": "did:example:agent-a#dev-a2-e2ee",
        "profiles": ["anp.core.binding.v1", "anp.identity.discovery.v1", "anp.direct.base.v1", "anp.direct.e2ee.v2"] }
    ]
  }
}
```
Verification methods use `JsonWebKey2020` with `OKP`/`Ed25519` (signing) and `OKP`/`X25519` (e2ee).

Group DID Document example (§15.2):
```json
{
  "id": "did:example:group-123",
  "controller": ["did:example:group-host", "did:example:group-admin-controller"],
  "verificationMethod": [{ "id": "did:example:group-123#gov-1", "type": "JsonWebKey2020",
     "controller": "did:example:group-123", "publicKeyJwk": { "kty": "OKP", "crv": "Ed25519", "x": "..." } }],
  "assertionMethod": ["did:example:group-123#gov-1"],
  "service": [{
    "id": "did:example:group-123#message",
    "type": "ANPMessageService",
    "serviceEndpoint": "https://group-host.example.com/anp/groups/group-123",
    "serviceDid": "did:example:group-host-domain",
    "profiles": ["anp.core.binding.v1", "anp.identity.discovery.v1", "anp.group.base.v2", "anp.group.e2ee.v2"],
    "securityProfiles": ["transport-protected", "group-e2ee"]
  }]
}
```
Group DIDs never have a `deviceManifest`.

### 3.4 `deviceManifest` (§5.5) — structure & eligibility rules
```json
{ "deviceManifest": { "type": "ANPDeviceManifest", "devices": [
  { "device_id": "dev-a-7N3KQ2", "signing_key_id": "did:example:agent-a#dev-a-sign",
    "e2ee_key_id": "did:example:agent-a#dev-a-e2ee",
    "profiles": ["anp.core.binding.v1","anp.identity.discovery.v1","anp.direct.base.v1","anp.direct.e2ee.v2"] } ] } }
```
1. MUST be published (current) if the DID advertises/invokes a device-addressed E2EE Profile; Base-only MAY omit.
2. `type` MUST = `ANPDeviceManifest`; `devices` MUST be array; each entry MUST contain **exactly** `device_id`, `signing_key_id`, `e2ee_key_id`, `profiles`.
3. `device_id` opaque, unique within this DID's Manifest, **never reused after removal**; not a DID/serial/display name/role.
4. `signing_key_id`, `e2ee_key_id` = DID URLs in the same DID Doc. `signing_key_id` authorized for `authentication` (when Origin Proof used) and/or `assertionMethod` (when Object Proof used); `e2ee_key_id` MUST be in `keyAgreement`.
5. `profiles` non-empty, complete dependency set: P5 entry = P1+P2+P3+P5; P6 entry = P1+P2+P4+P6.
6. P3/P4/P7/non-E2EE flows MUST NOT consult the Manifest.
7. Removal = publish updated DID Doc without that entry and its device-key references; future selections MUST be rejected; re-enroll with new ID + keys.
8. No separate Manifest endpoint/proof/epoch/hash/checkpoint/CAS — protected by the DID method.
9. MUST NOT contain private keys, roles, tokens, display names, hardware IDs, presence, recovery state, topology.
- **Eligible Device** = entry whose key refs and declared Profile set satisfy the owning E2EE Profile *at time of use* (§2.2). §10.2.1: selected entry must declare requested E2EE Profile + deps; its keys must match the keys actually used; origin-proof `keyid` = `signing_key_id`; E2EE session key = `e2ee_key_id`.

### 3.5 Discovery process (§9)
Agent: resolve DID → read `service` → select the single cross-domain `ANPMessageService` → read `serviceDid` if s2s needed → combine `profiles`/`securityProfiles`/runtime caps/local policy → Base op: use DID + service directly (no Manifest, no device synthesis) → E2EE op: resolve current `deviceManifest`, choose Eligible Devices → `anp.get_capabilities` on same entry.
Group: resolve `group_did` → unique `ANPMessageService` → `serviceDid` → caps. Member key material still discovered via each member's Agent DID entry.
Service DID: resolve `serviceDid` doc → its `ANPMessageService` → `serviceEndpoint` → caps → trusted only after P8 runtime binding verification.
**Attachment download ticket discovery anchor** = original message sender DID (in groups: original group message sender, *not* `group_did`). MUST NOT derive control-plane service from `object_uri` hostname.
Service selection (§9.4): filter by `profile` → by `security_profile` → runtime caps authoritative → local policy.
Re-resolve DID (§9.5) on: signature verification failure, key negotiation failure, capability change, suspected control change, `serviceDid` verification failure, endpoint-origin binding failure, static/runtime conflict, cache expiry.

### 3.6 DID transitions (§12)
- Internal op (not on wire): `resolve_current_agent_did(input_did, trusted_cache) -> { requested_did, current_did, transition_status, assurance } | error`. MUST NOT add `stable_subject_id` to wire.
- Only registered automatic path: path-type `did:wba` whose last segment uses `e1_` fingerprint Profile; validate every hop from the previously trusted DID per ANP-03; reject cycles, conflicting successors, cache conflicts.
- Assurance levels: `verified` (old root key signs deactivation+successor), `recovery_verified` (pre-authorized recovery key), `provider_asserted` (authenticated same-origin complete chain, or authenticated provider channel), `unverified`. Never upgrade `provider_asserted` to verified; don't fail *solely* because of `provider_asserted` — business policy decides.
- `alsoKnownAs`/path similarity = candidate only. Bare-domain did:wba, `k1_`, legacy paths, `did:web`, other methods: use as written; deactivated ⇒ fail closed `anp.did_transition_invalid` with `reason = transition_profile_not_supported`.
- **Group DIDs never auto-transition**; deactivated `group_did` ⇒ Host MUST reject new group ops and P6 app-message processing.

### 3.7 P2 minimum interop (§14)
Each Agent has `agent_did`; each Group `group_did`; both docs have ≥1 `ANPMessageService`; DID-based discovery; static hints `profiles`/`securityProfiles`/`serviceDid`; runtime caps authoritative; no dynamic group state in docs; Base stays DID-level; publish/validate `deviceManifest` when advertising E2EE; no Device DIDs; return actual transition assurance; `e1_` rules if claimed; `alsoKnownAs` candidate-only; no automatic Group DID transitions.

---

## 4. P3 Direct Messaging Base — `anp.direct.base.v1` (Released; deps P1, P2)

### 4.1 Model
- Protocol endpoint is the **Agent** (not device/replica). Delivery task completes when the target Agent's **ingress service** accepts. Internal fan-out, queues, replicas, device counts MUST NOT be exposed on the wire (§5.4, §10.2).
- One sender, one receiver per `direct.send`; **no broadcast** to multiple targets (§5.2).
- Non-goals: E2E confidentiality, multi-device consistency, global strict order, history replay, device-level delivery proof, **read status**, presence, history pull. ⇒ **There are no standard delivered/read receipts for direct messages.** The only standard acknowledgment is the synchronous `accepted: true` result from the target ingress.
- `meta.profile` MUST = `anp.direct.base.v1` and `meta.security_profile` MUST = `transport-protected` when used standalone.
- With `meta.profile = "anp.direct.e2ee.v2"`, P5 overrides P3's mandatory `auth.origin_proof` (deniability: auth comes from E2EE session/AAD).
- Target mode: **agent-addressed**. `meta.target.kind` MUST = `"agent"`; else `anp.invalid_target_binding`.

### 4.2 Methods
| Method | Kind | Direction | Notes |
|---|---|---|---|
| `direct.send` | Request | sender (or sender-domain service) → target ingress `ANPMessageService` | agent-addressed, state-changing, idempotent |
| `direct.incoming` | **Notification (MUST implement)** | ANP endpoint → target Agent (recipient's runtime) | no JSON-RPC response; push path; doesn't change send success semantics |

#### `direct.send` request requirements (§7.1.2)
1. `method="direct.send"` 2. `meta.profile="anp.direct.base.v1"` 3. `meta.security_profile="transport-protected"` 4. `meta.sender_did` 5. `meta.target.kind="agent"` 6. `meta.target.did` 7. `meta.operation_id` 8. `meta.message_id` 9. `meta.content_type` 10. body mutual-exclusion OK 11. `auth.scheme="anp-rfc9421-origin-proof-v1"` 12. `auth.origin_proof` binds the Signed Request Object 13. `meta.sender_device_id` / `meta.recipient_device_id` MUST NOT exist.

For the Signed Request Object: `method = direct.send`, `meta.target.kind = agent`, `meta.target.did` = recipient, `meta.message_id` and `meta.content_type` MUST exist. `@target-uri = anp://agent/<pct-encoded target DID>`.

#### `body` fields (§6.2)
| Field | Type | Req | Notes |
|---|---|---|---|
| `conversation_id` | string | MAY | app context; not device/replica/security/anti-replay ID |
| `reply_to_message_id` | string | MAY | reply threading |
| `annotations` | object | MAY | sender metadata; relays MUST NOT modify; unknown fields MAY be ignored; no hidden control semantics |
| `text` | string | MUST if `content_type="text/plain"` | |
| `payload` | JSON object | MUST if `content_type="application/json"` (also used for `application/anp-attachment-manifest+json`) | no double serialization |
| `payload_b64u` | string | MAY for binary / private extension types | unpadded base64url |

**Exactly one** of `text` / `payload` / `payload_b64u` MUST be present; zero or >1 ⇒ reject.

MTI content types: `text/plain`, `application/json`, `application/anp-attachment-manifest+json`. Others: MAY; unsupported ⇒ `anp.unsupported_content_type` (1009).

#### Success result (§7.1.3)
MUST: `accepted` (=`true`), `message_id`, `operation_id`, `target_did`, `accepted_at` (RFC 3339). MAY: `conversation_id`. MUST NOT: device selectors, per-device results, fan-out status.

#### Failure conditions (§7.1.4) — MUST reject when
target DID missing/unreachable; hop caller not authenticated; content type unsupported; body violates mutual exclusion; target policy prohibits; security-profile requirements violated; `auth.origin_proof` missing/invalid/expired/replayed; `keyid` DID ≠ `meta.sender_did`.

#### `direct.incoming` constraints (§7.2.3)
- MUST be a Notification (no `id`), receiver MUST NOT respond.
- `params.meta.profile = "anp.direct.base.v1"`; `security_profile` = that of the accepted `direct.send`; `target.kind="agent"`; `target.did` = notification recipient DID; `sender_did` = original logical sender; `operation_id`, `message_id`, `content_type` = original values; `params.body` = original payload.
- If `params.auth` present: scheme `anp-rfc9421-origin-proof-v1`, `origin_proof` = **lossless copy** of the original; intermediates MUST NOT regenerate.
- No device selectors.
- Re-push of same message SHOULD keep `operation_id`, `message_id`, equivalent body. Auto-resend policy is local (no mandated retry count/backoff).

(derived) `direct.incoming` shape:
```json
{ "jsonrpc": "2.0", "method": "direct.incoming",
  "params": {
    "meta": { "profile": "anp.direct.base.v1", "security_profile": "transport-protected",
              "sender_did": "did:example:agent-a", "target": { "kind": "agent", "did": "did:example:agent-b" },
              "operation_id": "msg-20001", "message_id": "msg-20001", "content_type": "text/plain",
              "created_at": "2026-03-29T12:00:00Z" },
    "auth": { "scheme": "anp-rfc9421-origin-proof-v1", "origin_proof": { "...": "lossless copy" } },
    "body": { "conversation_id": "conv-01", "text": "hello from agent-a" } } }
```
**Ambiguity:** P3 does not specify the physical channel for pushing `direct.incoming` to the recipient Agent (WSS session, callback URL, long-poll). It is effectively a local/domain-internal concern between the recipient's ANP endpoint and the Agent runtime. Treat it as a server→client push over WSS (or equivalent) in your design.

### 4.3 Idempotence, dedup, ordering (§8)
- Idempotency key: `(sender_did, target.did, method, operation_id)` — check first. Message dedup (SHOULD): `(sender_did, target.did, message_id)` — check second (see decision flow P3-2).
- Equivalent replay ⇒ same/equivalent result; non-equivalent ⇒ `anp.idempotency_conflict`.
- Retry: same `operation_id`, same `message_id`, semantically equivalent payload.
- After accepted target-DID transition: newly signed request, not an exact retry; MAY dedupe on logical `message_id` with accepted transition; MUST NOT merge on unverified `current_did` hint.
- **No global strict ordering.** MAY best-effort order per `conversation_id`. Interop layer MUST NOT assume FIFO.

### 4.4 Superseded DIDs (§5.5)
Receiver MUST return `anp.did_superseded` (1019) rather than rewriting target. Sender verifies transition (P2), applies business policy, replaces `meta.target.did`, rebuilds SRO + `contentDigest`, re-signs; `message_id`/`operation_id` unchanged. Never rewrite historical messages/signatures/receipts.

### 4.5 Security (§9)
- Secure transport mandatory.
- For every `direct.send` with `meta.sender_did` under Base: sender MUST provide `auth.origin_proof`; receiver ingress MUST verify per P1 App. A, check `keyid` DID == `sender_did`, `keyid` in `authentication`, sender DID Doc method-validated.
- Cross-domain: forward origin proof unchanged; target domain MUST verify independently; service-level auth at each hop additionally; upstream pre-verification doesn't exempt target.
- ANP-02 access tokens MAY optimize repeated requests but MUST NOT replace `auth.origin_proof` cross-domain; sender-constrained tokens preferred over Bearer.
- If recipient policy requires `direct-e2ee`: receiver MUST reject transport-protected `direct.send` (use 2004 `direct.security_mode_required`).
- Overlay binding points (SHOULD into authenticated context): `sender_did`, `target.did`, `message_id`, `conversation_id`, `content_type`, `security_profile`, origin proof digest.

### 4.6 P3 errors (recommended, §11)
| code | anp_code | meaning |
|---|---|---|
| 2000 | `direct.recipient_unreachable` | target temporarily unreachable |
| 2001 | `direct.policy_violation` | target policy rejected |
| 2002 | `direct.invalid_payload_shape` | payload structure invalid |
| 2003 | `direct.conversation_conflict` | conversation context conflict |
| 2004 | `direct.security_mode_required` | higher security profile required |
| 2005 | `direct.invalid_origin_proof` | origin proof invalid/expired/missing |
| 2006 | `direct.origin_did_mismatch` | `sender_did` vs `keyid` DID mismatch |
| 2007 | `direct.origin_proof_replayed` | suspected replay |

### 4.7 P3 minimum interop (§12)
`direct.send`; `direct.incoming`; `target.kind="agent"`; `text/plain`; `application/json`; `application/anp-attachment-manifest+json`; mutual exclusion; idempotent `message_id`/`operation_id`; origin-proof submit+verify; SRO JCS digest rules; secure transport; DID-level addressing without device selectors/per-device results; superseded-DID handling.

### 4.8 Examples (copied)
Attachment manifest via Base direct message (§13.2):
```json
{
  "jsonrpc": "2.0", "id": "req-20002", "method": "direct.send",
  "params": {
    "meta": { "profile": "anp.direct.base.v1", "security_profile": "transport-protected",
      "sender_did": "did:example:agent-a", "target": { "kind": "agent", "did": "did:example:agent-b" },
      "operation_id": "msg-20002", "message_id": "msg-20002", "created_at": "2026-03-29T12:05:00Z",
      "content_type": "application/anp-attachment-manifest+json" },
    "auth": { "scheme": "anp-rfc9421-origin-proof-v1", "origin_proof": {
      "contentDigest": "sha-256=:BASE64_SHA256_OF_SIGNED_REQUEST_OBJECT:",
      "signatureInput": "sig1=(\"@method\" \"@target-uri\" \"content-digest\");created=1774785900;expires=1774785960;nonce=\"n-20002\";keyid=\"did:example:agent-a#key-1\"",
      "signature": "sig1=:BASE64_SIGNATURE:" } },
    "body": { "payload": {
      "attachments": [ {
        "attachment_id": "att-001", "filename": "report.pdf", "mime_type": "application/pdf", "size": "1048576",
        "digest": { "alg": "sha-256", "value_b64u": "BASE64URL_DIGEST" },
        "access_info": { "object_uri": "https://objects.example.com/objects/obj-plain-001" },
        "encryption_info": { "mode": "none" } } ],
      "caption": "Please check the attachment" } } }
}
```
JSON payload (§13.3): `content_type: "application/json"`, `body: { "conversation_id": "conv-01", "payload": { "type": "example", "data": { "hello": "world" } } }`.
**Spec inconsistency:** the §13.3 example omits `auth`, contradicting §6.4/§7.1.2 (auth MUST). Implement auth as mandatory.
did:wba example (§13.4): `sender_did: "did:wba:a.example:agents:alice:e1_<fingerprint>"`, `keyid="did:wba:a.example:agents:alice:e1_<fingerprint>#key-1"`.

---

## 5. P4 Group Messaging Base — `anp.group.base.v2` (Released; deps P1, P2)

### 5.1 What changed in v2
- No `group.invite`, `group.accept_invite`, `invitation`/`invitation_id`, `membership_request`, `group.approve_membership`, `group.reject_membership`, `group.governance_notice`. Invite links / Join Tokens = deployment extensions that MUST NOT create standard membership before `group.join` succeeds. No `pending` state, no approval flow.
- `group_policy` = `message_security_profile` + `bootstrap_security_profile` + `admission_mode` + `permissions` (+ optional `attachments_allowed`, `max_members`).
- DID-only membership; Handle-backed membership and public rebind method removed; Host-coordinated member DID update added (`group.member_did_update` as a *non-callable* action ID).
- Standalone: `meta.profile = "anp.group.base.v2"`, `meta.security_profile = "transport-protected"`.

### 5.2 Core model
- One group = one `group_did` (target for management and messaging). Not equal to any crypto `group_id`.
- **Group Host Service** MUST accept and linearly order all state-changing operations and assign a new `group_state_version` per accepted state change.
- `group_state_version`: Host-assigned, **opaque string**; new per state change; `group.send` MUST NOT advance it; a send's response returns the snapshot version it was accepted against.
- `group_event_seq`: monotonically increasing **decimal string** per group, covers control ops **and** messages; not a sole security basis.
- Ordered events (§10.1): `group.create`, `group.join`, `group.add`, Host action `group.member_did_update`, `group.remove`, `group.leave`, `group.update_profile`, `group.update_policy`, `group.send`.
- Roles (MTI): `owner > admin > member` (fixed hierarchy; no custom roles). DID-scoped; devices/MLS leaves get no roles.
- Member status (MTI): `active`, `left`, `removed`. State machine: NonMember→Active (`group.join` if open-join, or `group.add`); Active→Left (`group.leave`); Active→Removed (`group.remove`); Active→Active (Host DID update).
- P6 MLS leaves never add/remove P4 members, change roles, counts, policy, or create P4 events.
- Initiator signature (`auth.origin_proof`) vs group result witness (`group_receipt` signed by `group_did`) are separate and not substitutable.

### 5.3 Standard objects
`group_policy` (copied):
```json
{
  "message_security_profile": "transport-protected",
  "bootstrap_security_profile": "transport-protected",
  "admission_mode": "open-join",
  "permissions": { "send": "member", "add": "admin", "remove": "admin", "update_profile": "admin", "update_policy": "owner" },
  "attachments_allowed": true,
  "max_members": "500"
}
```
- `message_security_profile` (SHOULD; `transport-protected`|`group-e2ee`): governs `group.send` and member-only ops after activation.
- `bootstrap_security_profile` (SHOULD): governs `group.join` and overlay onboarding methods.
- `admission_mode` (MUST): `admin-add` (⇒ `group.join` MUST be rejected) | `open-join` (⇒ `group.join` MUST be allowed). `group.add` gated by `permissions.add` in both modes.
- `permissions` (MUST): exactly keys `send`, `add`, `remove`, `update_profile`, `update_policy`; values `owner`|`admin`|`member`.
- `attachments_allowed` bool MAY; `max_members` decimal string MAY = limit of active member DIDs (devices don't count).

`group_member`: `agent_did` (MUST, current DID), `role` (MUST; default interpret `member`), `status` (MUST), `joined_at` (MAY), `added_by` (MAY; only for `group.add`). MUST NOT contain device IDs/lists/selectors/MLS leaf IDs or name/stable-path IDs.

`group_profile`: `display_name` (SHOULD at create), `description`, `avatar_uri`, `discoverability` (`private`|`listed`|`public`), `labels` (object).

`group_state_ref`: `group_did` (MUST), `group_state_version` (MUST), `policy_hash` (MAY), `roster_hash` (MAY).

`group_receipt` (§7.9): `receipt_type` (MUST; `group-operation-accepted` | `group-message-accepted`), `group_did`, `group_state_version`, `group_event_seq`, `subject_method`, `operation_id`, `message_id` (MAY, protected if present), `actor_did`, `accepted_at`, `payload_digest`, `proof` (SHOULD; **MUST** when receipt leaves the Host's domain and other domains rely on it). Proof = P1 App. B; issuer DID = `group_did`; VM in `group_did`'s `assertionMethod`. Verifier MUST cross-check fields against response/notification and state position. `payload_digest` in examples = `"sha-256=:BASE64_SHA256_OF_SIGNED_REQUEST_OBJECT:"` (i.e. the request's `contentDigest`).

Group state change event (`group.state_changed` body) (§7.10, copied):
```json
{
  "event_id": "evt-didupd-001",
  "event_type": "member-did-updated",
  "group_did": "did:wba:groups.example:team:e1_group",
  "group_state_version": "43",
  "group_event_seq": "129",
  "subject_method": "group.member_did_update",
  "changed_at": "2026-08-25T02:11:00Z",
  "actor_did": "did:wba:groups.example",
  "previous_subject_did": "did:wba:example.com:user:alice:e1_old",
  "subject_did": "did:wba:example.com:user:alice:e1_current",
  "membership_status": "active",
  "group_receipt": { "...": "..." }
}
```
`event_type` values: `member-activated` (from join/add), `member-removed` (`membership_status="removed"`), `member-left` (`"left"`), `member-did-updated` (MUST have `previous_subject_did`, `subject_did`, `membership_status="active"`), `group-profile-updated`, `group-policy-updated`.
For DID-update receipts: `subject_method="group.member_did_update"`; `actor_did` = Host `ANPMessageService.serviceDid`; `operation_id` deterministically binds `group_did`+`previous_subject_did`+`subject_did` (e.g. `"didupd_BASE64URL_SHA256"`); `payload_digest` covers the old→new change.
**Ambiguity:** the common event fields are only shown via the DID-update example; the full field list for other event types is not normatively tabulated. Infer: `event_id`, `event_type`, `group_did`, `group_state_version`, `group_event_seq`, `subject_method`, `changed_at`, `actor_did`, `subject_did`, `membership_status` (membership events), `group_receipt`.

### 5.4 Common rules for P4 methods (§8)
- All state-changing methods except `group.get_info`, plus `group.send`: `params.auth.scheme="anp-rfc9421-origin-proof-v1"`, `auth.origin_proof` MUST bind SRO; forwarded unchanged cross-domain.
- Successful state change / `group.send`: non-federated SHOULD return `group_receipt`; if response leaves Host's domain for reliance by another domain, MUST return `group_receipt` with `proof`.
- `group.incoming` and `group.state_changed` = **OPTIONAL push** (but must follow standard envelope if implemented). Note however MTI item 18 requires the final self-scoped `group.state_changed` for removals/leaves.
- No device selectors/lists/per-device results anywhere in P4.
- Target modes: `group.create` = **service-scoped** (`target.kind="service"`, `target.did` = Host `serviceDid`; `@target-uri = anp://service/<pct>`); everything else = **group-addressed** (`@target-uri = anp://group/<pct>`); notifications are agent-addressed to the recipient.

### 5.5 Method catalogue
| Method | Target | Auth | Body (MUST / MAY) | Result MUST (MAY) |
|---|---|---|---|---|
| `group.create` | service (`serviceDid`) | origin_proof | `group_policy` MUST; `group_profile` SHOULD; `initial_members[]` MAY (entries: `member_did` MUST, `role` MAY) | `group_did`, `group_state_version`, `created_at`, `creator_did` (`group_event_seq`, `group_profile`, `group_policy`, `group_receipt`) |
| `group.get_info` | group | none required (anonymous OK for `public`/`listed`; identity MUST for `private`) | `include_policy`, `include_member_list` MAY | `group_did`, `group_state_version`, `group_profile` (`group_policy` if permitted, `member_list[]` of `group_member` (active only), `member_count` decimal string) |
| `group.join` | group | origin_proof | `reason_text` MAY; no name/alternate ID; member = `meta.sender_did` | `group_did`, `member_did`, `membership_status="active"`, `group_state_version` (`group_receipt`) |
| `group.add` | group | origin_proof | `member_did` MUST; `role` MAY (default `member`), `reason_text` MAY | `group_did`, `member_did`, `membership_status="active"`, `group_state_version` (`group_receipt`) |
| `group.remove` | group | origin_proof | `member_did` MUST; `reason_text` MAY | `group_did`, `member_did`, `group_state_version` (`membership_status`, `group_receipt`) |
| `group.leave` | group | origin_proof | (sender = leaver) | `group_did`, `leaver_did`, `group_state_version` (`group_receipt`) |
| `group.update_profile` | group | origin_proof | `group_profile_patch` (RFC 7386 JSON Merge Patch) | `group_did`, `group_state_version`, `group_profile` (`group_receipt`) |
| `group.update_policy` | group | origin_proof | `group_policy_patch` (RFC 7386) | `group_did`, `group_state_version`, `group_policy` (`group_receipt`) |
| `group.send` | group | origin_proof | `thread_id`, `reply_to_message_id`, `annotations` MAY; exactly one of `text`/`payload`/`payload_b64u` | `accepted=true`, `group_did`, `message_id`, `operation_id`, `group_event_seq`, `group_state_version`, `accepted_at` (`group_receipt`) |
| `group.incoming` | Notification → agent | lossless copy of origin_proof if present | see below | — |
| `group.state_changed` | Notification → agent | — | exactly one event object | — |
| `group.member_did_update` | **NOT a method** (Host action ID) — client call ⇒ `-32601` | | | |

Processing specifics:
- `group.create`: creator becomes active `owner` identified only by `meta.sender_did`. Host MUST confirm each submitted DID is current/active; superseded ⇒ `anp.did_superseded`, never rewrite the signed request.
- `group.join`: if sender is a successor of an existing active member's superseded DID, run §8.12 DID update first. Not open-join and no membership updated ⇒ reject, SHOULD `group.policy_violation`.
- `group.add`: `member_did` must be current/active; superseded ⇒ `anp.did_superseded`; never replace `body.member_did` in signed request.
- `group.remove`: target must be `active` (else reject); `member_did` MUST equal current roster DID; emits `member-removed` incl. final self-scoped envelope.
- `group.leave`: status → `left`; emits `member-left` incl. final self-scoped envelope to `leaver_did`.
- `group.get_info`: projection outside caller visibility ⇒ `group.policy_violation`. Anonymous reads of public groups SHOULD NOT expose full member list.
- `group.send`: no version concurrency control; Host only checks sender is `active` and has `send` permission.

`group.incoming` envelope (if implemented): `meta.profile="anp.group.base.v2"`; `security_profile` = that at acceptance; `target.kind="agent"`; `target.did` = recipient; `sender_did` = original group message sender; `operation_id`/`message_id`/`content_type` = original. Body (copied):
```json
{
  "group_did": "did:example:group-123",
  "group_state_version": "42",
  "group_event_seq": "128",
  "accepted_at": "2026-03-29T14:10:01Z",
  "group_receipt": { "...": "..." },
  "thread_id": "thr-001",
  "reply_to_message_id": "msg-0009",
  "annotations": {},
  "text": "hello group"
}
```
Receiving domain may fan out locally; never on the wire.

`group.state_changed` envelope: `meta.profile="anp.group.base.v2"`, `security_profile="transport-protected"`, `target.kind="agent"`, `target.did` = recipient, **`meta.sender_did` = `body.group_did`**, body = exactly one event object. MUST NOT carry credentials, non-member reminders, governance notices. Exception: for `member-removed`/`member-left`, Host MUST send one final envelope to `subject_did` (same event object), with bounded retry/retention; Host MUST NOT retain delivery state indefinitely; subject must not treat absence as continued membership; later `group.not_member` is equally authoritative.

### 5.6 Host-coordinated member DID update (§8.12)
Triggers (MAY): DID cache expiry, stored DID deactivated, delivery failure, peer reports superseded DID, request from a possible successor DID. Start from exact stored `agent_did`, verify full transition via P2.
Before accepting MUST: (1) find exactly one active record with old DID; (2) obtain actual assurance; (3) accept `verified`/`recovery_verified`, apply business policy to `provider_asserted`, never `unverified`; (4) new DID not another active member, no ambiguity/fork/cycle/cache conflict; (5) **compare-and-swap** on expected old DID.
After acceptance atomically: replace only `agent_did`; preserve `role`, `status`, `joined_at`, `added_by`, member count; advance `group_state_version` and `group_event_seq`; old DID loses authority; append one `member-did-updated` event + receipt. Operation ID SHOULD be deterministic digest of (`group_did`, `previous_subject_did`, `subject_did`). If a new DID calls `group.send`/`leave`/`update_*`/private `get_info` before refresh, Host completes update first, orders the event, then authorizes. Delivery to an old DID discovering a successor ⇒ update roster before new `group.incoming`.
If group uses E2EE, P6 must independently verify the transition, confirm roster, add new-DID leaves, *then* remove old-DID leaves.

### 5.7 Idempotence (§10.3)
Key `(sender_did, group_did, method, operation_id)`; exact old-DID replay returns prior result before superseded rejection. Optional internal cross-DID index (stable record + group + method + op ID) — never on wire. `group.send` dedup SHOULD use `(sender_did, group_did, message_id)`.

### 5.8 Security / authorization (§11)
- Host MUST verify origin proof; `keyid` DID == `sender_did`; `keyid` in `authentication`; sender DID method-validated.
- Authorization MUST derive from `group_policy.permissions.*` and `admission_mode`.
- Group DID signature is for receipts only (not a second request signature).
- If `message_security_profile = group-e2ee` ⇒ Host MUST reject transport-protected `group.send` and member-only ops. If `bootstrap_security_profile = group-e2ee` ⇒ `group.join` must use P6; no silent downgrade.
- Overlay binding points: `group_did`, `sender_did`, `group_state_version`, `message_id`, `content_type`, `security_profile`, origin-proof digest.
- Access tokens MAY optimize but MUST NOT replace origin proof.

### 5.9 P4 errors (recommended §12)
| code | anp_code | meaning |
|---|---|---|
| 3000 | `group.not_member` | caller not member |
| 3001 | `group.already_member` | target already member |
| 3002 | `group.admission_not_allowed` | join path unavailable / prerequisites unmet |
| 3003 | `group.policy_violation` | violates policy |
| 3005 | `group.member_conflict` | member status conflict |
| 3006 | `group.security_mode_required` | higher security profile required |
| 3007 | `group.host_unavailable` | Host temporarily unavailable |
| 3008 | `group.invalid_origin_proof` | origin proof invalid/expired/missing |
| 3009 | `group.origin_did_mismatch` | `sender_did` vs `keyid` mismatch |
| 3010 | `group.invalid_group_receipt` | receipt signature invalid / mismatched |
(3004 is unassigned.)

### 5.10 P4 MTI (§14)
All 9 methods (`group.create`, `get_info`, `join`, `add`, `remove`, `leave`, `update_profile`, `update_policy`, `send`); `group_did`/`group_state_version`/`group_event_seq`; DID-only members with owner/admin/member; statuses active/left/removed; Host DID updates; `member-did-updated` event + receipts; exact old-DID replay; no device selectors; P4/P6 separation; final self-scoped `group.state_changed` for removed/left.

### 5.11 Examples & inconsistencies
`group.create` (copied, abbreviated auth):
```json
{
  "jsonrpc": "2.0", "id": "req-30001", "method": "group.create",
  "params": {
    "meta": { "profile": "anp.group.base.v2", "security_profile": "transport-protected",
      "sender_did": "did:wba:a.example:agents:alice:e1_<fingerprint>",
      "target": { "kind": "service", "did": "did:wba:groups.example" },
      "operation_id": "op-30001", "created_at": "2026-03-29T12:30:00Z" },
    "auth": { "scheme": "anp-rfc9421-origin-proof-v1", "origin_proof": { "contentDigest": "...", "signatureInput": "...", "signature": "..." } },
    "body": {
      "group_profile": { "display_name": "Cross-Domain Agents", "description": "Collaboration Group", "discoverability": "private" },
      "group_policy": { "message_security_profile": "transport-protected", "bootstrap_security_profile": "transport-protected",
        "admission_mode": "admin-add",
        "permissions": { "send": "member", "add": "admin", "remove": "admin", "update_profile": "admin", "update_policy": "owner" },
        "attachments_allowed": true, "max_members": "500" },
      "initial_members": [ { "agent_did": "did:wba:a.example:agents:alice:e1_<fingerprint>", "role": "owner" } ] } }
}
```
Response: `group_did`, `group_state_version: "1"`, `group_event_seq: "1"`, `created_at`, `creator_did`, `group_receipt` (`receipt_type: "group-operation-accepted"`, `subject_method: "group.create"`, `proof.verificationMethod: "<group_did>#assert-1"`, `proofValue: "zBASE58MULTIBASE_PROOF"`).
`group.send` response (copied):
```json
{ "jsonrpc": "2.0", "id": "req-30004", "result": {
  "accepted": true, "group_did": "did:wba:groups.example:team:dev:e1_<fingerprint>",
  "message_id": "msg-30004", "operation_id": "msg-30004", "group_event_seq": "9", "group_state_version": "2",
  "accepted_at": "2026-03-29T12:50:01Z",
  "group_receipt": { "receipt_type": "group-message-accepted", "group_did": "did:wba:groups.example:team:dev:e1_<fingerprint>",
    "group_state_version": "2", "group_event_seq": "9", "subject_method": "group.send", "operation_id": "msg-30004",
    "message_id": "msg-30004", "actor_did": "did:wba:a.example:agents:alice:e1_<fingerprint>", "accepted_at": "2026-03-29T12:50:01Z",
    "payload_digest": "sha-256=:BASE64_SHA256_OF_SIGNED_REQUEST_OBJECT:",
    "proof": { "type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022",
      "verificationMethod": "did:wba:groups.example:team:dev:e1_<fingerprint>#assert-1", "proofPurpose": "assertionMethod",
      "created": "2026-03-29T12:50:01Z", "proofValue": "zBASE58MULTIBASE_PROOF" } } } }
```
**Inconsistencies:**
- §8.1.2 says `initial_members` entries MUST contain `member_did` (creator is implicit owner), but §15.1 example uses `agent_did` and lists the creator as owner. Recommend: accept `member_did` (normative) and tolerate/ignore a creator self-entry; don't emit `agent_did` in requests.
- `group.send` JSON example (req-30005) omits `auth`, contradicting §7.7/§8.9.2.
- `group.create` result example omits `group_event_seq` from required but includes it (fine — MAY).
- `group.create` "auth MUST" vs §7.7 "all state-changing except group.get_info" — consistent.
- `group.state_changed` `meta.sender_did = group_did` — there is no explicit statement whether it carries an origin proof; group_receipt inside event provides the Host witness.

---

## 6. P5 Direct E2EE — `anp.direct.e2ee.v2` (Released; deps P1, P2, P3 + ANP-02 identity inputs)

### 6.1 Model
- Overlay on `direct.send`; business sender/recipient still `meta.sender_did` / `meta.target.did`. P5 **requires** `meta.sender_device_id` and `meta.recipient_device_id` to pick exactly one **device pair** `(sender_did, sender_device_id, recipient_did, recipient_device_id)`.
- One logical DID→DID message ⇒ **one independently encrypted `direct.send` per recipient device**, each with its own `message_id` = `operation_id`. Service MUST NOT share ratchet state or do hidden cryptographic fan-out. Sibling ciphertexts MAY share an inner encrypted `logical_message_id` (correlation only; never routing/idempotency/accepted-result input).
- Not defined: device enrollment, history pull, **read status**, presence, group E2EE, copying keys/ratchets/plaintext across devices.
- `anp.direct.e2ee.v1` is a separate single-endpoint contract; MUST NOT infer a device for a v1 peer, reuse v1 state, or downgrade v2 → v1 / P3.
- **Ratchet design: X3DH-like + Double-Ratchet-like** (not HPKE, not MLS).
- MTI suite: `ANP-DIRECT-E2EE-X3DH-25519-CHACHA20POLY1305-SHA256-V1` (trailing `V1` is the suite version; MUST NOT be renamed `V2`). Params: X25519 static + ephemeral, HKDF-SHA-256, ChaCha20-Poly1305, Bundle proof = P1 App. B (`eddsa-jcs-2022`). All JCS (RFC 8785) + UTF-8 for protected Bundle doc, `AD_init`, `AD_msg`, Application Plaintext.
- Optional suites: `ANP-DIRECT-E2EE-X3DH-25519-AES256GCM-SHA256-V1`; `ANP-DIRECT-E2EE-PQXDH-HYBRID-V1` (reserved). MTI support always required.
- Init messages are **not** long-term signed by default (deniability). Optional, non-MTI "Direct Init Accountability Extension" may add `params.auth`.

### 6.2 Wire rules for `direct.send` under P5
- `meta.profile = "anp.direct.e2ee.v2"`, `meta.security_profile = "direct-e2ee"`, `meta.target.kind = "agent"`.
- `meta.content_type` ∈ { `application/anp-direct-init+json`, `application/anp-direct-cipher+json` } only (MTI path); other values rejected unless extension negotiated.
- `meta.message_id` and `meta.operation_id` MUST exist and be **equal**; unique per recipient device.
- `params.auth` MUST be **absent** (receiver MUST reject it unless accountability extension negotiated). Origin binding equivalence to P3 §9.7 is via `AD_init`, `AD_msg`, and AEAD-protected Application Plaintext.

### 6.3 DID / key requirements (§4)
- DID Doc: ≥1 authentication key + assertion key; ≥1 `keyAgreement`; `ANPMessageService` with per-device key-material methods; current `deviceManifest` entries with full P1/P2/P3/P5 profile set.
- Current device eligibility check for `(D, d)` (§4.1.1): `d` selects exactly one current Manifest entry under `D`; entry declares `anp.direct.e2ee.v2` + P1/P2/P3; `signing_key_id` = Bundle-proof signing method; `e2ee_key_id` = X25519 method in `keyAgreement`; Bundle/Session/AAD/replay/Mailbox all use the same DID/device/key refs. Failure ⇒ reject new material and ciphertext, stop using affected caches & sessions, re-resolve DID. Other device pairs unaffected.
- Key role separation: `assertionMethod` key signs Bundles (no DH); `keyAgreement` key does static DH; MUST NOT be the same key. Each device owns separate signing + X25519 keys, SPK/OPK private keys, sessions, ratchet, skipped keys, replay state; devices MUST NOT share key references.

### 6.4 Key-material service capabilities (§4.4)
Per `(owner_did, owner_device_id)`, `ANPMessageService` MUST support: publish Bundle; replenish/rotate OPK pool; query Bundle; issue one OPK per query; mark OPK allocated/consumed; return revoked/invalidated status (if supported); stop serving when device loses eligibility.

### 6.5 `prekey_bundle` (§6.2–6.5) (copied)
```json
{
  "bundle_id": "bundle-20260329-001",
  "owner_did": "did:wba:example.com:agent:alice:e1_xxx",
  "owner_device_id": "dev-a-7N3KQ2",
  "suite": "ANP-DIRECT-E2EE-X3DH-25519-CHACHA20POLY1305-SHA256-V1",
  "static_key_agreement_id": "did:wba:example.com:agent:alice:e1_xxx#ka-1",
  "signed_prekey": { "key_id": "spk-001", "public_key_b64u": "BASE64URL_X25519_SPK", "expires_at": "2026-04-05T00:00:00Z" },
  "proof": { "type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022",
    "verificationMethod": "did:wba:example.com:agent:alice:e1_xxx#assert-1", "proofPurpose": "assertionMethod",
    "created": "2026-03-29T00:00:00Z", "proofValue": "zBASE58MULTIBASE_PROOF" }
}
```
- MUST contain: `bundle_id`, `owner_did`, `owner_device_id`, `suite`, `static_key_agreement_id`, `signed_prekey`, `proof`. MUST NOT contain `one_time_prekey`.
- Proof issuer = `owner_did`; VM ∈ `assertionMethod`; protected doc = bundle minus `proof`. Invalid ⇒ `anp.direct.e2ee.bundle_invalid` (4001).
- `bundle_id` uniquely maps (within acceptance window) to owner_did, owner_device_id, suite, static_key_agreement_id, spk.key_id, spk.public_key_b64u; never redefined. Multiple concurrent bundle IDs allowed in grace period; recipient retains SPK private key until window ends.
- Sender verification before use (§6.5): (1) resolve DID, validate device; (2) `proof.verificationMethod` == Manifest `signing_key_id` and in `assertionMethod`; (3) verify proof; (4) `static_key_agreement_id` == Manifest `e2ee_key_id` and in `keyAgreement`; (5) suite supported; (6) SPK not expired; (7) record OPK `key_id` if returned; (8) `recipient_signed_prekey_id` = `signed_prekey.key_id`.
- OPK object: `{ "key_id": "opk-001", "public_key_b64u": "BASE64URL_X25519_OPK" }`. OPK use SHOULD (MAY omit). Server SHOULD mark allocated on return; MUST NOT hand the same OPK to multiple senders/pairs; MUST mark consumed after successful init; receiver MUST delete OPK private key; recycling unconsumed allocated OPKs = deployment policy; a used OPK never re-issued.

### 6.6 Key-service methods (§7) — both **service-scoped**, `security_profile = "transport-protected"`, `params.auth` absent, auth via hop/service-level authenticated session
`direct.e2ee.publish_prekey_bundle`
- meta: `profile="anp.direct.e2ee.v2"`, `security_profile="transport-protected"`, `target={kind:"service", did: publisher's own serviceDid}`, `sender_did`, `sender_device_id`, `operation_id`.
- body: `prekey_bundle` (MUST; `owner_did`==`sender_did`, `owner_device_id`==`sender_device_id`), `one_time_prekeys[]` (MAY; non-empty; each `key_id` + `public_key_b64u`).
- Authenticated context MUST identify exact `(sender_did, sender_device_id)`, currently eligible; server MUST check caller authorized to publish for `owner_did`.
- Idempotency key: `(sender_did, sender_device_id, target.did, method, operation_id)`.
- Result MUST: `published=true`, `owner_did`, `owner_device_id`, `bundle_id`, `published_at`; MAY `published_opk_count`.

`direct.e2ee.get_prekey_bundle`
- meta same pattern, `target.did` = target Agent's `serviceDid`.
- body MUST: `target_did`, `target_device_id`; MAY: `preferred_suite`, `require_opk`.
- Requester must be an eligible `(sender_did, sender_device_id)`; service validates `(target_did, target_device_id)`; MUST NOT return sibling-device material. Anonymous fetch not MTI.
- Result MUST: `target_did`, `target_device_id` (== request == `prekey_bundle.owner_device_id`), `prekey_bundle`; MAY `one_time_prekey`.
- `require_opk=true` and none ⇒ SHOULD explicit error (`anp.direct.e2ee.opk_unavailable` 4003).
- Idempotency key `(sender_did, sender_device_id, target_did, target_device_id, target.did, method, operation_id)`; retry after OPK allocation MUST return same bundle + same OPK (after re-validating eligibility); idempotency record write + OPK allocation MUST be **atomic**; no re-allocation on retry.

Example publish (copied):
```json
{
  "jsonrpc": "2.0", "id": "req-50001", "method": "direct.e2ee.publish_prekey_bundle",
  "params": {
    "meta": { "profile": "anp.direct.e2ee.v2", "security_profile": "transport-protected",
      "sender_did": "did:wba:example.com:agent:alice:e1_xxx", "sender_device_id": "dev-a-7N3KQ2",
      "target": { "kind": "service", "did": "did:wba:example.com" },
      "operation_id": "op-50001", "created_at": "2026-03-29T12:00:00Z" },
    "body": { "prekey_bundle": { "...": "as above" },
      "one_time_prekeys": [ { "key_id": "opk-001", "public_key_b64u": "BASE64URL_X25519_OPK_001" },
                            { "key_id": "opk-002", "public_key_b64u": "BASE64URL_X25519_OPK_002" } ] } }
}
```

### 6.7 X3DH-like session establishment (§8, §9.4)
Keys: sender device `KA_A` (static X25519 = Manifest `e2ee_key_id`), `EK_A` (fresh ephemeral); recipient device `KA_B` (static), `SPK_B`, optional `OPK_B`.
```text
DH1 = DH(KA_A, SPK_B)
DH2 = DH(EK_A, KA_B)
DH3 = DH(EK_A, SPK_B)
[DH4 = DH(EK_A, OPK_B)]            # only if OPK returned
IKM = DH1 || DH2 || DH3 [|| DH4]
PRK = HKDF-Extract(salt = 0x00*32, IKM)
SK  = HKDF-Expand(PRK, info = "ANP Direct E2EE v1 Initial Secret", L = 32)
RK0 = HKDF-Expand(SK, info = "ANP Direct E2EE v1 Root Key",  L = 32)
CK0 = HKDF-Expand(SK, info = "ANP Direct E2EE v1 Chain Key", L = 32)
SID = HKDF-Expand(SK, info = "ANP Direct E2EE v1 Session ID", L = 16)
session_id = base64url(SID)
CK1, MK0, NONCE0 = kdf_ck(CK0)     # init consumes message 0 of A->B chain
```
(Note: HKDF-Expand over `SK` directly as PRK — `SK` is used as the PRK input for the three Expand calls.)

KDFs (§10.2.1):
```text
kdf_rk(RK, dh_out) -> (RK', CK):
  PRK = HKDF-Extract(salt = RK, IKM = dh_out)
  OUT = HKDF-Expand(PRK, info = "ANP Direct E2EE v1 KDF_RK", L = 64);  RK' = OUT[0:32]; CK = OUT[32:64]
kdf_ck(CK) -> (CK', MK, NONCE):
  PRK = HKDF-Extract(salt = 0x00*32, IKM = CK)
  OUT = HKDF-Expand(PRK, info = "ANP Direct E2EE v1 KDF_CK", L = 76);  CK' = OUT[0:32]; MK = OUT[32:64]; NONCE = OUT[64:76] (12 bytes)
```
Nonce never transmitted; `ciphertext_b64u` = AEAD ciphertext+tag only.

`application/anp-direct-init+json` body (copied):
```json
{
  "session_id": "BASE64URL_16_BYTES",
  "suite": "ANP-DIRECT-E2EE-X3DH-25519-CHACHA20POLY1305-SHA256-V1",
  "sender_static_key_agreement_id": "did:wba:example.com:agent:alice:e1_xxx#ka-1",
  "recipient_bundle_id": "bundle-20260329-001",
  "recipient_signed_prekey_id": "spk-001",
  "recipient_one_time_prekey_id": "opk-001",
  "sender_ephemeral_pub_b64u": "BASE64URL_X25519_EK_A",
  "ciphertext_b64u": "BASE64URL_INIT_CIPHERTEXT"
}
```
MUST: all except `recipient_one_time_prekey_id` (MAY). Init ciphertext MUST carry a complete Application Plaintext (no empty init).

`AD_init` = UTF-8 JCS bytes of:
```json
{
  "content_type": "application/anp-direct-init+json",
  "message_id": "<outer meta.message_id>", "operation_id": "<outer meta.operation_id>",
  "profile": "anp.direct.e2ee.v2", "security_profile": "direct-e2ee",
  "sender_did": "<outer meta.sender_did>", "sender_device_id": "<outer meta.sender_device_id>",
  "recipient_did": "<outer meta.target.did>", "recipient_device_id": "<outer meta.recipient_device_id>",
  "suite": "<body.suite>", "recipient_bundle_id": "<body.recipient_bundle_id>",
  "sender_static_key_agreement_id": "<body.sender_static_key_agreement_id>",
  "recipient_signed_prekey_id": "<body.recipient_signed_prekey_id>",
  "recipient_one_time_prekey_id": "<body.recipient_one_time_prekey_id>",
  "session_id": "<body.session_id>"
}
```
Omit `recipient_one_time_prekey_id` when absent (no null/empty placeholders).

Recipient pre-checks before any state change (§9.4.1): both device endpoints currently eligible; `sender_static_key_agreement_id` == sender Manifest `e2ee_key_id`; `recipient_bundle_id` belongs to the outer recipient device and SPK belongs to that bundle; OPK belongs to same device pool; derived `session_id` == `body.session_id`.

Session index MUST include `(local_did, local_device_id, peer_did, peer_device_id, session_id, suite, local_e2ee_key_id, peer_e2ee_key_id)`; never merge across device pairs.

State machine:
- Initiator after sending init: `RK=RK0, DHs=EK_A, DHr=null, CKs=CK1, CKr=null, Ns=1, Nr=0, PN=0, MKSKIPPED={}, status="pending-confirmation"`. MUST NOT send separate `direct-cipher` while pending (buffer locally; idempotent init retries OK).
- Responder after decrypting init: consume OPK; `RK=RK0, DHr=EK_A, CKr=CK1, Nr=1, DHs=GenerateRatchetKeyPair(), (RK,CKs)=kdf_rk(RK, DH(DHs,DHr)), Ns=0, PN=0, MKSKIPPED={}, status="established"`.
- Responder first reply: `direct-cipher` with `ratchet_header = {dh_pub_b64u: DHs.public, pn:"0", n:"0"}`; key/nonce via `kdf_ck(CKs)`; then `Ns=1`.
- Initiator on first reply (must have `pn="0"`, `n="0"`, else `bad_init_message`/`invalid_security_binding`, no state change): DH ratchet step (`(RK,CKr)=kdf_rk(RK, DH(DHs, DHr_new))`, `DHr=DHr_new`, `PN=Ns`, `Ns=0`, `Nr=0`, new `DHs`, `(RK,CKs)=kdf_rk(RK, DH(DHs_new, DHr))`), `kdf_ck(CKr)` → decrypt with `AD_msg`; on success `CKr=CKr_next, Nr=1, status="established"`; on failure roll back entirely.

### 6.8 Double-Ratchet-like steady state (§10)
Session state MUST store: `session_id`, `suite`, `local_agent_did`, `local_device_id`, `peer_did`, `peer_device_id`, `local_e2ee_key_id`, `peer_e2ee_key_id`, `RK`, `DHs`, `DHr`, `CKs`, `CKr`, `Ns`, `Nr`, `PN`, `MKSKIPPED`, `status`.
Ratchet header: `{ "dh_pub_b64u": "...", "pn": "12", "n": "3" }` (all MUST; decimal strings).
- `RatchetEncrypt`: `CKs', MK, NONCE = kdf_ck(CKs)`; header `{DHs.public, decimal(PN), decimal(Ns)}`; build `AD_msg`; encrypt; `CKs=CKs'`, `Ns++`.
- `TrySkippedMessageKeys`: lookup `MKSKIPPED[(dh_pub_b64u, n)]`; always delete entry after try; failure ⇒ `decrypt_failed`.
- `SkipMessageKeys(until_n)`: no-op if `until_n < Nr`; `until_n - Nr > MAX_SKIP` ⇒ `max_skip_exceeded`; else derive and store skipped keys keyed `(DHr, Nr)`.
- `RatchetDecrypt`: try skipped → if new `dh_pub` do DH ratchet step (process `pn` skipped keys on old chain first) → `n < Nr` & not skipped ⇒ `decrypt_failed` → skip to `n` → `kdf_ck(CKr)` → decrypt with `AD_msg` → commit `CKr`, `Nr++`. Use tentative state; failure MUST NOT consume `CKr`/advance `Nr`.
- `MAX_SKIP` MUST be defined; recommended 1000; non-default value must be exposed via capability negotiation. Skipped-key deletion SHOULD be deterministic (by message count / ratchet steps), per session; never shared across pairs.
- Header encryption not MTI (if supported, advertise + define rules).

`application/anp-direct-cipher+json` body:
```json
{ "session_id": "BASE64URL_16_BYTES",
  "ratchet_header": { "dh_pub_b64u": "BASE64URL_DH_PUB", "pn": "12", "n": "3" },
  "ciphertext_b64u": "BASE64URL_CIPHERTEXT" }
```
`suite` MAY be present (must equal session suite).

Inner Application Plaintext (JCS-serialized before AEAD):
```json
{
  "application_content_type": "text/plain | application/json | application/anp-attachment-manifest+json | ...",
  "logical_message_id": "logical-8c9651",
  "conversation_id": "conv-001",
  "reply_to_message_id": "msg-0001",
  "annotations": {},
  "text": "...", "payload": {}, "payload_b64u": "..."
}
```
`application_content_type` MUST; `logical_message_id` MAY (non-empty); exactly one of `text`/`payload`/`payload_b64u`; omit absent optionals (no null/""); `annotations` omitted or `{}`.

`AD_msg` = UTF-8 JCS bytes of:
```text
{ "content_type": "application/anp-direct-cipher+json",
  "message_id": "<outer>", "operation_id": "<outer>",
  "profile": "anp.direct.e2ee.v2", "security_profile": "direct-e2ee",
  "sender_did": "<outer>", "sender_device_id": "<outer>",
  "recipient_did": "<outer meta.target.did>", "recipient_device_id": "<outer>",
  "session_id": "<body.session_id>", "ratchet_header": { ... exactly as sent ... } }
```
`attachment_manifest_digest` AAD binding is NOT MTI.

### 6.9 Device-qualified send, Mailbox, `direct.incoming` (§10.7)
Target service MUST before accepting: (1) both devices currently eligible; (2) Bundle/Session/AAD device pair == outer meta; (3) idempotency key `(sender_did, sender_device_id, recipient_did, recipient_device_id, method, operation_id)`; (4) enqueue opaque ciphertext **only** in Mailbox `(recipient_did, recipient_device_id)`; (5) never decrypt/re-encrypt/fan out to siblings.
Result MUST: `accepted=true`, `message_id`, `operation_id`, `target_did`, **`recipient_device_id`**, `accepted_at`; no device-result arrays.
```json
{ "jsonrpc": "2.0", "id": "req-50003", "result": { "accepted": true, "message_id": "msg-50003", "operation_id": "msg-50003",
  "target_did": "did:wba:example.org:agent:bob:e1_yyy", "recipient_device_id": "dev-b-4M8P1X", "accepted_at": "2026-03-29T12:02:01Z" } }
```
Mailbox: opaque per-(DID, device) queue, may hold multiple sessions, no ratchet state; no history-pull, read-receipt, or device-sync methods defined.
P5 `direct.incoming`: Notification; `meta.profile="anp.direct.e2ee.v2"`; preserve profile, security_profile, both DIDs, both selectors, message_id, operation_id, content_type and unchanged body; deliver only to `recipient_device_id`; relays MUST NOT add/remove/infer/rewrite selectors or change Profile to P3; destination revalidates eligibility before enqueue/delivery; `params.auth` absent unless extension.

### 6.10 Replay / idempotence (§11)
- Outer idempotency key includes both DIDs + both devices; checked **before** advancing ratchet.
- Replay dimensions: `session_id`, `sender_device_id`, `recipient_device_id`, `message_id`, `ratchet_header.dh_pub_b64u`, `ratchet_header.n`, optional ciphertext digest.
- Init replay record key: `(recipient_did, recipient_device_id, recipient_bundle_id, sender_did, sender_device_id, sender_ephemeral_pub_b64u, session_id)`. Same op ID + same init replay key ⇒ idempotent retry; same init replay key + different op/message ID ⇒ `anp.direct.e2ee.replay_detected`. Duplicate `direct-cipher` MUST NOT advance ratchet.

### 6.11 Re-establishment, device changes, DID transitions (§12)
- Rebuild SHOULD on: repeated decrypt failures; explicit instruction; suite change; device removed/key changed/eligibility lost; policy. Rebuild = new `direct-init` (no separate rekey protocol).
- Multiple `session_id`s MAY coexist per `(local_did, local_device_id, peer_did, peer_device_id, suite)`; default outbound = most recent `established`; none ⇒ new init. Unknown `session_id` ⇒ `anp.direct.e2ee.session_not_found`.
- `application/anp-direct-control+json` (`reset`/`close`/`error`) is NOT MTI; reject unless negotiated.
- Device removal: stop publishing/returning its PreKeys, stop Mailbox enqueue/delivery, stop affected sessions. New devices get only messages sent after eligibility; no history copying.
- DID transition: stop new ciphertext on old-DID sessions; resolve successor's Manifest; fresh PreKeys; new session per device pair; rebuild AAD/ciphertext/outer fields; MUST NOT reuse old-DID session/ratchet/keys/skipped/replay state.

### 6.12 P5 errors (fixed 4000–4012; `error.data.anp_code` MUST)
| code | anp_code |
|---|---|
| 4000 | `anp.direct.e2ee.bundle_not_found` |
| 4001 | `anp.direct.e2ee.bundle_invalid` |
| 4002 | `anp.direct.e2ee.bundle_expired` |
| 4003 | `anp.direct.e2ee.opk_unavailable` |
| 4004 | `anp.direct.e2ee.missing_key_agreement` |
| 4005 | `anp.direct.e2ee.session_not_found` |
| 4006 | `anp.direct.e2ee.session_conflict` |
| 4007 | `anp.direct.e2ee.bad_init_message` |
| 4008 | `anp.direct.e2ee.replay_detected` |
| 4009 | `anp.direct.e2ee.decrypt_failed` |
| 4010 | `anp.direct.e2ee.max_skip_exceeded` |
| 4011 | `anp.direct.e2ee.reset_required` |
| 4012 | `anp.direct.e2ee.invalid_security_binding` |
Selector/Manifest issues use Core 1015–1018; after eligibility passes, Bundle owner/key/session/AAD/Mailbox mismatch ⇒ 4012. `error.data` SHOULD include `target_did`, `bundle_id`, `opk_id`, `session_id`, `required_security_profile`, `retryable`. Never leak sibling-device inventory, private state, topology.
**Note:** P5 error `anp_code`s are prefixed `anp.direct.e2ee.*` while P3 uses `direct.*` and P4 `group.*` — inconsistent naming, but these are the spec strings.

### 6.13 Security boundaries (§14)
Bind DIDs, device IDs, key IDs, bundle_id, session_id in `AD_init`. SPK binding to `assertionMethod` cannot be skipped. Malicious key service can still DoS/refuse OPKs — SHOULD add transparency logs. Not post-quantum. Default: no long-term attribution of control objects.

### 6.14 P5 MTI (§15) — 26 items, summarized
Parse `authentication`/`assertionMethod`/`keyAgreement`/`ANPMessageService`; publish/get bundle (+OPK pool if claiming OPK); service-scoped target for key methods; verify bundle proof (App. B); MTI X3DH-like; only init/cipher content types; `operation_id == message_id`; no `params.auth`; carry init/cipher via `direct.send`; fixed `kdf_rk`/`kdf_ck`/nonce; init consumes msg 0, continue from `CK1`; init carries full Application Plaintext; initiator waits for first reply; Double Ratchet state; RatchetEncrypt/Decrypt/Skip/TrySkipped; `MAX_SKIP` + `MKSKIPPED`; idempotent key methods with same-OPK retry; init replay protection; device validation against current Manifest; device IDs in AAD/session index/replay keys/idempotency keys and `message_id`+`operation_id` in both AADs; one ciphertext per recipient device; Mailbox per (DID, device), selectors preserved cross-domain; per-device-pair state isolation; `logical_message_id` correlation-only; no device metadata leakage.

---

## 7. P6 Group E2EE — `anp.group.e2ee.v2` (**Candidate**; deps P1, P2, P4)

### 7.1 Status and gate
- Included in 1.2 docs but **stable v2 release is gated** on a registered MLS `ExtensionType` for `anp_did_wba_device_binding`. Draft uses **provisional private-use `0xF0A1`** (not IANA). It MUST be used only after `anp.group.e2ee.v2` is explicitly negotiated; ANP must publish a stable code point before v2 release; changing the draft value = breaking draft revision. ⇒ For production, treat P6 as experimental; do not advertise it to unknown peers unless you accept candidate-status interop.
- `anp.group.e2ee.v1` is a separate contract; no in-place v1→v2 state upgrade; fail closed.

### 7.2 Model
- **MLS 1.0** (RFC 9420) as group key state machine. Restricted subset: KeyPackage, Add, Remove, Commit, Welcome, PrivateMessage, epoch advancement. **Not** in v2 interop: External Commit, GroupInfo/`group_join_info`, `group.e2ee.get_join_info`, `accept_welcome` method, multiple concurrent controllers, non-owner membership Commits, `Update` as protocol action, proposal batching, ReInit, PSK, Subgroup, other custom extensions.
- MTI suite: `MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519` (DHKEMX25519, AES-128-GCM, SHA-256, Ed25519 leaf sig). All group members agree on suite.
- **One Agent DID = one P4 member; each device = one MLS leaf.** `credential.identity = UTF8(agent_did)` for every leaf; sibling leaves distinguished by authenticated `device_id` (via `did_wba_binding`). Leaf identity = `(agent_did, device_id)` pair.
- Each device has its own KeyPackage private material, leaf key, epoch secrets, MLS state — never copied.
- Four coordinates bound but distinct: `group_did`, `crypto_group_id` (MLS group_id; opaque bytes, `crypto_group_id_b64u`), `group_state_version` (P4), `epoch` (MLS, decimal string).
- **Owner is the sole general MLS controller** (create/add/remove/DID-update Commits), submitted from an owner device that holds current MLS state. Narrow exception: an eligible same-DID leaf with authoritative device-management authorization MAY remove a *different, already-revoked/ineligible* device leaf of its own DID (exactly one leaf; not self; not P4 member removal). Admins only affect P4 state.
- Group Host orders, assigns `group_event_seq`, issues receipts, distributes per-device envelopes; SHOULD NOT be MLS controller/member; SHOULD NOT hold plaintext; MUST NOT copy private state; never decrypts/re-encrypts.
- **State coupling** (not method mapping): owner observes P4 state (via `group.state_changed`, internal orchestration, etc.) and drives P6:
  - group created, no `crypto_group_id` ⇒ owner MUST `group.e2ee.create` once
  - member `active` and eligible device has no leaf + KeyPackage available ⇒ owner MUST `group.e2ee.add` for that device (repeat per device)
  - member `left`/`removed` ⇒ owner MUST `group.e2ee.remove` every leaf of that DID
  - device loses Manifest eligibility (DID still active) ⇒ owner or authorized same-DID sibling MAY remove only that leaf
  - `member-did-updated` ⇒ Add every selected new-DID device, then Remove every old-DID leaf
- Only `group.e2ee.send` content is MLS-encrypted; control requests are plaintext JSON-RPC.

### 7.3 Security profiles & targets (§4)
| Method | security_profile | Target mode |
|---|---|---|
| `group.e2ee.publish_key_package` | `transport-protected` | service-scoped (own serviceDid) |
| `group.e2ee.get_key_package` | `transport-protected` | service-scoped (target Agent's serviceDid) |
| `group.e2ee.create` | `group-e2ee` | service-scoped (Group Host serviceDid) |
| `group.e2ee.add` | `group-e2ee` | group-addressed |
| `group.e2ee.remove` | `group-e2ee` | group-addressed |
| `group.e2ee.send` | `group-e2ee` | group-addressed |
| `group.e2ee.notice` (Notification) | `transport-protected` | agent-addressed + `recipient_device_id` |
| P6 `group.incoming` (Notification) | `group-e2ee` | agent-addressed + `recipient_device_id` |
Every device-originated P6 request MUST have `meta.sender_device_id`; every device-targeted notification MUST have `meta.recipient_device_id`.

### 7.4 Device binding (§6)
`did_wba_binding` (name retained for all DID methods):
```json
{
  "agent_did": "did:wba:example.com:agents:alice:e1_<fingerprint>",
  "device_id": "dev-a-7N3KQ2",
  "verification_method": "did:wba:example.com:agents:alice:e1_<fingerprint>#dev-a-sign",
  "leaf_signature_key_b64u": "BASE64URL_ED25519_LEAF_PK",
  "issued_at": "2026-03-29T12:00:00Z",
  "expires_at": "2026-04-29T12:00:00Z",
  "proof": { "type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022", "created": "2026-03-29T12:00:00Z",
    "proofPurpose": "assertionMethod", "verificationMethod": "did:wba:example.com:agents:alice:e1_<fingerprint>#dev-a-sign", "proofValue": "z..." }
}
```
- Issuer = `agent_did`; `verification_method` == `proof.verificationMethod` == Manifest `signing_key_id` (in `assertionMethod`).
- **MLS extension `anp_did_wba_device_binding`, ExtensionType `0xF0A1`**: `extension_data` = UTF-8 JCS bytes of the full `did_wba_binding` incl. proof. KeyPackage LeafNode MUST contain exactly one; retained LeafNode preserves it; LeafNode `capabilities.extensions` and GroupContext `required_capabilities` MUST list `0xF0A1`. Reject missing/duplicate/malformed/colliding. Sibling JSON `group_key_package.did_wba_binding` MUST have identical JCS bytes.
- Verification (11 steps): method-validate DID; `device_id` exactly once in Manifest with `anp.group.e2ee.v2`+deps; VM == current `signing_key_id` in `assertionMethod`; proof valid (App. B) with issuer `agent_did`; protected doc covers agent_did/device_id/verification_method/leaf key/issued_at/expires_at; extension + capabilities present; byte-identical; leaf public key matches; `credential.identity` == `agent_did`; suite/policy/time window valid.
- Leaf signature key SHOULD be separate from DID identity key. `k1_` DIDs: alternative proof only via explicit extension negotiation.

### 7.5 Core objects
`group_key_package`: `key_package_id`, `owner_did`, `owner_device_id`, `suite`, `mls_key_package_b64u` (TLS-serialized MLS KeyPackage), `did_wba_binding` (all MUST), `expires_at` (SHOULD). One KeyPackage = one device; consumed after successful add (unless deployment declares last-resort exception).
`group_cipher_object` (body of `group.e2ee.send`):
```json
{ "crypto_group_id_b64u": "BASE64URL_GROUPID", "epoch": "7", "private_message_b64u": "BASE64URL_PRIVATEMESSAGE",
  "group_state_ref": { "group_did": "did:wba:groups.example:team:dev:e1_<fingerprint>", "group_state_version": "42", "policy_hash": "sha-256:..." },
  "epoch_authenticator": "BASE64URL_AUTH" }
```
`crypto_group_id_b64u`, `epoch`, `private_message_b64u` MUST; `group_state_ref.group_did` == outer target.
Group Application Plaintext (inside PrivateMessage; JCS): `application_content_type` (MUST), `thread_id`, `reply_to_message_id`, `annotations`, exactly one of `text`/`payload`/`payload_b64u`.
`e2ee_notice_object`: `notice_id` (MUST; stable across redeliveries; dedupe key `(group_did, notice_id)` per device), `notice_type` (`commit-delivery`|`welcome-delivery`), `group_did`, `group_state_ref`, `crypto_group_id_b64u`, `epoch` (all MUST), `subject_did`, `subject_device_id`, `subject_status` (`active`|`removed`), `commit_b64u` (MUST for commit-delivery), `welcome_b64u` + `ratchet_tree_b64u` (MUST for welcome-delivery), `epoch_authenticator`, `group_receipt` (MAY).
Encodings: `commit_b64u` = TLS-serialized full `MLSMessage` (wire format `mls-public-message`); `welcome_b64u` = TLS `Welcome`; `private_message_b64u` = TLS `PrivateMessage`; `ratchet_tree_b64u` = TLS ratchet tree (always explicitly provided to new members).

### 7.6 Methods
| Method | Caller | Body MUST | Result MUST |
|---|---|---|---|
| `group.e2ee.publish_key_package` | any eligible device (hop/service auth; no origin_proof) | `group_key_package` (owner == sender pair) | `published=true`, `owner_did`, `owner_device_id`, `key_package_id`, `published_at` |
| `group.e2ee.get_key_package` | eligible device (hop/service auth; anonymous not MTI) | `target_did`, `target_device_id` (MAY `preferred_suite`, `require_fresh`) | `target_did`, `target_device_id`, `group_key_package` (exact pair; never sibling; MAY mark `reserved`; mark `consumed` after add) |
| `group.e2ee.create` | owner device; `auth.origin_proof` MUST | `group_did`, `group_state_ref`, `suite`, `creator_key_package`, `crypto_group_id_b64u`, `epoch` (SHOULD `"0"`) | `created=true`, `group_did`, `group_state_ref`, `crypto_group_id_b64u`, `epoch`, `accepted_at` |
| `group.e2ee.add` | owner device; origin_proof | `member_did`, `member_device_id`, `group_state_ref`, `group_key_package`, `crypto_group_id_b64u`, `epoch` (new), `commit_b64u`, `welcome_b64u`, `ratchet_tree_b64u` | `accepted=true`, `group_did`, `member_did`, `member_device_id`, `group_state_ref`, `crypto_group_id_b64u`, `epoch`, `accepted_at` |
| `group.e2ee.remove` | owner device, or same-DID exception; origin_proof | `member_did`, `member_device_id`, `group_state_ref`, `crypto_group_id_b64u`, `epoch` (new), `commit_b64u` | same as add |
| `group.e2ee.send` | any eligible current leaf of active member; origin_proof with device's current signing key; `content_type="application/anp-group-cipher+json"`; `message_id`, `operation_id` | `group_cipher_object` | `accepted=true`, `group_did`, `message_id`, `operation_id`, `group_event_seq`, `group_state_version`, `accepted_at`, `epoch`, `group_receipt` |
`create/add/remove` do NOT create P4 state or advance `group_state_version`/`group_event_seq` independently. `group.e2ee.send` is NOT wrapped in `group.send`. Rejoin after leaf removal = normal Add with fresh KeyPackage (no rejoin method; no restoring old epoch secrets).

`authenticated_data` for `group.e2ee.send` (JCS):
```json
{ "content_type": "application/anp-group-cipher+json", "group_did": "<outer meta.target.did>",
  "crypto_group_id_b64u": "<body>", "group_state_ref": { "...": "..." }, "security_profile": "group-e2ee",
  "sender_did": "<outer>", "sender_device_id": "<outer>", "message_id": "<outer>", "operation_id": "<outer>" }
```
Commit binding for add/remove (SHOULD): `group_did`, `crypto_group_id_b64u`, `group_state_ref`, `subject_method`, `member_did`, `member_device_id`, `epoch`, `security_profile`, `sender_did`, `sender_device_id`, `operation_id`.

Host verification for `group.e2ee.send` (§13.3) in this **order** with distinct errors: sender DID not active ⇒ `group.not_member`; sender device not eligible ⇒ `anp.device_not_eligible`/`anp.device_state_changed`; eligible but not a current leaf ⇒ **`group.e2ee.leaf_not_current` (5013)**; then policy, then payload. Host also verifies origin proof by device's current signing key.

### 7.7 Notifications and Device Delivery Queue (§12)
- `group.e2ee.notice`: `meta.profile="anp.group.e2ee.v2"`, `security_profile="transport-protected"`, `target.kind="agent"`, `target.did`, `recipient_device_id`, `sender_did` SHOULD = `group_did`; body = `e2ee_notice_object`; no `params.auth`.
- Add Commit ⇒ one envelope per retained leaf + `welcome-delivery` only to the exact new `(subject_did, subject_device_id)`. Remove Commit ⇒ one per retained leaf **plus one final envelope to the removed leaf** (`subject_status="removed"`), bounded retry/retention; removed device terminalizes without deriving new epoch secrets.
- P6 `group.incoming` (application ciphertext): `meta.profile="anp.group.e2ee.v2"`, `security_profile="group-e2ee"`, agent-addressed + `recipient_device_id`, preserves sender pair, message_id, operation_id, content_type; `params.auth` preserves original `origin_proof` **plus `origin_context`** (`created_at` of submission, optional `extra_meta`); body: `group_did`, `group_state_version`, `group_event_seq`, `accepted_at`, `group_receipt`, `group_cipher_object` (unchanged). One envelope per current leaf.
- Receivers reconstruct the submission SRO (`method="group.e2ee.send"`, meta from preserved fields + `target={kind:"group", did: body.group_did}` + `origin_context.created_at`, body = `group_cipher_object`) to verify origin proof; don't enforce `expires`/nonce on delivery; unresolvable rotated key ⇒ "unproven" not "forged"; MLS sender checks are authoritative.
- **Device Delivery Queue** per `(recipient_did, recipient_device_id)`: durable; stores only public meta, preserved proof, opaque ciphertext; reproduces envelopes byte-unchanged; revalidate eligibility per attempt; never deliver to siblings; transport-level confirmation (no app ack method); per-device order by `group_event_seq` (incoming) and epoch (commits); Welcome may overtake; final Remove notice must be last; bounded retention with defined recovery (Remove + fresh Add for lost Welcome/Commit).
- Receiver idempotency: `(group_did, group_event_seq)` + `message_id` for incoming; `(group_did, notice_id)` for notices.

### 7.8 DID update orchestration (§10.5, §11.12)
Verify P4 `member-did-updated` event + receipt, independently verify P2 transition and assurance, confirm roster; Host pauses all new `group.e2ee.send` from P4 acceptance until final Remove; serialize control actions; Add each selected new-DID device (all with same `group_state_ref`), then Remove each old-DID leaf; intermediate epochs carry no application messages; failures keep plane paused and retry; P6 failure never rolls back P4. Owner DID update: transitional Adds may come from old-owner leaf; Removes from new-owner leaf; else fail closed.
Pausing rules: whole-member removal/leave, DID update, orphan/conflict ⇒ pause sends; single-device revocation ⇒ do NOT pause (stop delivering to revoked device).

### 7.9 Epoch / forks
`epoch` decimal string; reject too-old messages; MAY keep bounded old-epoch window. `epoch_authenticator` SHOULD be exposed in `group_cipher_object`, notices, receipts. Fork (multiple `crypto_group_id`s, inconsistent authenticators, conflicting Commits) ⇒ SHOULD mark `fork-suspected` and suspend sends.

### 7.10 P6 errors (recommended §17)
| code | anp_code |
|---|---|
| 5000 | `group.e2ee.key_package_not_found` |
| 5001 | `group.e2ee.invalid_key_package` |
| 5002 | `group.e2ee.did_binding_invalid` |
| 5003 | `group.e2ee.controller_required` |
| 5004 | `group.e2ee.state_not_ready` |
| 5005 | `group.e2ee.epoch_conflict` |
| 5006 | `group.e2ee.crypto_group_mismatch` |
| 5007 | `group.e2ee.private_message_invalid` |
| 5008 | `group.e2ee.commit_invalid` |
| 5009 | `group.e2ee.welcome_invalid` |
| 5010 | `group.e2ee.fork_suspected` |
| 5011 | `group.e2ee.notice_type_unsupported` |
| 5012 | `group.e2ee.key_package_consumed` |
| 5013 | `group.e2ee.leaf_not_current` (stable; MUST be returned for "device not current leaf but DID active") |
Device-binding issues reuse Core 1015–1018.

### 7.11 P6 MTI (§18) — 35 items; highlights
MTI suite; restricted MLS subset; all 6 methods; Manifest-backed device verification + `0xF0A1` extension; target models; owner controller + closed same-DID exception; P4-driven create/add/remove; DID-update ordering + pause; `group.e2ee.send` not wrapped; notices for welcome/commit with explicit ratchet tree; P6 `group.incoming`; one PrivateMessage per send, one envelope per leaf; final removed-leaf commit-delivery; terminal-state convergence via multiple signals; rejoin with fresh KeyPackage; leaf removal ≠ Manifest removal; durable Device Delivery Queue; proof reconstruction for redelivery; `leaf_not_current`. Not required: External Commit, join info, `accept_welcome`, `get_state`, Update, multi-controller, history pull/read receipts/device sync, rejoin method.

### 7.12 Example inconsistencies
- §19.2/19.3 examples abbreviate `did_wba_binding` (no `leaf_signature_key_b64u`, `issued_at`, `expires_at`, `proof`) — not conformant as written; real payloads need the full object.
- §19.5/19.8 notice examples include `meta.operation_id` on a Notification (fine — not prohibited), but no `message_id`.
- §4.3 says `group.e2ee.create` uses `group-e2ee` security profile, while its sibling key-package methods use `transport-protected` — intentional.

---

## 8. P7 Attachments & Object Transfer — `anp.attachment.v1` (Released; deps P1, P2; composes with P3, P4, P5 v1/v2, P6 v1/v2)

### 8.1 Three planes (§3.1–3.2)
1. **Message plane** — `direct.send` / `group.send` / `group.e2ee.send` carry only the `attachment_manifest` list (content type `application/anp-attachment-manifest+json`).
2. **Control plane** — `attachment.create_slot`, `attachment.commit_object`, `attachment.abort_object`, `attachment.get_download_ticket` (JSON-RPC, service-scoped).
3. **Data plane** — independent HTTPS `PUT upload_uri` / `GET object_uri` with `Authorization: Bearer {download_ticket}`. Object bytes MUST NOT be embedded in JSON-RPC or relayed across the federation path.

Mainline (MUST):
1. `attachment.create_slot` → 2. (if `object-e2ee`) encrypt locally → 3. HTTPS PUT bytes → 4. `attachment.commit_object` → 5. send manifest via enclosing Profile → (sender side creates **Access Grant** per attachment upon message acceptance) → 6. receiver resolves the **original message sender's DID** → its `ANPMessageService` → `attachment.get_download_ticket` → 7. `GET object_uri` with Bearer ticket → 8. verify size + SHA-256 digest; decrypt if `object-e2ee`.

### 8.2 Modes and allowed combinations (§3.3–3.7)
- `encryption_info.mode` ∈ `none` | `object-e2ee` only. `service-managed`, `wrapped_object_key_b64u`, `key_wrap_alg`, inline tickets, custom ticket headers, permanent public links, mirror URIs, chunk lists, thumbnail sub-objects, byte relaying — all **prohibited**.

| Carrier | `meta.security_profile` | allowed `mode` | `object_key_b64u` in manifest? |
|---|---|---|---|
| Direct Base | `transport-protected` | `none` | No |
| Group Base | `transport-protected` | `none` | No |
| Direct E2EE | `direct-e2ee` | `none` / `object-e2ee` | Yes |
| Group E2EE | `group-e2ee` | `none` / `object-e2ee` | Yes |
- Object keys only travel inside E2EE-protected manifests; never in `create_slot`/`commit_object`.
- Multi-device: one object uploaded once; no per-device objects/tickets/grants; no device selectors in any P7 wire object (deployment may use device context internally only).

### 8.3 Carriage (§6)
- Direct Base: `meta.profile="anp.direct.base.v1"`, `security_profile="transport-protected"`, `content_type="application/anp-attachment-manifest+json"`, `body.payload` = Attachment Message, `auth.origin_proof` MUST, every manifest `mode="none"`.
- Group Base: same with `anp.group.base.v2` / `group.send`; response SHOULD include `group_receipt`.
- Direct E2EE: outer `content_type="application/anp-direct-cipher+json"` (or `...-init+json` for first message); inner `application_content_type="application/anp-attachment-manifest+json"`.
- Group E2EE: outer `application/anp-group-cipher+json`; manifest only inside Group Application Plaintext.

### 8.4 Objects (§7)
Attachment Message:
```json
{
  "attachments": [ {
    "attachment_id": "att-001", "filename": "report.pdf", "mime_type": "application/pdf", "size": "1048576",
    "digest": { "alg": "sha-256", "value_b64u": "BASE64URL_DIGEST" },
    "access_info": { "object_uri": "https://objects.example.com/objects/obj-001" },
    "encryption_info": { "mode": "none" } } ],
  "caption": "Attachment description",
  "primary_attachment_id": "att-001"
}
```
- `attachments` MUST, non-empty; `caption` MAY; `primary_attachment_id` MAY (must reference an existing `attachment_id`).
- `attachment_id` unique within one message only; grants/tickets/audit keyed by `(message_id, attachment_id)` or `(object_uri, message_id, attachment_id)`.
- Manifest MUST: `attachment_id`, `mime_type` (original file MIME), `size` (decimal string, uploaded-object bytes), `digest` (`alg="sha-256"`, `value_b64u` of uploaded bytes — plaintext for `none`, ciphertext for `object-e2ee`), `access_info` (`object_uri` https), `encryption_info`. MAY: `filename`, `media_info` (`width`, `height`, `duration_ms`, `codec`; numeric as decimal strings).
- `object_uri` is a locator, not a public link; receiver MUST obtain a ticket first; MUST NOT derive control-plane service from its hostname.
- No thumbnail/chunking fields (thumbnail = separate attachment; chunked upload internal to HTTP).

### 8.5 Object-level encryption (§8)
```json
{ "mode": "object-e2ee", "object_cipher": "chacha20-poly1305",
  "object_key_b64u": "BASE64URL_32_BYTES", "nonce_b64u": "BASE64URL_12_BYTES", "plaintext_size": "1048576" }
```
Sender: random 32-byte key K, random 12-byte nonce N, AAD = empty, `C = ChaCha20-Poly1305-Encrypt(K, N, "", P)`; upload C; `size = len(C)` (= len(P)+16), `digest = sha-256(C)`, `plaintext_size = len(P)`; `mime_type` = original. New K per committed object; never reuse (K, N); key MUST NOT derive from P5 ratchet / P6 epoch secrets. `expected_size` in create_slot SHOULD be ciphertext size.
Receiver: check length == `size` → check sha-256 → (`object-e2ee`) decrypt with empty AAD → check `len(P) == plaintext_size`; any failure ⇒ reject, SHOULD log.
No retroactive revocation: anyone who has key+bytes keeps them.

### 8.6 Access Grant & Download Ticket (§9)
- `create_slot`/`commit_object` create objects only — no download rights.
- On acceptance of the carrying `direct.send`/`group.send`/`group.e2ee.send`, the **sender-side system MUST create an Access Grant per attachment** binding `message_id`, `attachment_id`, `object_uri`, `message_security_profile`, and `message_target_did` (direct) or `group_did` (group). Grants authorize the DID/group, not a device.
- `intended_target` is only a policy hint; never sufficient for authorization.
- Ticket MUST bind `attachment_id`, `object_uri`, `requester_did`, `message_id`, `message_security_profile`, `message_target_did`|`group_did`, `expires_at`; MUST NOT include device selectors. Format is implementation-defined (opaque `download_ticket_b64u`).
- Ticket SHOULD be short-lived (≤ 5 min default); MAY be one-time; MUST be sent in `Authorization` header, never URL query.
- Issuance validation: `target.kind="service"`; `target.did` == serviceDid resolved from original sender DID; `requester_did == meta.sender_did`; grant for `(message_id, attachment_id, object_uri)` exists; `message_security_profile` matches; direct ⇒ `message_target_did` present + policy; group ⇒ `group_did` present + requester currently satisfies group access policy (SHOULD refuse removed members).
- Grant sync across internal services not standardized; external `ANPMessageService` must be able to see grants.
- DID transitions: historical manifests/grants not rewritten; MAY internally map a successor requester DID to an old grant only after P2 verification + business policy.

### 8.7 Control-plane methods (§10) — all `meta.profile="anp.attachment.v1"`, `security_profile="transport-protected"`, **service-scoped** (`target.kind="service"`, `target.did` = target `serviceDid`); cross-domain auth via P8 `serviceDid` + HTTP Message Signatures; Object Service need not re-verify end-user origin proof; no device selectors.
**Ambiguity:** P7 does not state whether `auth.origin_proof` is required on control-plane requests from a local client to its own service; examples omit `auth`. Treat client→home-service auth as local session auth (ANP-02), and cross-domain ticket requests as P8 s2s-signed.

| Method | Body MUST | Body SHOULD/MAY | Result MUST (MAY) |
|---|---|---|---|
| `attachment.create_slot` | `attachment_id`, `intended_message_security_profile` (`transport-protected`/`direct-e2ee`/`group-e2ee`), `object_encryption_mode` (`none`/`object-e2ee`) | SHOULD `expected_size`, `mime_type`; MAY `filename`, `expected_digest`, `intended_target` `{kind: agent|group, did}` | `attachment_id`, `slot_id`, `upload_uri`, `object_uri`, `commit_token`, `expires_at` (`upload_headers`) |
| `attachment.commit_object` | `attachment_id`, `slot_id`, `commit_token`, `size`, `digest` (`sha-256`), `object_encryption_mode` | MAY `plaintext_size` (MUST if object-e2ee), `media_info`; MUST NOT `object_key_b64u`/`nonce_b64u` | `committed=true`, `attachment_id`, `object_uri`, `committed_at` |
| `attachment.abort_object` | `attachment_id`, `slot_id` | — | `aborted=true`, `attachment_id`, `aborted_at` |
| `attachment.get_download_ticket` | `attachment_id`, `object_uri`, `requester_did` (== `meta.sender_did`), `message_security_profile` (of the carrying message), `message_id`, + `message_target_did` (direct) or `group_did` (group) | MAY `one_time` | `download_ticket_b64u`, `expires_at`, `ticket_binding` {`attachment_id`, `object_uri`, `requester_did`, `message_id`, `message_security_profile`, `message_target_did`|`group_did`} |
Rule: `transport-protected` ⇒ `object_encryption_mode` MUST be `none`.
Slot lifecycle: SlotCreated → Uploading → Uploaded → Committed; Aborted (from any pre-commit); Expired (timeout). Only Committed objects may be referenced.

Examples (copied):
```json
{ "jsonrpc": "2.0", "id": "req-70001", "method": "attachment.create_slot",
  "params": { "meta": { "profile": "anp.attachment.v1", "security_profile": "transport-protected",
      "sender_did": "did:example:agent-a", "target": { "kind": "service", "did": "did:example:domain-a" },
      "operation_id": "op-70001", "created_at": "2026-03-29T14:00:00Z" },
    "body": { "attachment_id": "att-001", "expected_size": "1048592", "mime_type": "application/pdf", "filename": "report.pdf",
      "intended_message_security_profile": "direct-e2ee", "intended_target": { "kind": "agent", "did": "did:example:agent-b" },
      "object_encryption_mode": "object-e2ee" } } }
```
```json
{ "jsonrpc": "2.0", "id": "req-70001", "result": { "attachment_id": "att-001", "slot_id": "slot-70001",
  "upload_uri": "https://objects.example.com/upload/slot-70001", "upload_headers": { "Content-Type": "application/octet-stream" },
  "object_uri": "https://objects.example.com/objects/obj-abc", "commit_token": "ct-abc-123", "expires_at": "2026-03-29T14:15:00Z" } }
```
```json
{ "jsonrpc": "2.0", "id": "req-70004", "method": "attachment.get_download_ticket",
  "params": { "meta": { "profile": "anp.attachment.v1", "security_profile": "transport-protected",
      "sender_did": "did:example:agent-b", "target": { "kind": "service", "did": "did:example:domain-a" },
      "operation_id": "op-70004", "created_at": "2026-03-29T14:10:00Z" },
    "body": { "attachment_id": "att-001", "object_uri": "https://objects.example.com/objects/obj-abc",
      "requester_did": "did:example:agent-b", "message_security_profile": "direct-e2ee", "message_id": "msg-70008",
      "message_target_did": "did:example:agent-b", "one_time": true } } }
```
```json
{ "jsonrpc": "2.0", "id": "req-70004", "result": { "download_ticket_b64u": "BASE64URL_TICKET", "expires_at": "2026-03-29T14:15:00Z",
  "ticket_binding": { "attachment_id": "att-001", "object_uri": "https://objects.example.com/objects/obj-abc",
    "requester_did": "did:example:agent-b", "message_id": "msg-70008", "message_security_profile": "direct-e2ee",
    "message_target_did": "did:example:agent-b" } } }
```
Data plane:
```http
PUT /upload/slot-70001 HTTP/1.1
Host: objects.example.com
Content-Type: application/octet-stream
Content-Length: 1048592

<encrypted object bytes>

GET /objects/obj-abc HTTP/1.1
Host: objects.example.com
Authorization: Bearer BASE64URL_TICKET
```
Note: `download_ticket_b64u` from the result is placed after `Bearer ` as-is.

### 8.8 P7 errors (fixed 6000–6013; `anp_code` MUST)
| code | anp_code |
|---|---|
| 6000 | `anp.attachment.slot_not_found` |
| 6001 | `anp.attachment.slot_expired` |
| 6002 | `anp.attachment.commit_token_invalid` |
| 6003 | `anp.attachment.object_too_large` |
| 6004 | `anp.attachment.unsupported_mime_type` |
| 6005 | `anp.attachment.grant_not_found` |
| 6006 | `anp.attachment.unauthorized_requester` |
| 6007 | `anp.attachment.download_ticket_invalid` |
| 6008 | `anp.attachment.ticket_binding_mismatch` |
| 6009 | `anp.attachment.ticket_expired` |
| 6010 | `anp.attachment.digest_mismatch` |
| 6011 | `anp.attachment.decrypt_failed` |
| 6012 | `anp.attachment.object_unavailable` |
| 6013 | `anp.attachment.encryption_policy_violation` |
`error.data` SHOULD include `attachment_id`, `slot_id`, `object_uri`, `message_id`, `expected_digest`.
**Ambiguity:** these codes are returned via JSON-RPC errors for control plane; the data-plane HTTP GET/PUT error mapping (401/403/404/410) is not specified. Recommend HTTP 401 for invalid/expired ticket, 403 for binding mismatch, 404 for unknown object.

### 8.9 P7 MTI (§13)
Base (1–18): all four methods; manifest content type; `attachments`; required manifest fields; `object_uri`; ticket service discovery from original sender DID; sha-256; HTTPS PUT/GET; Bearer ticket; service-scoped target; no byte relaying; `mode=none` under transport-protected; no device selectors; DID-transition grant mapping only after verification. E2EE attachments (19–23): `object-e2ee`, chacha20-poly1305 flow, key in E2EE manifest, ciphertext digest + decrypt, no retroactive revocation.

**Inconsistency:** P7 §6.1 refers to "Signed Direct Payload" / §6.2 "Signed Group Payload" — legacy names for the P1 Signed Request Object.

---

## 9. P8 Federation & Cross-Domain — `anp.federation.relay.v1` (Released; deps P1, P2, P3, P4; MAY combine with P5 v1/v2, P6 v1/v2, P7)

### 9.1 Principles
- **No relay wrapper protocol.** Cross-domain calls send the **original** business/control method (`direct.send`, `group.*`, `group.e2ee.*`, `attachment.*`) directly to the final target `ANPMessageService`. (Despite the name `federation.relay`, there is no `federation.*` method defined.)
- Discover target service first (P2), then call.
- All group-state / `group_event_seq` changes go to the Group Host only.
- Object bytes never travel over s2s JSON-RPC.
- E2EE payloads opaque to intermediaries.
- **Two identities**: outer HTTP Message Signature by the sender domain's **federated service DID** (`ANPMessageService.serviceDid`, SHOULD be bare-domain `did:web:alice.com` / `did:wba:alice.com`) vs inner business `meta.sender_did` + `auth.origin_proof`. MUST NOT be confused or substituted.
- Preserve P5/P6 device selectors unchanged; never synthesize selectors for P3/P4/P7.
- s2s calls MUST run in `transport-protected` (TLS); the inner `meta.security_profile` is whatever the original request said and MUST NOT be changed.

### 9.2 Routing (§5)
| `meta.target.kind` | Route to |
|---|---|
| `agent` | resolve Agent DID → its `ANPMessageService` → send `direct.send` |
| `group` | resolve Group DID → Group Host's `ANPMessageService` → send `group.*` / `group.e2ee.add/remove/send` |
| `service` | `target.did` is the `serviceDid` → resolve → send |
- `direct.e2ee.get_prekey_bundle` / `group.e2ee.get_key_package`: route by `body.target_did`; preserve `body.target_device_id`; never substitute a device. Non-anonymous.
- `attachment.get_download_ticket`: anchor = original attachment message sender DID (group: original sender, not `group_did`; never `object_uri` host).
- Group event distribution: Host SHOULD reuse `group.incoming`, `group.state_changed`, `group.e2ee.notice` (or equivalent carrying at least `group_did`, `group_event_seq`, `group_state_version`, payload). P4 notifications stay DID-addressed; P6 keeps exact recipient-device selector, never broadcast to siblings.

### 9.3 Service-to-service authentication (§6)
- Secure channel with mutual or equivalent peer auth.
- Source service identified by outer **HTTP Message Signatures** (RFC 9421 per ANP-02 HTTP binding): `Signature-Input` `keyid` = full DID URL in `serviceDid` doc's `authentication`.
- **Caller-anchor verification** (§6.2.2) — receiver MUST:
  1. pick caller anchor: `meta.sender_did` for `direct.send`, all `group.*` requests, `direct.e2ee.*`, `group.e2ee.*` requests, `attachment.*`; **`body.group_did`** for `group.incoming`, `group.state_changed`, `group.e2ee.notice`;
  2. resolve + method-validate anchor DID Doc;
  3. select its `ANPMessageService`;
  4. read `serviceDid` (missing ⇒ fail);
  5. extract `keyid` from outer `Signature-Input`, get its DID;
  6. require `keyid` DID == `serviceDid` (else fail);
  7. resolve + validate `serviceDid` doc;
  8. verify HTTP signature with key in its `authentication`.
  Never always derive `serviceDid` from `meta.sender_did` (wrong for group notifications).
- Bare-domain service DID MAY hold multiple `authentication` keys for instances/rotation. Path DIDs (e.g. `did:wba:alice.com:agents:relay:e1_...`) SHOULD NOT be the federated service DID.
- Keep `method`, `params.meta`, `params.body` equivalent; re-encoding allowed only if semantics unchanged.
- Forward `auth.origin_proof` unchanged; target verifies independently; never re-sign. For `attachment.*`, there's usually no origin proof — s2s auth is not a substitute for one.
- Intermediary-visible fields limited to: `meta.profile`, `security_profile`, `sender_did`, `target`, `operation_id`, `message_id`, `content_type`, and P5/P6 device selectors where declared.
- DID transitions: pre-JSON-RPC deactivation may yield method-binding HTTP error (e.g. WBA HTTP `409`); in-application ⇒ `anp.did_superseded`; never both. Forward final service's error unchanged; `current_did` is not a trusted redirect; intermediaries MUST NOT rewrite `sender_did`, `target.did`, `body.member_did`, device bindings, mentions, AAD, or origin proof. (Group Host may emit new notifications to the current DID — it originates those.) Refresh DID/service caches after superseded/signature/endpoint/deactivation/capability conflicts.
- **Ambiguity:** P8 defers HTTP signature details (covered components, `Content-Digest` header, created/expires/nonce window) to ANP-02 §"http-binding"; P8 itself doesn't list which HTTP components must be covered. Consult ANP-02 notes when implementing.

### 9.4 Idempotence & retry (§7)
Reuse each business method's idempotency keys. Retries keep `operation_id`, `message_id`, `attachment_id`, device selectors, semantically equivalent payload. Trace/attempt fields are internal and never idempotency keys. Duplicate of processed request SHOULD return equivalent first response.

### 9.5 Cross-domain success semantics (§8)
| Operation | Success = |
|---|---|
| `direct.send` | final target-domain ingress accepted (internal routing out of scope) |
| P4 control (`join/add/remove/update_*`) | Group Host accepted and ordered (join/add ⇒ membership established) |
| P6 `create/add/remove` | Group Host accepted crypto control result (does not create P4 state) |
| `group.send` | Group Host accepted + assigned `group_event_seq` |
| `group.e2ee.send` | Host accepted/ordered ciphertext and returned `group_event_seq`, `group_state_version`, `group_receipt` (decryption by members not implied) |
| `attachment.get_download_ticket` | final Object Service returned ticket or explicit rejection (≠ download success) |

### 9.6 Download tickets cross-domain (§9)
- Protocol endpoint = original sender DID's public `ANPMessageService` (may route internally to Object Service).
- **Mode A (standard, MUST mainline): domain-service proxy** — requesting Agent asks its local `ANPMessageService`, which calls the remote service with s2s auth.
- Mode B (agent direct) — deployment extension, not MTI.
- Object service authorizes using (1) verified outer caller `serviceDid` and (2) body context (`requester_did`, security profile, target/group, `message_id`) vs grant. Need not verify end-user origin proof.
- Download over separate HTTPS; ticket SHOULD be in `Authorization` (P7 says MUST) — not URL query.

### 9.7 P8 MTI (§10)
DID-based discovery for agents and groups; original methods directly; keep `security_profile`/`operation_id`/origin proof; all group-state ops to Host; route join/add/remove/leave/update_*/send to Host; P6 landing points; P5/P6 getter routing; ticket to original sender's service; no byte forwarding; ≥1 group-event distribution mechanism (+`group.e2ee.notice` with P6); declare `serviceDid` + verify outer signatures by caller anchor; bare-domain did:wba support; device selectors only for P5/P6; HTTP 409 vs `anp.did_superseded` layering; no rewriting DID-bound fields; cache refresh.
No P8-specific error codes.

---

## 10. P9 Message Mentions — v1 binding extension (Released; no own `meta.profile`; deps P1 + P4 v2 or P6 v2)

- **Group messages only** (direct-message mentions are a future extension). No new method, no new `meta.profile`, no new content type, no `protocol` marker, no mention-local sender or proof.
- Marker: a structured JSON payload with a top-level **`mentions` array**. Payload must be `application/json` (`meta.content_type` for Group Base; inner `application_content_type` for Group E2EE).
- Placement: Group Base ⇒ `params.body.payload` of `group.send` (covered by origin proof SRO digest); Group E2EE ⇒ inner `Group Application Plaintext.payload` (MLS-protected). Pushed `group.incoming` MUST preserve it unchanged; SHOULD include lossless origin proof copy.

Payload shape:
```json
{
  "text": "@agents please summarize this discussion.",
  "mentions": [ {
    "id": "men_1",
    "range": { "start": 0, "end": 7, "unit": "unicode_code_point" },
    "target": { "kind": "group_selector", "selector": "agents" },
    "mention_role": "addressee" } ]
}
```
- Top-level: `text` (MUST string), `mentions` (MUST array), `annotations` (MAY). Unknown top-level fields MAY be ignored. Don't include `mentions` if no structured mention semantics.
- Mention object: `id` (MUST, unique per message), `range` (MUST), `target` (MUST), `mention_role` (MAY; `addressee` default | `cc`). MUST NOT contain `sender`, `sender_did`, `from`, `actor_did`, `auth`, `origin_proof`, `proof`, `signature`, `sender_device_id`, `recipient_device_id`, `device_id`, MLS leaf IDs.
- Range: `start` (inclusive), `end` (exclusive), non-negative **integers** (note: JSON numbers, not decimal strings — exception to P1 §7.3 style), `unit` MUST be `unicode_code_point`; `start < end ≤ code-point length of text` (computed on parsed JSON string before any normalization). Surface text not duplicated.
- Targets: `{kind:"human", did, display_name?}`, `{kind:"agent", did, display_name?}`, `{kind:"group_selector", selector: "all"|"agents"|"humans"}` (no `did`). `display_name` is never identity.
- Selectors are terminal-side interpretations: `all` = all active members; `agents` / `humans` = per local roster/profile classification (not P4 roles; P4 has no human/agent field). Resolve against the message's `group_state_version` snapshot if available, else best effort.
- **Servers/Host MUST NOT**: do mention-specific authorization, expand selectors, reject for unknown target DIDs or broad selectors, or modify mentions. MAY enforce operational limits (size, mention count, rate limit, spam).
- **Terminal validation** (12 steps): rely on authenticated sender context; parse; require `mentions`; `text` string; `mentions` array; unique ids; valid ranges; valid `target.kind`; DID present for human/agent; valid selector; valid `mention_role`; then local behavior. Invalid mention ⇒ ignore for triggering but MAY display text; never trigger privileged behavior from invalid objects; never use visible text alone to resolve targets.
- Historical mentions are never rewritten after DID transitions; local association after P2 verification only.
- No P9 error codes.
- Example (copied):
```json
{ "jsonrpc": "2.0", "id": "req-group-mention-001", "method": "group.send",
  "params": { "meta": { "profile": "anp.group.base.v2", "security_profile": "transport-protected",
      "sender_did": "did:wba:example.com:user:alice",
      "target": { "kind": "group", "did": "did:wba:groups.example.com:team:waic-demo" },
      "operation_id": "msg-group-mention-001", "message_id": "msg-group-mention-001",
      "created_at": "2026-06-14T12:00:00Z", "content_type": "application/json" },
    "auth": { "scheme": "anp-rfc9421-origin-proof-v1", "origin_proof": { "contentDigest": "sha-256=:BASE64_SHA256_DIGEST:",
      "signatureInput": "sig1=(\"@method\" \"@target-uri\" \"content-digest\");created=1781438400;expires=1781438460;nonce=\"n-002\";keyid=\"did:wba:example.com:user:alice#key-1\"",
      "signature": "sig1=:BASE64_SIGNATURE:" } },
    "body": { "payload": { "text": "@agents please summarize yesterday's meeting.",
      "mentions": [ { "id": "men_1", "range": { "start": 0, "end": 7, "unit": "unicode_code_point" },
        "target": { "kind": "group_selector", "selector": "agents" }, "mention_role": "addressee" } ] } } } }
```

---

## 11. examples/message-vnext (illustrative, NOT crypto vectors)

| File | Content | Notes / inconsistencies |
|---|---|---|
| `01-did-document-two-devices.json` | Agent DID with JSON-LD `@context` defining `deviceManifest` terms under `https://agentnetworkprotocol.com/ns/message/v2#…`; `#root` Ed25519 key + two device sign/e2ee key pairs; `ANPMessageService` with `serviceDid: did:example:alice-domain`; two Manifest entries; top-level DID Doc `proof` (DataIntegrityProof by `#root`, a did:wba-style document proof) | **Lists `anp.group.base.v1`** in service `profiles` and Manifest `profiles` — stale; Messaging 1.2 uses `anp.group.base.v2` (P6 entry must list P4 v2 per P2 §5.5 rule 5). Useful: shows the JSON-LD context IRIs for Manifest terms. |
| `02-direct-two-device-deliveries.json` | One logical message → two separate P5 `direct.send` requests (one per recipient device `dev-b-4M8P1X`, `dev-b2-6VQ9RS`), each with own session, ratchet header, ciphertext; inner `logical_message_id` shared; two independent results with `recipient_device_id` | **Uses `operation_id` ≠ `message_id`** (`op-bob-b1-001` vs `delivery-bob-b1-001`), contradicting P5 §3.7 (`operation_id` MUST equal `message_id`). Follow the spec, not the example. |
| `03-device-prekey-bundle.json` | Bundle for `(did:example:bob, dev-b2-6VQ9RS)`, `static_key_agreement_id: did:example:bob#dev-b2-e2ee`, proof by `#dev-b2-sign` | consistent: VM == Manifest `signing_key_id`, static key == `e2ee_key_id` |
| `04-mls-two-device-leaves.json` | One P4 member (`p4_member_count_contribution: 1`) with two MLS leaves (leaf_index "7", "11"), each with full `group_key_package` + full `did_wba_binding` | invariant: same `credential.identity`, distinct `device_id`; LeafNode carries `0xF0A1`, capabilities + GroupContext `required_capabilities.extension_types` include it |
| `05-device-revocation.json` | before/after DID Doc: removing `dev-a2-9R5TLM` and its key references from verificationMethod/authentication/assertionMethod/keyAgreement/Manifest | follow-up: stop PreKey + Mailbox use, invalidate unconsumed KeyPackages, remove MLS leaf in each group + new epoch, never reuse ID/keys. Also lists `anp.group.base.v1` (stale). |
| `06-device-state-changed-error.json` | Error 1018 `anp.device_state_changed`, `retryable: true`, `details: { affected_did, affected_device_id, affected_role: "recipient", resolution_required: true }` | P5/P6 only; shows a useful `details` shape |
| `07-did-transition-retry.json` | 1019 `anp.did_superseded` with `details.requested_did` / `current_did`; predecessor doc `deactivated: true`, `successorDid`, proof by old `#binding-key`; successor doc with `alsoKnownAs`; `assurance: "verified"`; retry keeps `message_id`/`operation_id`, new `target.did`, rebuilt digest + signature | `alsoKnownAs` and `current_did` alone don't establish continuity |

---

## 12. ANP-02 HTTP binding pointer (relevant to P8 s2s auth and client→service auth)

(Not in the requested reading list; skimmed only §3 to resolve P8's deferred reference.)
- HTTP requests: RFC 9421 `Signature-Input` + `Signature` headers; RFC 9530 `Content-Digest` when a body is present.
- Minimum covered components: `@method`, `@target-uri`, `content-digest` (if body). Recommended: `@authority`, `content-type`, `content-length`.
- `keyid` full DID URL in `authentication`; `created` MUST, `expires` SHOULD, `nonce` MAY (MUST use server nonce if challenged).
- Server: verify format → body digest → resolve DID (method binding) → `authentication` → signature coverage → time window (1–5 min recommended) → replay cache `(keyid, nonce)` → authorization (403) → else 401 with `WWW-Authenticate: DIDWba ... error="invalid_signature" ... nonce="..."` and `Accept-Signature`.
- Optional access token returned via `Authentication-Info: access_token="...", token_type="Bearer", expires_in=...`; client sends `Authorization: Bearer <token>`. (P3/P4: tokens never replace `auth.origin_proof`.)
- Note the difference: **outer HTTP** signatures sign real HTTP components; **inner `auth.origin_proof`** (P1 App. A) signs logical components `@method`=JSON-RPC method, `@target-uri`=`anp://kind/did`, `content-digest`=JCS(SRO) digest — fixed set without `@authority`.
- Practical transport (derived): JSON-RPC request is the HTTP POST body to `ANPMessageService.serviceEndpoint` (e.g. `https://agent-a.example.com/anp`), `Content-Type: application/json`; the JSON-RPC response is the HTTP response body. P1 does not mandate HTTP status codes; return 200 with JSON-RPC error objects for application errors, reserve 401/403 for transport-level ANP-02 auth failures.

---

## 13. Minimal viable conformant subset — first production release (DID-addressed direct messaging + attachments, no E2EE)

### 13.1 Profiles to implement and advertise
```json
{
  "supported_profiles": [
    "anp.core.binding.v1",
    "anp.identity.discovery.v1",
    "anp.direct.base.v1",
    "anp.attachment.v1",
    "anp.federation.relay.v1"
  ],
  "supported_security_profiles": ["transport-protected"]
}
```
- **Caveat on P8:** `anp.federation.relay.v1` formally **depends on `anp.group.base.v2`** (P8 §4.2) and its MTI includes routing group ops to the Host and ≥1 group event distribution mechanism. A direct-only release that federates cross-domain therefore has two options:
  - (a) implement P8 behaviour for direct + attachments (s2s `serviceDid` signatures, caller-anchor verification, original-method forwarding, ticket routing) **without advertising** `anp.federation.relay.v1` — still interoperable because cross-domain calls are just P3/P7 methods with outer HTTP signatures; or
  - (b) also implement P4 to be able to claim P8.
  Recommend (a) for v1 of the product, documenting it; P3 itself requires nothing from P8, and P7 cross-domain ticket issuance only needs s2s auth.
- Do **not** advertise `direct-e2ee`/`group-e2ee` or any `*.e2ee.*` profile. No `deviceManifest` required. Don't put `anp_version` in requests.

### 13.2 DID Document requirements (per Agent DID you host)
- `id`, `verificationMethod` (Ed25519 for signing), `authentication` (key used for `auth.origin_proof` `keyid`), optionally `assertionMethod`.
- Exactly one cross-domain `ANPMessageService`: `id`, `type: "ANPMessageService"`, `serviceEndpoint` (HTTPS), `serviceDid` (bare-domain DID of your domain, e.g. `did:wba:yourdomain.com`), `profiles` (as above), `securityProfiles: ["transport-protected"]`.
- The `serviceDid` DID Doc must have an `authentication` key for outer HTTP Message Signatures.

### 13.3 Methods to implement
| Method | Role | Notes |
|---|---|---|
| `anp.get_capabilities` | server (anonymous + authenticated) | returns `service_did`, `supported_profiles`, `supported_security_profiles`, `limits` (decimal strings), SHOULD `supported_content_types` |
| `direct.send` | server (ingress) + client/outbound | agent-addressed; `auth.origin_proof` mandatory; `text/plain`, `application/json`, `application/anp-attachment-manifest+json` |
| `direct.incoming` | Notification push to local Agent runtime | must implement; lossless origin-proof copy |
| `attachment.create_slot` | server (own service) | service-scoped; `object_encryption_mode` must be `none` under transport-protected |
| `attachment.commit_object` | server | |
| `attachment.abort_object` | server | |
| `attachment.get_download_ticket` | server (for objects your users sent) + outbound proxy (for objects others sent) — Mode A domain proxy | validate Access Grant; Bearer tickets ≤5 min |
| HTTPS `PUT upload_uri`, `GET object_uri` (Bearer) | object data plane | sha-256 + size verification by receiver |

### 13.4 Core server pipeline (derived checklist, in order)
1. HTTPS only; parse JSON (`-32700`); reject batch (`1004`), non-object params (`1003`), non-string/empty/null id (`1000`), `jsonrpc != "2.0"` (`-32600`), unknown method (`-32601`).
2. Outer auth: if a s2s hop, verify HTTP Message Signatures with caller-anchor rules (P8 §6.2.2); if local client, ANP-02 auth / session.
3. `meta.profile` supported (`1001`); `security_profile` supported and allowed for the profile (`1002`/`1013`); reject unknown core `meta` fields (allow `x_*`); reject device selectors in Base ops (invalid params, **not** 1015–1018).
4. Target mode check (`1014`): `direct.send` ⇒ agent; `attachment.*` ⇒ service with `target.did == own serviceDid`.
5. For `direct.send`: verify `auth.origin_proof` (rebuild SRO `{method, meta, body}` → JCS → SHA-256 → compare `contentDigest`; rebuild `@method` and `@target-uri = anp://agent/<pct(target.did)>`; RFC 9421 verify; `keyid` DID == `sender_did`; `keyid` ∈ `authentication`; created/expires window; nonce replay cache). Errors `2005`/`2006`/`2007` (or `1005`).
6. Idempotency lookup `(sender_did, target.did, method, operation_id)` **before** any other state check; equivalent ⇒ replay stored result; conflict ⇒ `1008`. Then message dedup `(sender_did, target.did, message_id)`.
7. Target exists/hosted (`1007`), not superseded (`1019` with `requested_did`/`current_did`), policy (`2001`/`1010`), content type (`1009`), payload exclusivity (`2002`), limits (`1011`).
8. Persist + return `{accepted: true, message_id, operation_id, target_did, accepted_at}`; then async `direct.incoming` to the local Agent.
9. If message carries an attachment manifest and the **sender** is local: create Access Grants for each `(message_id, attachment_id, object_uri)` with `message_security_profile` and `message_target_did` upon acceptance by the remote ingress.
10. Outbound: resolve target DID → `ANPMessageService` → forward the original request unchanged (same `auth.origin_proof`), signed at HTTP layer by your `serviceDid`; keep `operation_id`/`message_id` on retries; return success to the local caller only after remote ingress accepts.

### 13.5 Production-relevant gaps the spec leaves to you (MVP)
- No delivered/read receipts, history pull, presence, or ordering guarantees (best-effort per `conversation_id` only). If the product needs read receipts, define a private extension method with a private prefix (P1 §11.3) and do not assume peers support it.
- Physical channel for `direct.incoming` (WSS vs callback) is implementation-defined.
- Idempotency record retention window is not specified — choose ≥ the max sender retry horizon.
- Rate limits / max sizes advertised via `limits` in `anp.get_capabilities`.

### 13.6 What adding E2EE later requires
**Direct E2EE (P5 `anp.direct.e2ee.v2`):**
- Publish `deviceManifest` in each Agent DID Doc (per-device Ed25519 signing key in `authentication`+`assertionMethod`, X25519 key in `keyAgreement`; `profiles` = P1+P2+P3+P5). Device IDs opaque, never reused.
- Add methods: `direct.e2ee.publish_prekey_bundle`, `direct.e2ee.get_prekey_bundle` (service-scoped, device-authenticated sessions, OPK pool with atomic allocation + idempotent retry returning same OPK).
- `direct.send` P5 path: content types `application/anp-direct-init+json` / `application/anp-direct-cipher+json`, `security_profile="direct-e2ee"`, `sender_device_id`+`recipient_device_id`, `operation_id == message_id`, **no `params.auth`**. One ciphertext per recipient device; per-device Mailbox `(recipient_did, recipient_device_id)`; result includes `recipient_device_id`; P5 `direct.incoming` delivered only to the selected device.
- Client SDK: X3DH-like + Double-Ratchet-like exactly as specified (HKDF info strings, `kdf_rk`, `kdf_ck` 76-byte output, nonce derivation, init consumes message 0, pending-confirmation buffering, `MAX_SKIP`=1000, JCS AAD objects).
- Server: device-eligibility checks against freshly resolved Manifests (errors 1015–1018), P5 errors 4000–4012, idempotency keys extended with device IDs, init replay records, selector preservation across federation.
- Update capabilities: add `anp.direct.e2ee.v2` and `direct-e2ee`; E2EE attachments then allow `object-e2ee` (ChaCha20-Poly1305, empty AAD, key/nonce inside encrypted manifest).
- Never downgrade a failed v2 send to transport-protected; if recipient policy requires E2EE, reject transport-protected sends (`2004`).
**Group (P4 v2, then P6 candidate):** P4 is a prerequisite for P6; P6 is gated on the MLS ExtensionType (`0xF0A1` provisional) — treat as experimental.
**Architecture decisions to make now so E2EE fits later:** keep idempotency keys pluggable (add device dimensions), store messages as opaque bodies keyed by profile, design delivery queues so they can be keyed per `(did, device_id)`, keep DID-resolution cache with forced refresh hooks, and keep JCS + Data Integrity (`eddsa-jcs-2022`) libraries available (also needed by P4 receipts).

---

## 14. Consolidated MUST / MUST NOT checklist (implementation-oriented)

### Envelope / binding (P1)
- [ ] MUST `jsonrpc:"2.0"`; `params` object; `id` non-empty string; no batch; Notifications only for async push.
- [ ] MUST return exactly one Response per Request with matching `id`; `result` xor `error`.
- [ ] MUST include `meta.profile` (single profile) and `meta.security_profile` on every request.
- [ ] MUST NOT use `meta.anp_version` to select profile; new senders SHOULD omit it.
- [ ] MUST include `operation_id` for state-changing ops; `message_id` + `content_type` for message-bearing ops/notifications.
- [ ] MUST reject unknown core `meta` fields; MAY ignore `x_*`; MUST reject unknown security/routing/idempotency-affecting fields.
- [ ] MUST declare target mode per method; mismatch ⇒ `anp.invalid_target_binding`; service-scoped ⇒ `target.did == serviceDid`.
- [ ] MUST NOT put URLs in `target.did`; no `target.kind="device"`.
- [ ] MUST use unpadded base64url for binary, decimal strings for counters/epochs/sizes/versions.
- [ ] MUST NOT double-serialize JSON; `application/json` payload must be an object in `body.payload`.
- [ ] MUST NOT invent content types to distinguish business meanings.
- [ ] MUST implement `anp.get_capabilities` (anonymous + authenticated); runtime result overrides DID hints.
- [ ] MUST idempotency-check before version/concurrency checks; conflict ⇒ 1008.
- [ ] MUST return `error.data.anp_code` for ANP codes; MUST NOT leak sensitive state.
- [ ] MUST NOT silently downgrade security profile.
- [ ] MUST NOT use `created_at` as sole anti-replay; MUST NOT use `trace_id` in security/idempotency.
- [ ] MUST reject device selectors in Base ops; MUST validate them only in P5/P6.
- [ ] Origin proof: SRO = `{method, meta, body}` JCS; sha-256; `sig1`; components exactly `("@method" "@target-uri" "content-digest")`; `@target-uri = anp://{kind}/{pct-encoded did}`; `keyid` DID == business DID; key ∈ `authentication`; intermediaries MUST forward unchanged and MUST NOT re-sign.
- [ ] Object proof: `DataIntegrityProof` + `eddsa-jcs-2022` + `assertionMethod`; protected doc = object minus `proof`; `proofValue` base58btc `z…`.

### Identity / discovery (P2)
- [ ] Exactly one cross-domain `ANPMessageService` per DID Doc; `serviceDid` MUST if s2s.
- [ ] MUST NOT put dynamic state (members, epochs, prekeys, KeyPackages, presence) in DID Docs.
- [ ] `deviceManifest` only when advertising E2EE; entries exactly 4 fields; `device_id` never reused.
- [ ] Discovery anchor for download tickets = original message sender DID; MUST NOT derive from `object_uri` host.
- [ ] Re-resolve DID on signature/key/endpoint/capability failures.
- [ ] MUST NOT infer DID continuity from `alsoKnownAs`/paths; Group DIDs never auto-transition.

### Direct Base (P3)
- [ ] `direct.send`: agent target; one recipient; `auth.origin_proof` MUST; exactly one of `text`/`payload`/`payload_b64u`; result `accepted,message_id,operation_id,target_did,accepted_at`.
- [ ] MUST implement `direct.incoming` Notification; no response; lossless proof copy.
- [ ] MUST NOT expose device/replica/fan-out data.
- [ ] Superseded target ⇒ `anp.did_superseded`; never silently rewrite.
- [ ] If policy requires E2EE ⇒ reject transport-protected.

### Group Base (P4 v2)
- [ ] Host linearly orders all state changes + sends; new `group_state_version` per state change only; `group_event_seq` for all.
- [ ] `group.create` service-scoped; others group-addressed; origin proof on all state-changing + `group.send`.
- [ ] Roles owner>admin>member; statuses active/left/removed; `permissions` exactly 5 keys.
- [ ] `admin-add` ⇒ reject `group.join`; `open-join` ⇒ allow.
- [ ] `group_receipt.proof` MUST when crossing domains; issuer `group_did`.
- [ ] `group.member_did_update` is NOT callable (`-32601`); CAS-based Host update; emit `member-did-updated`.
- [ ] Final self-scoped `group.state_changed` to removed/left subject, bounded retention.
- [ ] No invitations/approvals in core; no device selectors.

### Direct E2EE (P5 v2)
- [ ] `operation_id == message_id`; no `params.auth`; only init/cipher content types; both device selectors.
- [ ] One ciphertext per recipient device; Mailbox per (DID, device); no hidden fan-out; no sibling delivery.
- [ ] Bundle proof issuer = owner DID, VM = Manifest `signing_key_id`; static key = Manifest `e2ee_key_id`; no OPK in bundle.
- [ ] OPK single-allocation, atomic with idempotency record; consumed after init.
- [ ] Initiator MUST NOT send `direct-cipher` while `pending-confirmation`.
- [ ] Never share state across device pairs; never downgrade v2.

### Group E2EE (P6 v2, candidate)
- [ ] MLS MTI suite; restricted subset; `0xF0A1` extension exactly once, capability-declared.
- [ ] `credential.identity = UTF8(agent_did)`; one leaf per device.
- [ ] Owner-only controller (plus narrow same-DID revoked-sibling removal).
- [ ] Host never decrypts/re-encrypts; one envelope per leaf; durable Device Delivery Queue; final Remove notice.
- [ ] Pause sends during DID update / whole-member removal; don't pause for single-device revocation.
- [ ] `group.e2ee.leaf_not_current` ordering of errors.

### Attachments (P7)
- [ ] Object bytes only over HTTPS PUT/GET; never in JSON-RPC or s2s.
- [ ] `mode` ∈ {none, object-e2ee}; transport-protected ⇒ none; object keys only in E2EE manifests.
- [ ] Access Grant created on message acceptance; tickets bound to `(attachment_id, object_uri, requester_did, message_id, message_security_profile, target/group, expires_at)`; ≤5 min; `Authorization: Bearer`, never query string.
- [ ] Receiver verifies size + sha-256 (+ decrypt + plaintext_size).
- [ ] No device fields in any P7 object.

### Federation (P8)
- [ ] Use original methods directly; no wrapper relay protocol.
- [ ] Outer HTTP signature by `serviceDid`; caller anchor `meta.sender_did` (requests) or `body.group_did` (group notifications); `keyid` DID == anchor's `serviceDid`.
- [ ] Preserve origin proof, security profile, operation/message IDs, P5/P6 selectors; never rewrite DID-bound fields.
- [ ] Don't return both HTTP 409 and `anp.did_superseded` for one request.

### Mentions (P9)
- [ ] `mentions` inside `body.payload` (Base) or inner plaintext payload (E2EE); `application/json`.
- [ ] No sender/proof/device fields in mention objects; code-point ranges.
- [ ] Servers MUST NOT authorize, expand, reject-by-target, or modify mentions.

---

## 15. Consolidated error-code table

| Range | Owner | Codes |
|---|---|---|
| −32700…−32603 | JSON-RPC | −32700 parse, −32600 invalid request, −32601 method not found (incl. calling `group.member_did_update`), −32602 invalid params, −32603 internal |
| 1000–1021 | P1 Core (`anp.*`) | 1000 invalid_request_id, 1001 unsupported_profile, 1002 unsupported_security_profile, 1003 invalid_params_shape, 1004 batch_not_supported, 1005 unauthorized, 1006 forbidden, 1007 target_not_found, 1008 idempotency_conflict, 1009 unsupported_content_type, 1010 delivery_rejected, 1011 rate_limited, 1012 temporarily_unavailable, 1013 invalid_security_binding, 1014 invalid_target_binding, 1015 device_binding_required, 1016 device_binding_invalid, 1017 device_not_eligible, 1018 device_state_changed, 1019 did_superseded, 1020 did_transition_invalid, 1021 did_transition_conflict |
| 2000–2007 | P3 (`direct.*`, recommended) | 2000 recipient_unreachable, 2001 policy_violation, 2002 invalid_payload_shape, 2003 conversation_conflict, 2004 security_mode_required, 2005 invalid_origin_proof, 2006 origin_did_mismatch, 2007 origin_proof_replayed |
| 3000–3010 | P4 (`group.*`, recommended) | 3000 not_member, 3001 already_member, 3002 admission_not_allowed, 3003 policy_violation, (3004 unassigned), 3005 member_conflict, 3006 security_mode_required, 3007 host_unavailable, 3008 invalid_origin_proof, 3009 origin_did_mismatch, 3010 invalid_group_receipt |
| 4000–4012 | P5 (`anp.direct.e2ee.*`, fixed) | 4000 bundle_not_found, 4001 bundle_invalid, 4002 bundle_expired, 4003 opk_unavailable, 4004 missing_key_agreement, 4005 session_not_found, 4006 session_conflict, 4007 bad_init_message, 4008 replay_detected, 4009 decrypt_failed, 4010 max_skip_exceeded, 4011 reset_required, 4012 invalid_security_binding |
| 5000–5013 | P6 (`group.e2ee.*`, recommended) | 5000 key_package_not_found, 5001 invalid_key_package, 5002 did_binding_invalid, 5003 controller_required, 5004 state_not_ready, 5005 epoch_conflict, 5006 crypto_group_mismatch, 5007 private_message_invalid, 5008 commit_invalid, 5009 welcome_invalid, 5010 fork_suspected, 5011 notice_type_unsupported, 5012 key_package_consumed, 5013 leaf_not_current |
| 6000–6013 | P7 (`anp.attachment.*`, fixed) | 6000 slot_not_found, 6001 slot_expired, 6002 commit_token_invalid, 6003 object_too_large, 6004 unsupported_mime_type, 6005 grant_not_found, 6006 unauthorized_requester, 6007 download_ticket_invalid, 6008 ticket_binding_mismatch, 6009 ticket_expired, 6010 digest_mismatch, 6011 decrypt_failed, 6012 object_unavailable, 6013 encryption_policy_violation |
| — | P8, P9 | none defined |
| HTTP | ANP-02 transport | 401 (+`WWW-Authenticate: DIDWba …`, `Accept-Signature`), 403, method-binding 409 (WBA deactivated DID, pre-JSON-RPC) |

Error object shape: `{ "code": <int>, "message": "<short>", "data": { "anp_code": "<string>", "retryable": <bool>, "details": { ... } } }`. Note `group.policy_violation` is referenced by name in P4 text (code 3003).

---

## 16. Ambiguities, gaps, and spec/example inconsistencies (consolidated)

1. **HTTP transport mapping undefined in P1**: no path, no HTTP status mapping for JSON-RPC errors, no WSS framing/subprotocol, no definition of how Notifications (`direct.incoming`, `group.incoming`, `group.state_changed`, `group.e2ee.notice`) are physically delivered (server push over WSS? callback POST to member domain's `serviceEndpoint`?). For cross-domain group notifications, P8 implies the Host calls the member domain's `ANPMessageService` (HTTP POST of a JSON-RPC Notification signed by the Host's `serviceDid`); for intra-domain push to agents it's local.
2. **`anp.get_capabilities` target mode** not declared (example omits `meta.target`, but P1 says non-endpoint-local methods need explicit target). Accept omitted target or `{kind:"service", did: serviceDid}`.
3. **Examples omitting mandatory `auth`**: P3 §13.3 JSON `direct.send`, P4 `group.send` req-30005. Spec text says `auth.origin_proof` MUST.
4. **P4 `initial_members` field name**: §8.1.2 requires `member_did`; §15.1 example uses `agent_did` and includes the creator.
5. **examples/message-vnext**: `anp.group.base.v1` in profile lists (should be v2); `02` uses `operation_id ≠ message_id` contrary to P5 §3.7.
6. **P6 examples** abbreviate `did_wba_binding` (missing required fields/proof).
7. **P7 attachment control-plane auth**: no statement whether local client calls carry `auth.origin_proof`; examples omit it; P8 says origin proof usually absent for `attachment.*`. Use local session auth.
8. **P7 data-plane HTTP error mapping** (401/403/404/410) unspecified; P8 §9.3 says ticket "SHOULD" be in `Authorization` "or a custom header", contradicting P7 §3.6/§9.5 (MUST `Authorization: Bearer`, custom ticket header negotiation prohibited). Follow P7.
9. **Error-code naming inconsistency**: P3 `direct.*`, P4 `group.*`, P6 `group.e2ee.*` vs P5 `anp.direct.e2ee.*`, P7 `anp.attachment.*`. Use spec strings verbatim.
10. **P9 ranges are JSON integers**, unlike P1 §7.3 decimal-string convention for counters.
11. **No receipts/read-state in any profile**: the only acknowledgments are synchronous acceptance results and `group_receipt` (Host acceptance). Delivered/read receipts are explicitly non-goals.
12. **Idempotency record retention** and Access Grant lifetime are unspecified.
13. **P8 depends on P4 v2** even for direct-only federation (see §13.1).
14. **P1 `limits` keys** beyond `max_request_bytes`/`max_message_bytes` not standardized; P5 says non-default `MAX_SKIP` "must be exposed via capability negotiation" but no field name is defined (suggest `limits.max_skip`).
15. **`group.state_changed` origin**: `meta.sender_did = group_did`; no origin proof defined for Host-originated notifications — authenticity rests on s2s `serviceDid` HTTP signature (caller anchor `body.group_did`) and embedded `group_receipt.proof`.
16. **P5 HKDF over `SK`**: `RK0/CK0/SID = HKDF-Expand(SK, info, L)` uses `SK` directly as PRK (no second Extract) — implement exactly as written.
17. **P6 candidate status**: `0xF0A1` is private-use; the stable code point will change the wire (breaking draft revision).
18. **`deviceManifest` JSON-LD context**: only defined in the example `@context` (`https://agentnetworkprotocol.com/ns/message/v2#…`), not normatively in P2.
