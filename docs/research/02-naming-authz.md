# ANP Naming (WNS / ANP-04) and Authorization (ANP-05) — Implementation Notes

Source repo: `/tmp/anp-research/AgentNetworkProtocol` (HEAD `0837cfd`, grafted single-commit clone, commit date 2026-10-23). Spec set ANP 1.2.

Files read in full:
- `04-anp-did-wba-name-space-specification.md` (ANP-04, **Released v1.2**)
- `appendix-b-compatibility-with-native-did-web.md` (Appendix B, **Released v1.2**; owns did:web Handle compatibility, B.4)
- `05-anp-did-authorization-protocol-specification.md` (ANP-05, **Draft / not released, v0.7**, "ANP vNext; not part of the ANP 1.2 release")
- `docs/anp-05-validation-guide.md` (informative, AUTHZ-* scenarios)
- `standard/W3C-proposal/DID-OAuth-Compatibility Discussion.md` and `DID-OAuth-Integration-Solution.md` (skimmed; historical/proposal context only)
- `tests/did-oauth-draft.test.mjs` (doc-consistency tests for ANP-05; used to detect a gap, see §0)

Conventions in these notes: "MUST" etc. are quoted from the spec. "Note:" marks my own analysis or inference.

---

## 0. CRITICAL FINDING: ANP-05 v0.7 Section 11 (VC Profile) body is missing

In the cloned HEAD, and in upstream `main` (checked via raw.githubusercontent and `gh api`), ANP-05 v0.7 has:

```
<a id="vc-authorization"></a>
## 11. VC-based authorization

## 12. Errors
```

The Section 11 heading is there, but the body (subsections 11.1–11.9) is empty. The same is true of the Chinese mirror. Evidence:

- Upstream commit `6683793dc1` ("update auth draft", 2026-10-15) deleted 364 lines from both EN and CN ANP-05 files (+0 −364). Commit `4aa866428b` ("docs: associate ANP-05 DIDs with standard CIMD clients", 2026-10-22) then made the v0.7 changes on top of it.
- The repo's own doc tests fail because of it: `node --test tests/did-oauth-draft.test.mjs` gives 103 tests, 65 pass. Every VC test fails (for example "VC delegation credential example follows the Section 11.2 shape"), and so does the anchor-count test, which expects 27 anchors. The file has 23: `errors`, `vc-oauth-composition`, `vc-direct-presentation` and `vc-organization-agents` are missing.
- The v0.7 text still points to Sections 11.2, 11.3, 11.4, 11.6 and 11.9 (§1.1, §2.2, §14), and the validation guide says v0.7 "retains those VC scenarios unchanged" (AUTHZ-51..75).

**What I did:** I recovered the last full VC Profile text from upstream commit `63a99ddf72` (ANP-05 **v0.6**, file `05-anp-did-authorization-protocol-specification.md`, lines 815–1183) using `gh api ... ?ref=63a99ddf72`. It uses the same VC Profile identifier, `anp.authorization.vc.v1-draft2`. The test file in HEAD still asserts this exact v0.6 Section 11 content (examples and normative sentences), so it is the intended v0.7 VC content. §2.10 of these notes is based on that recovered text and is labeled **[v0.6-recovered]**.

**Implementer action:** Treat the VC Profile as specified by v0.6 §11 plus the v0.7 §1/§2/§12–§14 references until upstream restores the section. Confirm with the ANP maintainers; this looks like an accidental deletion. It is listed as open question Q1.

---

## 1. WNS — WBA Name Space (ANP-04, Released v1.2)

### 1.1 Purpose and core commitments

- A Handle (e.g. `alice.example.com`) is a human-readable alias for a `did:wba` DID. The resolution chain is `Handle → /.well-known/handle/{local} → DID → DID Document (per ANP-03) → service`.
- Handles give a **stable** name while path-type did:wba DIDs **rotate**: `did:wba:example.com:user:alice:e1_<fingerprint>` changes when the binding key or profile changes (`e1_` ↔ `k1_`).
- **Protocol commitment every conforming Handle Provider MUST make and enforce:** once allocated, a Handle belongs permanently to the same subject. It is non-transferable and cannot be reused after revocation (tombstone).
- Handle stability does **not** replace ANP-03's cryptographic DID migration proof (`successorDid`, `alsoKnownAs`, document `proof`).
- WNS is deliberately minimal. It does **not** specify registration, management, identity-verification or length-policy business processes; those are Provider-defined (§8.2).

### 1.2 Handle syntax (§3.1)

```abnf
handle     = local-part "." domain
local-part = (ALPHA / DIGIT) *61(ALPHA / DIGIT / "-") (ALPHA / DIGIT)
domain     = ; A valid Fully Qualified Domain Name (FQDN), see RFC 1035
```

Rules:
- local-part MUST contain only ASCII lowercase `a-z`, digits `0-9`, and `-`.
- It MUST begin and end with a letter or digit.
- It MUST NOT contain `--`.
- It MUST be 1–63 characters long.
- domain MUST be a valid FQDN protected by a TLS certificate.
- domain MUST NOT carry a port.
- All input MUST be normalized to lowercase before processing (`Alice.Example.com` → `alice.example.com`).

Valid: `alice.example.com`, `bob-smith.example.com`, `agent-42.example.com`, `a.example.com`. Invalid: `-alice.example.com`, `alice-.example.com`, `al--ice.example.com`.

**Parsing rule (Note):** the local-part is the **first DNS label**. Everything after the first `.` is the domain. Example: `alice.sub.example.com` gives local=`alice`, domain=`sub.example.com`.

**ABNF inconsistency (Note):** `(ALPHA/DIGIT) *61(...) (ALPHA/DIGIT)` requires at least 2 characters, but the prose and the `a.example.com` example allow 1 character. Implement the prose (1–63). The prose ban on `--` is also not expressible in this ABNF. Apply both checks in code.

**IDN / punycode (Note — spec gap):** The spec does not mention IDN, U-labels, A-labels (`xn--`) or UTS-46.
- Local-part: the ASCII-only + no-`--` rules rule out punycode (`xn--...`), so IDN local-parts are impossible by construction. §9.2 cites this as homograph protection.
- Domain: only "valid FQDN (RFC 1035)" is required. Recommended handling:
  - Accept only A-label (ASCII/punycode) domains on the wire.
  - If you accept Unicode user input, convert with UTS-46/IDNA2008 before lowercase comparison, then compare in A-label form.
  - Show the domain prominently in the UI (§9.2 SHOULD) and consider a mixed-script warning.
- See Q4.

Reserved words (§3.3, SHOULD maintain and publish):
- Protocol words: `did`, `agent`, `well-known`, `service`
- System words: `admin`, `root`, `system`, `api`
- Defensive words: `support`, `security`, `official`
- The actual list is per Provider.
- Note: `by-did` collides with the DID Confirmation Endpoint path `/.well-known/handle/by-did`. Providers that implement that endpoint MUST effectively reserve the local-part `by-did`. The spec does not say this; see Q5.

### 1.3 `wba://` URI form (§3.2)

- `wba://alice.example.com` is used only for sharing and recognition, and is semantically equal to the Handle.
- Clients MAY accept it. If they do, they MUST strip `wba://` before resolution.
- Implementations MUST NOT make `wba://` support a prerequisite for interoperability.
- The scheme is **not IANA-registered**. Alternative shareable URL: `https://{domain}/.well-known/handle/{local-part}`.
- Note: No rules for `wba://` with a path, query, port, userinfo or trailing slash. Reject anything other than `wba://<handle>` after stripping.

### 1.4 Resolution endpoint (§4.2)

- URL: `https://{domain}/.well-known/handle/{local-part}`
- Method `GET`. Response `Content-Type: application/json`.

```http
GET /.well-known/handle/alice HTTP/1.1
Host: example.com
Accept: application/json
```

### 1.5 Handle Resolution Document (§4.3)

```json
{
  "handle": "alice.example.com",
  "did": "did:wba:example.com:user:alice:e1_<fingerprint>",
  "status": "active",
  "binding_generation": "8",
  "updated": "2025-01-01T00:00:00Z",
  "versionId": "42",
  "ttl": 300,
  "profile": {
    "type": "DIDSubjectProfile",
    "subject_did": "did:wba:example.com:user:alice:e1_<fingerprint>",
    "subject_type": "person",
    "handle": "alice.example.com",
    "display_name": "Alice",
    "description": "Researcher and AI agent user",
    "avatar_uri": "https://example.com/avatars/alice.png",
    "profile_uri": "https://example.com/alice/",
    "discoverability": "listed",
    "updated": "2025-01-01T00:00:00Z",
    "versionId": "profile-7",
    "ttl": 300
  }
}
```

| Field | Req | Semantics |
|---|---|---|
| `handle` | Required | Complete Handle |
| `did` | Required | The DID currently bound |
| `status` | Required | `active` \| `suspended` \| `revoked` (§4.7) |
| `binding_generation` | Required | **Decimal string.** MUST be positive at first allocation. MUST strictly increase whenever the bound DID or the status changes. Never roll back or reuse a value. Security-critical rollback protection. |
| `updated` | Optional | ISO 8601 |
| `versionId` | Optional | Mapping version for caching and diagnostics. MUST NOT replace `binding_generation` for rollback protection. |
| `ttl` | Optional | Suggested cache lifetime in seconds |
| `profile` | Optional | Presentation metadata only. MUST NOT be used for authn, authz, routing, service discovery, E2EE binding or security-profile negotiation. |

Status values (§4.7):

| Status | Meaning |
|---|---|
| `active` | Resolvable |
| `suspended` | Temporarily unresolvable, recoverable |
| `revoked` | Permanent. Provider MUST keep a permanent tombstone and MUST NOT reallocate the Handle. |

Notes:
- `binding_generation` is a decimal **string**. Compare it as an arbitrary-precision integer, not lexically and not as a JS double.
- A verifier SHOULD persist the highest generation it has accepted per Handle and reject lower values (rollback). The spec states the semantics ("verifiers can reject replayed historical bindings") but no explicit verifier MUST; see Q6.
- `suspended` is a body status value, but §4.8 defines no HTTP status code for suspended. Presumably the response is 200 with `status: "suspended"`; see Q7. Treat `suspended` as **not resolvable** for any security-sensitive use.

### 1.6 DID Confirmation Endpoint (private mode, §4.3.1)

- Recommended URL: `https://{domain}/.well-known/handle/by-did?did={urlencoded-did}`. `GET`, JSON.
- Response:

```json
{ "did": "did:wba:example.com:user:alice:e1_<fingerprint>", "confirmed": true, "status": "active", "updated": "2025-01-01T00:00:00Z", "ttl": 300 }
```

- `did` is required. `confirmed` is required and MUST be `true`. `status`, `updated` and `ttl` are optional.
- The response SHOULD NOT return `handle`, so the Handle is not disclosed through the DID Document.

### 1.7 Profile object (`DIDSubjectProfile`, §4.3.2)

Fields:
- `type`: SHOULD be `DIDSubjectProfile`.
- `subject_did`: required.
- `subject_type`: recommended. Values: `person`, `agent`, `group`, `organization`, `service`, `application`, `unknown`.
- `handle`: optional.
- `display_name`: recommended.
- Optional: `description`, `avatar_uri`, `profile_uri`, `discoverability` (`private` \| `listed` \| `public`), `labels`, `updated`, `versionId`, `ttl`, `proof`.

Optional `proof` (object-level assertion):

```json
"proof": {
  "type": "DataIntegrityProof",
  "cryptosuite": "eddsa-jcs-2022",
  "created": "2025-01-01T00:00:00Z",
  "proofPurpose": "assertionMethod",
  "verificationMethod": "did:wba:example.com:user:alice:e1_<fingerprint>#key-1",
  "proofValue": "z..."
}
```

Rules:
- `profile.subject_did` MUST equal top-level `did`. If present, `profile.handle` MUST equal top-level `handle`. On mismatch the client MUST ignore `profile` and MAY flag the result as suspicious.
- An absent or unknown `subject_type` MUST be treated as `unknown`. It MUST NOT be an authorization input. Private extensions go in `labels`.
- `display_name` is not an identity: duplicates are allowed and it can change. It MUST NOT be used in signatures, authz, E2EE binding or endpoint selection.
- Output SHOULD use `display_name`. Servers MAY accept legacy input `name`; standard output SHOULD NOT emit `name`.
- `avatar_uri` and `profile_uri` SHOULD be absolute HTTPS. Clients MUST NOT infer bindings, endpoints or capabilities from `profile_uri`. Treat remote content as untrusted.
- `labels` are non-security only.
- Caching:
  - Top-level `ttl` governs the handle→did mapping. `profile.ttl` governs the profile; when absent, fall back to top-level `ttl` as the maximum.
  - SHOULD NOT cache `profile` longer than the resolution document.
  - When the top-level `did` changes, clients MUST invalidate profile cache entries for the old DID.
- Proof:
  - If `proof` is absent, the profile MUST be treated as provider-supplied UI metadata.
  - If present, the signed object is the whole `profile` with `proof` removed.
  - The VM's DID MUST equal `subject_did`. The VM SHOULD be in `assertionMethod`.
  - A valid proof still MUST NOT be used for routing, authz, discovery or E2EE.
- Group projection: `group_did`→`subject_did`, `group_profile.display_name`→`display_name`, and so on. On conflict, the Group Host's `group_profile`/`group_policy`/`group_state_version` wins.
- UI: clients MUST keep working when `profile` is absent. They SHOULD show the Handle or DID next to `display_name`, especially before high-risk operations.

### 1.8 Mapping rules (§4.4, §4.6)

1. **Hostname consistency:** the Handle domain MUST equal the DID hostname. If the DID authority has a port (`did:wba:example.com%3A8800:...`), ignore the port and compare hostnames only.
2. A Handle is bound to exactly one DID.
3. The local-part is unique within a domain. The same local-part MAY exist on different domains.
4. WNS does not redefine `e1_`/`k1_` fingerprints (ANP-03 owns them).
5. Permanent reservation: never transfer or reallocate.
6. `binding_generation` is monotonic.

§4.5: after getting the DID, implementations MUST resolve the DID Document per ANP-03 (WBA) or the ANP-02 Web binding (did:web). They MUST NOT bypass the DID Document to infer endpoints, keys or other DID information from the Handle.

Note: the spec does not say whether one DID may have multiple Handles. "One-to-one correspondence" (§4.4) suggests not, but the explicit rules only say a Handle → exactly one DID. See Q8.

### 1.9 HTTP responses and errors (§4.8)

| Code | Meaning |
|---|---|
| 200 | Resolution Document |
| 404 | Never registered, **or the server is unwilling to disclose existence** |
| 410 | Revoked (permanently) |
| 301 / 308 | Migrated. `Location` points to the new Resolution Endpoint. |
| 429 | Rate limited. SHOULD include `Retry-After`. |

Error body example:

```json
{ "error": "handle_not_found", "message": "The handle 'bob.example.com' does not exist" }
```

Rules for 301/308:
- `Location` is a migration hint only.
- The client MUST re-run the §6 bidirectional verification at the new address and MUST NOT accept a new binding based only on the redirect.
- §8.3: the `Location` endpoint MUST still satisfy verification rules for the **input Handle domain**.

Note: only `handle_not_found` is shown as an error code. No error-code registry is defined. §9.4 says Providers SHOULD normalize error structures to limit state leakage.

### 1.10 Bidirectional binding verification (§6)

Forward: the Provider's Resolution Endpoint says Handle → DID. Reverse: the DID Document has an `ANPHandleService` service:

```json
{ "id": "did:wba:example.com:user:alice:e1_<fingerprint>#handle", "type": "ANPHandleService", "serviceEndpoint": "https://example.com/.well-known/handle/alice" }
```

Private confirmation mode:

```json
{ "id": "did:wba:example.com:user:alice:e1_<fingerprint>#handle", "type": "ANPHandleService", "serviceEndpoint": "https://example.com/.well-known/handle/by-did?did=did%3Awba%3Aexample.com%3Auser%3Aalice%3Ae1_%3Cfingerprint%3E" }
```

Service rules:
- `type` MUST be `ANPHandleService`. `id` SHOULD use the `#handle` suffix.
- `serviceEndpoint` MUST be a dereferenceable absolute HTTPS URI under the Provider's domain.

**When verification is mandatory (MUST):**
- identity authentication
- authorization decisions
- IM recipient resolution
- automated calls that change state, write, charge money or create resources

For UI display, search preview and directory browsing, verification MAY be deferred. It MUST be completed before any security-sensitive operation.

**Algorithm (§6.3.1, normative):**
1. Parse the input Handle into (domain, local). Build `E = https://{domain}/.well-known/handle/{local}`.
2. GET `E` → Resolution Document. Take its `did` (call it D).
3. Resolve D per ANP-03 → DID Document.
4. Find the service with `type == "ANPHandleService"`.
5. `serviceEndpoint` MUST be an absolute `https` URI, and its hostname MUST equal the Handle domain.
6. GET `serviceEndpoint` → JSON.
7. If `serviceEndpoint == E` exactly **and** the returned `did == D` **and** the returned `handle ==` the input Handle, the result is **`exact-handle`**.
8. Else, if the returned doc has no `handle` **and** `confirmed == true` **and** `did == D`, the result is **`provider-confirmed`**. This confirms only the provider relationship.
9. Anything else is a failure: no service, not https, hostname mismatch, dereference failure, `did` mismatch. Result **`unverified`**.
10. Where a specific Handle must be confirmed (authn, authz, recipient confirmation before sending), the verifier MUST obtain `exact-handle`. `provider-confirmed` is insufficient.

Verification levels (§6.3.2, SHOULD distinguish):

| Result | Meaning |
|---|---|
| `exact-handle` | Precise bidirectional binding for this Handle |
| `provider-confirmed` | The DID ↔ Provider relationship is confirmed, but no specific Handle is |
| `unverified` | Failed, or trust strength insufficient |

Notes for implementers:
- In step 7, "exactly the same" means string equality of the URI. Normalize your constructed `E` the same way the Provider publishes it: lowercase host, no trailing slash, no default port. The spec does not define URI normalization; see Q9.
- Step 6 dereferences the same URL as step 2 in public mode. You can reuse the step-2 response only if you are sure it came from the same URL. The spec says "MUST dereference `serviceEndpoint`" (Summary MUST #15).
- The spec says nothing about **multiple** `ANPHandleService` entries. Safe policy: succeed if any entry yields `exact-handle`; reject ambiguous entries pointing at different hosts. See Q10.
- Also check `status == "active"` before treating the binding as usable. The verification algorithm does not mention status, but `suspended`/`revoked` clearly should not authenticate.
- SSRF: the DID Document controls `serviceEndpoint`. Even though its hostname must equal the Handle domain, apply the usual outbound-fetch protections (no private IPs, size and time limits). Note: ANP-04 itself does not state SSRF rules; ANP-05 §13 does for its own fetches.

### 1.11 Handle lifecycle

| Phase | Rules |
|---|---|
| Registration | Provider-defined process (§8.2). Uniqueness within the domain is a MUST. Reserved words SHOULD be blocked. Initial `binding_generation` MUST be a positive decimal string. |
| DID rebinding (rotation) | §8.4. Once the new DID Document is available **and** the Provider's independent recovery or identity-verification policy succeeds, the Provider MUST update the mapping and strictly increase `binding_generation`. Rebinding MUST be a credential update for the **same subject**, never a transfer. Provider SHOULD lower the TTL during rotation windows. Clients MUST NOT assume a Handle stays bound to the same DID, and MUST re-run bidirectional verification after getting a new DID for security-sensitive operations. |
| Treating old/new DIDs as one subject | MUST follow ANP-03 from the old DID: stable subject path, every direct `successorDid`, reaching a proof-valid active DID. A valid old-binding or pre-authorized recovery proof gives cryptographic continuity. Without one, an authenticated same-origin HTTPS full-chain resolution may report `provider_asserted`. The Handle mapping, a matching prefix or `binding_generation` alone yield only `unverified`. Two DIDs MUST NOT be treated as the same subject only because of the same Handle or DID prefix. |
| Suspension | `status: "suspended"`. Recoverable. A `binding_generation` bump is required (status change). |
| Revocation / deletion | `status: "revoked"` or HTTP 410. Permanent tombstone. No ordinary registration, recovery or admin flow may reallocate the Handle to anyone. |
| Transfer | **Forbidden.** Handles are non-transferable. |
| Reuse | **Forbidden** (tombstone). |
| Provider migration (§8.3) | Same complete Handle and same domain; operations/infrastructure move only. Moving to a different domain creates a different Handle with no continuity. The new Provider MUST inherit the highest accepted `binding_generation`, the binding history and the tombstone obligation; the next state MUST use a strictly greater generation. The old Provider MAY return 301/308, and the `Location` endpoint MUST satisfy verification for the input Handle domain. Both Providers SHOULD resolve during the migration window. The DID holder updates `ANPHandleService` (SHOULD). The client MUST re-verify. |

Note: since a "migration" must keep the same domain, a 301/308 `Location` pointing to another host fails §6 step 5 (hostname must equal the Handle domain). Cross-host redirects therefore cannot pass verification. Effectively, only same-domain path changes are allowed.

### 1.12 Caching (§4.3.2, §8.1)

- Providers SHOULD send `Cache-Control` and `ETag` (`Last-Modified` optional) and SHOULD rate-limit.
- Top-level `ttl` sets the mapping cache. `profile.ttl` sets the profile cache.
- Lower the TTL during migration or rotation windows (SHOULD).
- Invalidate profile cache entries on `did` change (MUST).
- Note: re-validate before security-sensitive operations whenever the cached entry is past `ttl`. A sensible default when `ttl` is absent is ≤300 s, the value used in the spec's examples.

### 1.13 Security considerations (§9)

- **Domain/TLS:** a Handle is only as secure as its domain and TLS setup.
- **Phishing/homographs:**
  - ASCII-only local-part.
  - Reserved words.
  - Clients SHOULD visually emphasize the domain.
  - Keep the Handle/DID visible next to `display_name`.
  - Note: domain-level homographs (punycode TLDs or labels) are not addressed; apply browser-style IDN display policy.
- **Squatting (§9.3):** reserved lists, registration review and dispute processes (SHOULD; Provider policy). Note: there is a tension with permanence. Because Handles are non-transferable and never reusable, dispute resolution cannot reassign a squatted Handle. It can only revoke it, leaving a tombstone. See Q11.
- **Enumeration/privacy (§9.4):**
  - The 200/404/410 difference leaks existence, so rate-limit.
  - 404 MAY be used to avoid disclosing existence.
  - Do not return sensitive data.
  - Use the by-did private mode when the holder does not want the Handle in the DID Document.
- **Anti-tampering/spoofing (§9.5):** bidirectional verification. Require `exact-handle` for high assurance.
- **Future work:** `providerDid` and `handleCommitment` are mentioned as possible future mechanisms. Not defined.

### 1.14 Native did:web compatibility (Appendix B.4)

- A did:web DID Document can declare `ANPHandleService`. The verifier MAY run a weaker, **domain-only** legacy check:
  1. resolve the Handle → DID
  2. resolve the DID
  3. find `ANPHandleService`
  4. take the scheme and domain of `serviceEndpoint`
  5. require `https` and a domain equal to the Handle domain
- The path need **not** equal `/.well-known/handle/{local}`. Any stable HTTPS URL on the same domain is acceptable. The verifier does **not** dereference it, and there is no `e1_`/`k1_` check.
- This result **does not produce** WBA `exact-handle` or `provider-confirmed`, and must not be promoted to them.
- WBA hostname consistency and the §6 exact/private flows do not extend to Web compatibility mode (ANP-04 header). There is no migration to WBA.
- Note: give this result a separate label in code (e.g. `web-domain-declared`) so policy cannot confuse it with `exact-handle`.

### 1.15 Integration points

- ANP-07 Agent Description MAY include `"handle": "alice.example.com"`. It is informative; the authoritative binding comes from WNS plus the DID Document.
- ANP-08 `.well-known/agent-descriptions` entries MAY include `handle`.
- ANP-09 IM: Handles are used for input and display only. Routing stays DID-based.
- Profile URL (§5): `https://{local}.{domain}/` or `https://{domain}/{local}/`. Business content only. MUST NOT be an authoritative source for binding or discovery.

---

## 2. ANP-05 DID-Based Authorization (Draft v0.7, NOT released)

Header facts:
- Document ID ANP-05. Status "Draft / not released". Version 0.7. "ANP vNext; not part of the ANP 1.2 release".
- OAuth Profile id: **`anp.authorization.oauth2.cimd.v1-draft1`**. VC Profile id: **`anp.authorization.vc.v1-draft2`**.
- Revision history:
  - v0.7 replaces the earlier DID-as-`client_id` design (`anp.authorization.oauth2.did.v1-draft4`, **not an alias**) with CIMD URL clients.
  - v0.6 removed VC→OAuth token exchange.
  - v0.5 added the VC Profile.
- "Implementations MUST match the exact revision and revalidate affected metadata and pending transactions before migration. A changed client identifier is a new OAuth client."

Normative baselines:
- OAuth: RFC 6749 + RFC 9700 + **CIMD draft-02** (`draft-ietf-oauth-client-id-metadata-document-02`, pinned, not an RFC). Also RFC 7523 (client-auth branch only), 7515/7517/7518/7519/8725, 8037, 9864, 8414, 9728, 9207, 7638, 7591 §2 (metadata names), 7636, 8707, 6750, 9068, 9449, 7009, 7662, 8252 §7.3, 6234, and the W3C CID Multikey spec.
- Informative only: OAuth 2.1 draft-16 and rfc7523bis draft-11.
- VC: W3C VC Data Model 2.0, VC Data Integrity 1.0 + EdDSA cryptosuites (`eddsa-jcs-2022`), Bitstring Status List 1.0.
- Informative / roadmap: RFC 8693, RFC 9396 (RAR), RFC 8628 (device flow), VC-JOSE-COSE, OpenID4VP, OpenID4VCI.

### 2.1 Scope of v1 (what "v1" is supposed to deliver once released)

- Two **independent** paths:
  - (a) DID-associated **OAuth** for resource-side access authorization
  - (b) holder-bound **VC direct presentation** for single-level delegation and organization-role credentials
- **There is no VC/VP → OAuth token conversion in v1.**
- No multi-level redelegation. No token exchange. No generic per-operation (transaction) approval credential. No cumulative budgets. No standalone qualification/attribute credential profile.
- "A deployment claiming user-delegated support under the OAuth Profile MUST implement the authorization-code path; a client-credentials-only implementation MUST NOT claim OAuth user-delegation capability."
- AS authorization record for user-delegated grants MUST retain:
  - authenticated resource-owner id (issuer/tenant scoped)
  - URL client id
  - associated Agent DID (only if verified)
  - target resource
  - granted scopes
  - approval source and time
  - lifetime/revocation policy
  - stable internal grant reference
- Security baseline (MUST NOT): implicit grant, ROPC, access tokens in URI query strings, PKCE `plain`. Authorization code requires S256 PKCE, exact redirect matching (with only the loopback-port exception) and issuer/session validation. Roadmap features MUST NOT be advertised as v1.

### 2.2 When to use ANP-02 vs OAuth vs VC (§2.1–§2.2)

| Need | Use |
|---|---|
| Prove which DID sent a request; receiver applies local policy | **ANP-02** HTTP request auth (its cache token is not an OAuth token) |
| Resource-side–controlled access: user consent at a service with accounts, M2M with service-configured permissions, central revocation, short-lived tokens, per-resource isolation, existing OAuth RS | **OAuth Profile** |
| Authority originates **outside** the resource side: a company authorizes a purchasing Agent; an org appoints an HR Agent; one mandate shown to several unintegrated services; peer-to-peer without an AS | **VC Profile** (direct presentation) |

The spec summarizes the split this way. OAuth answers "does the resource side allow this client to perform this operation on this resource now?" VC answers "which issuer made what verifiable statement about this Agent?"

Comparison:

| Aspect | OAuth token | VC delegation/role credential |
|---|---|---|
| Issuer | AS trusted by RS | User, organization or accrediting body |
| Decision | AS before issuance; RS enforces | Each verifier at presentation |
| Scope | One resource per token (this Profile) | Possibly multi-service; each verifier uses only its own entries |
| Verification | AS key or introspection | Issuer DID, holder DID, status list |
| Revocation | Short-lived; AS stops issue/refresh | Status list (cache latency) |
| Privacy | AS sees every grant | Verifier sees the whole credential; status-list host sees the verifier IP |

Hard rules:
- An RS MUST NOT accept a raw VC or VP as a Bearer access credential.
- An OAuth-only interface MUST NOT be bypassed through VC direct presentation.
- A VC/VP MUST NOT be sent to an OAuth token endpoint under this Profile.
- A successful VC/VP verification MUST NOT create, imply, mint or authorize an OAuth access token.
- ANP-05 reuses ANP-02's DID validation and authentication-key authorization model, but **not** its HTTP-signature serialization or challenges. The token endpoint MUST NOT require a second ANP-02 HTTP signature.
- An ANP-02 auth-cache token is not an ANP-05 token; implementations MUST keep the acceptance rules separate.
- A DID's `authentication` relationship does not grant access to application resources.

### 2.3 Roles and identifiers (§3)

- `client_id` is the **exact HTTPS CIMD URL**. The Agent DID is an associated identity, never the OAuth wire identifier.
- The request `client_id`, the CIMD `client_id`, and the assertion `iss` and `sub` MUST be the **same exact URL**.
- Assertion `sub` = the client. Access-token `sub` = the authorization subject (resource owner for user delegation). MUST NOT copy the assertion `sub` into a user-delegated token.
- Assertion `aud` = the AS. Access-token audience = the RS.
- Client records, grants and token caches MUST be scoped by (issuer, tenant/trust domain, client_id). Resource owner, grant, target and processing mode are kept separately.
- RFC 9068 JWT `client_id` claim = the URL, never the DID. RFC 7662 introspection `client_id` = the URL.
- An RS that depends on client identity MUST get it from a trusted token, introspection or equivalent state, and MUST reject when it is unavailable. It must not trust caller-supplied fields.
- An RS MUST NOT infer a verified DID from an unvalidated `anp_did`, a `kid` label or URL contents. **No token claim is defined for conveying a verified DID** to an RS; a trusted channel or agreed extension is needed. If a resource needs DID authentication and the AS did not verify the binding, it needs an independent proof bound to the request/token under a separately agreed binding, or it MUST refuse. No such proof exchange is defined in this revision.
- A shared CIMD URL is **one** OAuth client even when used by many Agent instances. For per-Agent identity, publish separate URLs and keys (SHOULD).

### 2.4 CIMD URL client identity and DID binding (§4)

**CIMD URL syntax (§4.1):**
- HTTPS. MUST have a path.
- MUST NOT contain userinfo, a fragment, or `.`/`..` segments.
- Publishers under this Profile MUST omit a query.
- Compare by **exact string equality** after one decoding step. Do not normalize ports, case, paths or aliases.
- A DID or DID URL MUST NOT be used as `client_id`.

**Processing modes (chosen before a transaction starts):**

| Mode | What the AS does |
|---|---|
| `cimd` | Standard CIMD discovery, URL-client auth, and OAuth. No DID resolution, no ANP extensions, no digest checks. |
| `did_bound` | Same OAuth messages, plus the DID ↔ URL ↔ metadata-digest ↔ actual-key checks. The AS advertises `anp_cimd_binding`. |

- The client MUST pin issuer, URL `client_id`, mode and authentication policy before authorization.
- If DID-bound identity is required and the capability is missing or checks fail, the client MUST abort. It MUST NOT retry in `cimd`.
- A `cimd` connection MUST NOT be reported as AS-verified DID authentication.

**DID Document `ANPCIMD` service (§4.2):**
- Exactly one service of `type: "ANPCIMD"` per DID for this Profile.
- `id` = DID + non-empty fragment. `serviceEndpoint` = the exact CIMD URL.
- Duplicate IDs or multiple matches are rejected.
- This is an experimental ANP type, so JSON-LD deployments need a pinned extension context.
- The older `ANPOAuthClientMetadata` service does **not** select this Profile.
- For `did_bound` the service MUST also contain:
  - **`anp_oauth_keys`**: a non-empty array of distinct VM IDs from this DID's **`authentication`** relationship, explicitly authorized for the URL client. Each MUST resolve to this DID + a non-empty fragment. `keyAgreement` keys and bare `verificationMethod` entries do not count.
  - **`anp_metadata_sha256`**: 64-character lowercase hex SHA-256 of the **exact CIMD response bytes**. These are UTF-8 bytes after HTTP transfer/content decoding, including whitespace and the final newline. Do not reserialize, and do not include headers. Reject a BOM, invalid UTF-8 and duplicate JSON members. Compute the digest after serialization and publish it via the DID method's authenticated update procedure.

Example DID Document (did:wba e1_; spec §9.2):

```json
{
  "@context": [
    "https://www.w3.org/ns/did/v1",
    "https://w3id.org/security/data-integrity/v2",
    "https://w3id.org/security/multikey/v1",
    {
      "ANPCIMD": "https://github.com/agent-network-protocol/AgentNetworkProtocol/blob/main/05-anp-did-authorization-protocol-specification.md#anpcimd",
      "anp_oauth_keys": { "@id": "https://github.com/agent-network-protocol/AgentNetworkProtocol/blob/main/05-anp-did-authorization-protocol-specification.md#anp-oauth-keys", "@type": "@id", "@container": "@set" },
      "anp_metadata_sha256": "https://github.com/agent-network-protocol/AgentNetworkProtocol/blob/main/05-anp-did-authorization-protocol-specification.md#anp-metadata-sha256"
    }
  ],
  "id": "did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28",
  "verificationMethod": [{
    "id": "did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28#auth-1",
    "type": "Multikey",
    "controller": "did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28",
    "publicKeyMultibase": "z6Mkk8HzVpDddKLmZ6Bzpxe3xyCGEqFuCTRTFkXZktTuDoqD"
  }],
  "authentication": ["did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28#auth-1"],
  "service": [{
    "id": "did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28#oauth-client",
    "type": "ANPCIMD",
    "serviceEndpoint": "https://agents.example/agent-a/oauth/client.json",
    "anp_metadata_sha256": "3d03045553c170ab505cc6b3211c903b4b1b23823d8f46881f312a6242b83ff5",
    "anp_oauth_keys": ["did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28#auth-1"]
  }],
  "assertionMethod": ["did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28#auth-1"],
  "proof": { "type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022", "created": "2026-09-27T00:00:00Z",
             "verificationMethod": "did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28#auth-1",
             "proofPurpose": "assertionMethod", "proofValue": "zDOCUMENT_PROOF_PLACEHOLDER" }
}
```

CIMD document served at `https://agents.example/agent-a/oauth/client.json` (HTTP 200, `application/json`):

```json
{
  "client_id": "https://agents.example/agent-a/oauth/client.json",
  "client_name": "Example Agent A",
  "token_endpoint_auth_method": "private_key_jwt",
  "token_endpoint_auth_signing_alg": "Ed25519",
  "grant_types": ["client_credentials", "authorization_code", "refresh_token"],
  "response_types": ["code"],
  "redirect_uris": ["https://agents.example/agent-a/callback"],
  "scope": "documents.read",
  "jwks": { "keys": [{ "kty": "OKP", "crv": "Ed25519", "x": "VEpJi1nTD8okbTyhNIyr-NlO4dH7if8D8FOccCQyxQQ",
                       "kid": "did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28#auth-1",
                       "use": "sig", "alg": "Ed25519" }] },
  "anp_did": "did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28"
}
```

**Verified test vectors (I computed these locally from the spec's JSON block, including its final LF):**
- SHA-256 of the CIMD block = `3d03045553c170ab505cc6b3211c903b4b1b23823d8f46881f312a6242b83ff5`. This matches `anp_metadata_sha256`.
- RFC 7638 thumbprint of the JWK = `RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28`. This matches the `e1_` DID suffix.
- Both are usable as unit-test fixtures. Note that the JSON uses 2-space indentation exactly as in the spec file. The digest depends on those exact bytes.

**CIMD publication rules (publisher):**

| Output | Rule |
|---|---|
| `client_id` | Exact URL |
| `jwks` **or** `jwks_uri` | Exactly one of the two. Public keys selected from DID `authentication`. `jwks_uri` must serve a standard JWK Set, not a DID Document. No private parameters. |
| `client_name`, `client_uri`, `logo_uri` | Display only. A self-asserted name is not verified identity. `client_name` is required and non-empty. |
| `redirect_uris` | Actual callbacks. Do not infer them from the DID domain. |
| `grant_types`, `response_types`, `scope` | Features, not grants of permission. Authorization code requires `response_types=["code"]` and `redirect_uris`. |
| `token_endpoint_auth_method` | `private_key_jwt`. (`none` is outside the DID-backed claim.) |
| `token_endpoint_auth_signing_alg` | Optional. An asymmetric algorithm compatible with the key. |
| `anp_did` | Optional experimental reverse-discovery hint. **Has no authority** until the DID-bound checks pass. |

- `anp_profile` and `anp_application_type` are **not** required. A standards-only CIMD is enough for `cimd` mode.
- Served by unauthenticated HTTPS GET with HTTP 200 and JSON (SHOULD use `application/json`).
- **Fetchers MUST NOT follow redirects** and MUST NOT accept error responses as metadata.
- No secrets in the CIMD.
- Enhanced fetchers MUST support documents ≥ 5 KiB and enforce a finite maximum size, timeout and concurrency bound.

**DID-bound verification (enhanced AS, §4.2 + §6.2):**
1. Get the candidate DID from trusted config or the `anp_did` hint. **Never solely from a JWT header.**
2. Validate the DID per method:
   - did:wba: ANP-03 e1_ path profile or bare-domain binding, document proof, fingerprint, active state. **k1_ is excluded and must not be implicitly enabled.**
   - did:web: native resolution, HTTPS, exact `id`, ANP-02 Web rules. No WBA fingerprint or proof.
   - Other methods (did:webvh, BID) need a documented adapter before they are advertised.
3. The document `id` equals the expected bare DID. Exactly one `ANPCIMD` service, whose `serviceEndpoint` equals `client_id` exactly. Reverse `anp_did`, if present, must agree. A conflicting reverse DID MUST NOT override an existing accepted binding.
4. Verify that `anp_metadata_sha256` equals the SHA-256 of the fetched CIMD bytes. A missing, malformed or mismatched digest fails closed. A caller-supplied override, or a digest supplied only by the metadata host, is not a substitute.
5. The **actual key used to verify the assertion** MUST be in `anp_oauth_keys` **and** in the current DID `authentication`. Compare public-key material or the RFC 7638 thumbprint, **not `kid`**. Reject ambiguous selection. A JWS-supplied `jwk`, `jku`, `x5u` or `x5c` MUST NOT replace the accepted key source.
6. The digest covers an embedded `jwks` but **only the URL string** of `jwks_uri`. With `jwks_uri`, the actual-key check against the DID is what protects you.
7. Freshness: DID, CIMD and auth-key material are valid for **≤ 300 s** (stricter limits win). Revalidate stale material before accepting an assertion. A missing `kid` may trigger one bounded refresh. Known deactivation or removal invalidates caches immediately.

Trust note (§2.3, §4.2): for did:wba e1_, document integrity comes from the Agent-controlled binding-key proof, so a malicious host can only deny service or replay an old document. For did:web, a compromised DID-document host can replace keys and the digest. Neither mode gives rollback resistance beyond the DID method's own freshness.

### 2.5 First-contact admission (§4.3)

- A CIMD AS MAY admit unknown client URLs, or restrict admission to approved or pre-registered ones. ANP adds **no mandatory registration API**. Admission ≠ resource access.
- Steps:
  1. Check URL syntax, flow, issuer and local suspension/admission policy **before** network work. A cache miss MUST NOT erase a prior block.
  2. Fetch and validate the CIMD and key source. In `did_bound`, run the §4.2 checks before using callbacks or config.
  3. Apply admission policy (client, deployment, metadata origin, algorithms, callback, grant/resource). Self-published values don't override policy.
  4. Bind the candidate transaction to issuer, `client_id`, mode, accepted metadata/callback, resource and auth policy. In `did_bound`, also pin the verified DID, service and digest. A cache entry ≠ proof of key possession.
  5. At `/token`, verify a fresh client assertion, then independently validate grant, resource owner, target and permissions. In `did_bound`, recheck key authorization and freshness. A changed binding or security-relevant metadata **invalidates the pending transaction**.
- Authorization code: discovery and callback approval happen at `/authorize`; key possession is proven at code redemption. **No extra front-channel DID signature.**
- A pre-registered CIMD URL stays a URL client. Newly discovered data MUST NOT silently replace a pinned registration.
- Implementations MUST distinguish policy-controlled admission from unconditional acceptance and report disabled first contact accurately.
- §13: rate-limit failed attempts, bound fetches and candidate records, and avoid durable allocations for unauthenticated floods.

### 2.6 AS discovery and the `anp_cimd_binding` capability (§5)

- Clients use RFC 9728 protected-resource metadata (from a `401` `resource_metadata`) and RFC 8414 AS metadata. Validate the resource↔AS association and the exact issuer.
- Trusted out-of-band config is allowed. A DID service or Agent Description is **not** authority to select a different AS.
- `cimd` mode needs `client_id_metadata_document_supported: true` (or trusted config), plus `private_key_jwt`, a common algorithm and the grant. Authorization code also needs S256 and an issuer-validation strategy.
- An enhanced AS MUST advertise:

| Field | Rule |
|---|---|
| `profile` | exactly `anp.authorization.oauth2.cimd.v1-draft1` |
| `did_methods_supported` | non-empty; methods actually validated |
| `client_enrollment_methods_supported` | non-empty subset of `self_published`, `pre_registered` |
| `redirect_uri_modes_supported` | if authorization code is enabled: subset of `https`, `loopback` |

- Advertising `anp_cimd_binding` commits the AS to enforce `did_bound` for **every** CIMD client at those endpoints. **There is no per-request opt-out.** An AS offering both behaviors needs separate issuer/endpoint configurations.

```json
{
  "issuer": "https://auth.example",
  "authorization_endpoint": "https://auth.example/authorize",
  "token_endpoint": "https://auth.example/token",
  "client_id_metadata_document_supported": true,
  "token_endpoint_auth_methods_supported": ["private_key_jwt"],
  "token_endpoint_auth_signing_alg_values_supported": ["RS256", "Ed25519", "EdDSA"],
  "grant_types_supported": ["client_credentials", "authorization_code", "refresh_token"],
  "response_types_supported": ["code"],
  "code_challenge_methods_supported": ["S256"],
  "authorization_response_iss_parameter_supported": true,
  "anp_cimd_binding": {
    "profile": "anp.authorization.oauth2.cimd.v1-draft1",
    "did_methods_supported": ["did:web", "did:wba"],
    "client_enrollment_methods_supported": ["self_published", "pre_registered"],
    "redirect_uri_modes_supported": ["https", "loopback"]
  }
}
```

### 2.7 Client assertion (private_key_jwt, §6)

Transport:
- `POST` to the token endpoint, `application/x-www-form-urlencoded`.
- Exactly one each of `grant_type`, `client_id`, `client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer` and `client_assertion`.
- Duplicate security parameters MUST be rejected.
- Compact JWS only: no JWE, no detached payload, no multiple auth methods.
- Never put the assertion in URLs, task data or logs.

| Header | Rule |
|---|---|
| `alg` | Mutually accepted asymmetric algorithm |
| `kid` | Unambiguous id in the accepted JWKS. MAY be a DID URL used as an opaque label. |
| `typ` | Per AS policy: `JWT`, omitted, or `client-authentication+jwt` if supported |

| Claim | Rule |
|---|---|
| `iss` | exact URL `client_id` |
| `sub` | exact URL `client_id` |
| `aud` | one exact value: the AS issuer, **or** the token endpoint URL if that is the AS's convention. Pinned beforehand. Never selected from an error or changed as a fallback. |
| `iat` | integer NumericDate |
| `exp` | integer, `0 < exp - iat <= 300` |
| `jti` | ≥128 bits of randomness, never reused |

Enhanced verifier rules:
- Require all claims. Reject duplicate JSON members, unknown `crit`, unsupported algorithms and role-confused JWTs.
- Time checks: `iat <= now+skew` and `now < exp+skew`, with skew ≤ 60 s. If present, `nbf` must be an integer with `nbf <= exp` and `nbf <= now+skew`.
- **Replay:** atomically reserve `(AS issuer, client_id, jti)` until `exp + skew`. Do it after crypto and claim validation, before grant processing, and across keys, replicas and concurrent requests. Invalid signatures must not poison the store. Replay-store failure fails closed. A later grant error does not free the `jti`.

Algorithms (§6.3):
- RS256 is the RFC 7523 mandatory-to-implement algorithm. **Enhanced ANP implementations MUST also support Ed25519.**
- Prefer the RFC 9864 `Ed25519` identifier. `EdDSA` is an opt-in compatibility choice restricted to Ed25519 keys.
- ES256 or others need explicit support.
- Reject `none`, `HS*`, unsupported curves and key/algorithm mismatches.
- RSA ≥ 2048 bits. For Ed25519 Multikey → JWK, validate multibase, multicodec `0xed` (`ed 01`) and the 32-byte length.

Example decoded assertion:

```json
{ "typ": "JWT", "alg": "Ed25519", "kid": "did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28#auth-1" }
```
```json
{ "iss": "https://agents.example/agent-a/oauth/client.json", "sub": "https://agents.example/agent-a/oauth/client.json",
  "aud": "https://auth.example", "iat": 1790467200, "exp": 1790467500, "jti": "wTHzTd4fT8uRPLbI4_QY0g" }
```

### 2.8 Authorization flows (§7)

General rules:
- An implementation MUST support at least one flow and advertise only the flows it supports.
- **One target resource per grant/token.**
  - With RFC 8707, send exactly one absolute HTTPS `resource` without a fragment.
  - `did_bound` MUST send an explicit `resource` on authorize, code redemption, client credentials and refresh.
  - Plain `cimd` may use the AS's configured single-resource binding instead. Lack of RFC 8707 never permits an unrestricted token.
- Token caches are keyed by (issuer, tenant, resource owner, client_id, resource, scopes, mode, sender key). **Never select a token by DID alone.**

**Client credentials (§7.1)**
- Only for a **confidential** client acting for itself, or under a prior resource-owner arrangement recognized by the AS.
- MUST NOT obtain a user's permissions based solely on a DID or CIMD.
- AS verifies the assertion and a current policy/grant for this client, resource and scopes.
- **No refresh token** for client credentials.

```http
POST /token HTTP/1.1
Host: auth.example
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=https%3A%2F%2Fagents.example%2Fagent-a%2Foauth%2Fclient.json&client_assertion_type=urn%3Aietf%3Aparams%3Aoauth%3Aclient-assertion-type%3Ajwt-bearer&client_assertion=SIGNED_CLIENT_ASSERTION&resource=https%3A%2F%2Fdocs.example%2Fapi&scope=documents.read
```
```http
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: no-store
Pragma: no-cache

{ "access_token": "OPAQUE_ACCESS_TOKEN", "token_type": "Bearer", "expires_in": 600, "scope": "documents.read" }
```

**Hosted authorization code + PKCE (§7.2, step by step)**
1. Agent calls the RS without a token → `401` with `WWW-Authenticate: Bearer resource_metadata="https://docs.example/.well-known/oauth-protected-resource/api", scope="documents.read"`.
2. Agent fetches RFC 9728 metadata (`resource`, `authorization_servers`, `scopes_supported`, `bearer_methods_supported`). It validates the resource association, then fetches RFC 8414 AS metadata and checks the exact `issuer` and capabilities. A mismatch means stop before sending credentials (AUTHZ-20).
3. Agent pins the transaction record: issuer, resource, URL client_id, mode, auth policy, approved `redirect_uri`, `state` (fresh, session-bound) and PKCE verifier.
4. Agent opens the system browser to `/authorize` with `response_type=code`, `client_id=<CIMD URL>`, `redirect_uri`, `resource`, `scope`, `state`, `code_challenge`, `code_challenge_method=S256`.
5. AS fetches the CIMD and JWKS. In `did_bound` it also resolves and validates the DID binding before trusting the callback. It applies admission and approves the redirect (exact match, no wildcards).
6. AS authenticates the **user** by its own method and gets consent, or applies a valid existing authorization. Client/DID authentication ≠ user authentication or consent.
7. AS redirects to the callback with `code`, `state` and `iss` (RFC 9207 when selected).
8. Client validates `state`/session and the issuer:
   - Missing, duplicate or mismatched `iss` aborts. This applies to error callbacks too.
   - Without RFC 9207, the client must use a preselected RFC 9700 mix-up defense, for example a per-issuer redirect URI.
   - **`did_bound` authorization code MUST support RFC 9207.**
9. Client POSTs `/token` with `grant_type=authorization_code`, the same `client_id`, `code`, the same exact `redirect_uri`, `code_verifier`, a **fresh assertion** and the same `resource`.
10. AS verifies the current key/binding and the assertion, then **atomically consumes** the single-use code, checking client, redirect, PKCE, target and grant bindings. It issues a token whose `sub` is the resource owner, not the client.
11. Agent calls the RS. The RS validates the token, current authorization and operation policy.

**Local (loopback) flow (§7.2.1)**
- Only if the AS explicitly supports it. CIMD support alone does not imply it.
- The approved metadata entry has scheme `http`, literal host `127.0.0.1` or `[::1]`, and an exact non-empty path.
  - Query, fragment, userinfo, `localhost`, alternative IP spellings and wildcards are not allowed.
  - The entry may omit the port or contain one concrete port. It is not a template.
- Matching:
  - **Only the port is ignored** when comparing metadata with the authorization request (RFC 8252 §7.3).
  - The request MUST include an explicit port in 1–65535.
  - IPv4 and IPv6 entries are separate approved values.
  - Everything else matches exactly, with no decoding or normalization.
- The AS binds the **full actual** redirect, including the port, to the code. Redemption must repeat it exactly.
- The listener:
  - opened **before** launching the system browser
  - bound only to the loopback interface
  - closed on completion or timeout
  - not an embedded webview, `0.0.0.0` or LAN listener
- The loopback exception never authorizes AS-side fetches to loopback or private addresses.
- Remote or headless Agents without a same-device browser are out of scope (RFC 8628 is on the roadmap).

| Item | Value |
|---|---|
| Approved metadata redirect | `http://127.0.0.1/callback` |
| Actual authorization request redirect | `http://127.0.0.1:49152/callback` |
| Required redemption redirect | `http://127.0.0.1:49152/callback` |
| Different port only at redemption | `http://127.0.0.1:49153/callback` → reject |
| `localhost` spelling | `http://localhost:49152/callback` → reject |

```http
POST /token HTTP/1.1
Host: auth.example
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&client_id=https%3A%2F%2Fagents.example%2Flocal-a%2Foauth%2Fclient.json&code=ONE_TIME_LOCAL_CODE&redirect_uri=http%3A%2F%2F127.0.0.1%3A49152%2Fcallback&code_verifier=LOCAL_PKCE_VERIFIER&client_assertion_type=urn%3Aietf%3Aparams%3Aoauth%3Aclient-assertion-type%3Ajwt-bearer&client_assertion=FRESH_LOCAL_CLIENT_ASSERTION&resource=https%3A%2F%2Fdocs.example%2Fapi
```

Note: the local Agent still uses `private_key_jwt` with its own per-Agent key. It is treated as an authenticated client, but client credentials stay restricted to qualified confidential deployments (§4.4, AUTHZ-26).

**Refresh (§7.3)**
- MAY be issued for authorization code only.
- Each refresh needs a fresh assertion for the same client and mode.
- Preserve the resource owner, grant and single target. **Scopes MUST NOT increase.** `did_bound` requires an explicit unchanged `resource`.
- MUST rotate refresh tokens with reuse detection, or use a supported sender-constrained mechanism.
- Invalidated bindings or grants block refresh.

### 2.9 Tokens and resource enforcement (§8)

Token endpoint response:
- Standard JSON with `access_token`, `token_type`, `expires_in`, and `scope` = the actual grant.
- Headers `Cache-Control: no-store` and `Pragma: no-cache`.
- An error response MUST NOT also return a token.
- The token has a finite lifetime. The 300 s assertion limit is **not** the token lifetime.

Token types:
- **Opaque** tokens need a trusted validation path (RFC 7662 introspection).
- **JWT** access tokens MUST follow **RFC 9068** (`typ=at+jwt`, required claims, signed by the AS).
- The Agent's DID key does not make the Agent a token issuer.

```json
{ "iss": "https://auth.example", "sub": "user-248", "aud": "https://docs.example/api",
  "client_id": "https://agents.example/agent-a/oauth/client.json",
  "iat": 1790467200, "exp": 1790467800, "jti": "example-access-token-01", "scope": "documents.read" }
```

- The client assertion MUST NOT be accepted as an access token, ID token, refresh token or grant.
- `Bearer` per RFC 6750. **DPoP is RECOMMENDED** when AS and RS both support it, but optional. With DPoP, RFC 9449 applies: `token_type=DPoP`, `Authorization: DPoP`, `ath` at the RS, `cnf.jkt`. The DPoP key need not be the DID key. If policy requires DPoP, never fall back to Bearer.
- The RS MUST validate:
  - trusted AS
  - validity
  - revocation/status
  - audience = this resource
  - scope
  - local business policy
  It does not need to resolve DIDs.
- **Inbound vs outbound (§8.2):** an Agent acting as both RS and client keeps them separate. An A-targeted token MUST NOT be forwarded to B. Get a B-targeted token under B's AS. Client-only permissions MUST NOT substitute for missing user delegation. No token exchange in v1.
- **Incremental authorization (§8.3):**
  - No token → `401`. Insufficient permissions → `403` with `insufficient_scope`. The RS SHOULD include `resource_metadata` and the minimal scopes.
  - The client verifies the challenge belongs to its RS/AS, then requests a new approval with bounded retries. It never silently switches to client credentials.
  - Before **each operation**, the RS MUST check that authorization is still valid under the expiry/revocation policy.
  - Policy requiring online status fails closed when the status is unavailable.
  - Session IDs or open streams do not grant authority.
  - Credentials stay out of prompts, task text and artifacts.
- **Human / high-risk per-operation approval (§13):**
  - Where resource policy requires it, the RS MUST verify approval of the **actual operation**, including one-time-use and expiry, before executing, or reject.
  - General consent, task instructions, client auth and DPoP MUST NOT substitute for it.
  - v1 defines **no approval credential format**.
  - All permission decisions MUST be deterministic server-side policy, never inferred by an LLM.

### 2.10 VC Profile `anp.authorization.vc.v1-draft2` — direct presentation **[v0.6-recovered; body missing from v0.7 HEAD, see §0]**

**Roles (11.1)**
- **Issuer**: the user or org holding the authority. It signs with a key in **its `assertionMethod`**, and the key stays with the issuer.
- **Holder**: the Agent. It MUST be `credentialSubject.id`.
- **Verifier**: an RS, service, gateway or peer Agent.
- **Status list**: a Bitstring Status List credential published by the issuer.
- **The issuer MUST NOT be the holder** (a self-issued delegation is invalid).
- Issuer and holder DIDs are validated as in §6.2: same method scope, **k1_ rejected**.

**Delegation credential `ANPAgentDelegationCredential` (11.2)**
- `@context` = `["https://www.w3.org/ns/credentials/v2", "https://agent-network-protocol.com/contexts/authorization/v1"]`.
  - The context is experimental and must be published and fixed before a stable release.
  - **Never fetch a context outside the allowlist.**
- `type` ⊇ `["VerifiableCredential","ANPAgentDelegationCredential"]`.

| Field | Rule |
|---|---|
| `id` | required URI unique within the issuer (e.g. `urn:uuid:`) |
| `issuer` | bare DID string |
| `validFrom`, `validUntil` | both required, `validUntil > validFrom`. Shortest validity the task needs (SHOULD). |
| `credentialSubject.id` | bare Agent DID |
| `credentialSubject.permissions[]` | non-empty. Each entry has `resource` (absolute HTTPS URI, no fragment, compared exactly with RFC 8707 `resource`), `actions` (non-empty strings in the RS's OAuth scope namespace) and optional `constraints`. |
| `constraints.perOperationLimit` | `{ "value": "<non-negative decimal string, ≤ currency minor-unit digits>", "currency": "<ISO 4217>" }`. **No cumulative budget.** |
| `credentialStatus` | ≥1 `BitstringStatusListEntry` with `statusPurpose: "revocation"`; optional `suspension` entry |
| `proof` | `DataIntegrityProof`, `proofPurpose: "assertionMethod"`, VM in the issuer's `assertionMethod` |

- Cryptosuite: **MUST support `eddsa-jcs-2022`.** Others only when advertised and enabled. No RDF canonicalization, but the context allowlist is still enforced. No VC-JOSE-COSE, SD-JWT VC or selective disclosure.
- An **unknown constraint** term means reject the whole permission entry. Never ignore it.
- For `perOperationLimit`, the RS documents which amount is compared. If the amount is undocumented or the currency differs, **reject**. Never convert currency or guess the amount.
- Issuance:
  - The issuer SHOULD show the human the Agent DID, resources, actions, constraints and validity, and get explicit confirmation.
  - The issuing key MUST NOT go to the Agent.
  - **No issuance protocol is defined** (ANP messaging, a local interface or OpenID4VCI are all acceptable).

**Organization role credential `ANPAgentRoleCredential` (11.2)**
- Same `@context`, `id`, validity, `credentialStatus` and `proof` rules.
- `credentialSubject.role`: a non-empty string, **display/audit only**. MUST NOT be used alone as an authorization basis.
- `credentialSubject.capabilities[]`: non-empty. Each entry has `action` (absolute URI for a business action) and optional `constraints`. There is no `resource` and no `permissions`.
- The verifier maps action URIs only through a **documented correspondence**. An unmapped action MUST be treated as unknown and its entry rejected.
- A role credential cannot grant rights the org lacks. For third-party personal data, the RS MUST independently confirm a valid basis.

**Presentation (11.3)**
- The VP:
  - `type` ⊇ `VerifiablePresentation`
  - `holder` = the Agent's bare DID
  - `verifiableCredential` contains **exactly one** authorization credential (delegation **or** role)
- Other credentials may be attached only when the verifier requests them (for example an org-identity VC). Attached credentials are not holder-bound and grant nothing by themselves.
- A qualification or attribute VC MUST NOT substitute for the authorization credential.
- VP `proof`:
  - `DataIntegrityProof` with `proofPurpose: "authentication"`
  - VM in the holder's `authentication`
  - `domain` = a single string naming the verifier
  - `challenge` = a one-time value generated and stored by the verifier
  - `created` = the signing time
- Verifier checks:
  - Compare `domain` and `challenge` exactly. A challenge is accepted once (atomic consume).
  - `created` within 300 s of now, skew ≤ 60 s.
  - A VP is valid only for its `domain` and MUST NOT be forwarded.
- Before signing, the Agent MUST confirm `domain` is the verifier it is actually dealing with: the HTTPS origin it called, or the peer DID of the messaging session.

**Verification order (11.4). MUST run in this order, reject on any failure, no weaker fallback:**
1. **Format/size**
   - Support at least 16 KiB and enforce a finite maximum.
   - Reject duplicate JSON members, non-allowlisted contexts and unsupported suites.
   - The credential must have exactly one ANP authorization type, and that type must be in the stored transaction's `credential_types`. No substituting a different supported type.
2. **VP proof**: resolve the holder DID and verify the proof. Check `domain`, `challenge` and `created`.
3. **Holder binding**: `holder` == the DID authenticated by the carrying ANP-02 request or messaging session == `credentialSubject.id`. **Consume the challenge only after this check passes**, so a different DID cannot burn the legitimate challenge.
4. **Credential proof**: resolve the issuer DID. The key is in the issuer's `assertionMethod`. Issuer ≠ holder.
5. **Validity**: `validFrom <= now + s` and `now < validUntil + s`, with s ≤ 60 s.
6. **Status**
   - Fetch `statusListCredential` under SSRF controls and verify its proof.
   - **Its issuer must equal the credential issuer.** It must have `validUntil` and be within validity.
   - Check `statusPurpose`, the index and the bit. Reject if revoked or suspended.
   - **Reject if status is unavailable.**
   - Cache status for ≤ 300 s.
7. **Issuer authority**: the issuer DID must be bound to a local account, admitted under a documented new-customer policy, or a trusted org for that resource type.
   - The credential cannot establish this. Issuing authority MUST NOT be derived from credentials or tokens the issuer holds, so **no redelegation**.
   - For role credentials, the issuer must be the org the verifier will treat as principal. Policy may require an org-identity VC (format undefined).
   - A did:web domain proves domain control only.
8. **Permission intersection**: authority = local policy ∩ credential ∩ stored request.
   - Delegation: exact `resource` match, and actions ⊆ the entry's `actions`.
   - Role: the operation falls within one `capabilities[].action` under the correspondence.
   - Every constraint must be understood and enforceable.
   - In `operation` mode, evaluate the stored operation. In `session` mode, evaluate bounds and enforceability.
9. **Record**: credential `id`, issuer, holder, status entry, accepted permissions, verification time and the local principal.

**Direct presentation flow (11.6)**
1. The requester authenticates its DID via ANP-02 HTTP or an authenticated messaging session.
2. The verifier returns an `ANPPresentationRequest` and stores the transaction. The stored transaction holds: requester DID, profile, credential_types, domain, resource, actions, mode, expiry, and the pending operation for `operation` mode. Required request fields:
   - `type`
   - `profile`, which must exactly match `anp.authorization.vc.v1-draft2`
   - `challenge`: ≥128-bit random, single-use, ≤300 s
   - `domain`: HTTPS origin or the verifier DID
   - `credential_types`: non-empty
   - `resource` and `actions`
   - `mode`: `operation` or `session`
3. The holder checks that the profile matches exactly. **No silent downgrade.** It checks that its credential type is in `credential_types`, then signs the VP.
4. The verifier loads the transaction by challenge and confirms the currently authenticated DID is the transaction's requester. It runs 11.4.
   - `operation`: perform or reject **only** the stored operation.
   - `session`: may create a bounded context.
   - The verifier MUST NOT widen `operation` into a session.

```json
{
  "type": "ANPPresentationRequest",
  "profile": "anp.authorization.vc.v1-draft2",
  "challenge": "JP-0hfyItrCTHObnXV3Svg",
  "domain": "https://supplier.example",
  "expires_at": 1790467500,
  "credential_types": ["ANPAgentDelegationCredential"],
  "mode": "operation",
  "resource": "https://supplier.example/api/orders",
  "actions": ["orders.create"]
}
```

Example VP containing a delegation credential:

```json
{
  "@context": ["https://www.w3.org/ns/credentials/v2"],
  "type": ["VerifiablePresentation"],
  "holder": "did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28",
  "verifiableCredential": [{
    "@context": ["https://www.w3.org/ns/credentials/v2", "https://agent-network-protocol.com/contexts/authorization/v1"],
    "id": "urn:uuid:cdf2506e-b40d-4124-934b-7a9711fe5331",
    "type": ["VerifiableCredential", "ANPAgentDelegationCredential"],
    "issuer": "did:wba:corp.example:issuer:e1_jp0UC2iDyHyfM23uwWm480i4fC9QwHPTzQoVvdXgR1Y",
    "validFrom": "2026-09-20T00:00:00Z",
    "validUntil": "2026-10-20T00:00:00Z",
    "credentialSubject": {
      "id": "did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28",
      "permissions": [{
        "resource": "https://supplier.example/api/orders",
        "actions": ["orders.create"],
        "constraints": { "perOperationLimit": { "value": "5000.00", "currency": "CNY" } }
      }]
    },
    "credentialStatus": {
      "id": "https://corp.example/credentials/status/3#94567",
      "type": "BitstringStatusListEntry",
      "statusPurpose": "revocation",
      "statusListIndex": "94567",
      "statusListCredential": "https://corp.example/credentials/status/3"
    },
    "proof": { "type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022", "created": "2026-09-20T00:00:00Z",
               "verificationMethod": "did:wba:corp.example:issuer:e1_jp0UC2iDyHyfM23uwWm480i4fC9QwHPTzQoVvdXgR1Y#assert-1",
               "proofPurpose": "assertionMethod", "proofValue": "ISSUER_PROOF_VALUE_PLACEHOLDER" }
  }],
  "proof": { "type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022", "created": "2026-09-27T00:00:00Z",
             "verificationMethod": "did:wba:agents.example:agent-a:e1_RfdmtK_McXAgc6fbIC55GcOjXyXGPWixGhrDaiLsv28#auth-1",
             "proofPurpose": "authentication", "domain": "https://supplier.example",
             "challenge": "JP-0hfyItrCTHObnXV3Svg", "proofValue": "HOLDER_PROOF_VALUE_PLACEHOLDER" }
}
```

Role credential example (HR Agent):

```json
{
  "@context": ["https://www.w3.org/ns/credentials/v2", "https://agent-network-protocol.com/contexts/authorization/v1"],
  "id": "urn:uuid:0b6f2d7e-3c41-4a8e-9f05-6d2a7c1e8b34",
  "type": ["VerifiableCredential", "ANPAgentRoleCredential"],
  "issuer": "did:wba:corp.example:issuer:e1_jp0UC2iDyHyfM23uwWm480i4fC9QwHPTzQoVvdXgR1Y",
  "validFrom": "2026-09-01T00:00:00Z",
  "validUntil": "2026-12-01T00:00:00Z",
  "credentialSubject": {
    "id": "did:wba:agents.example:hr-agent:e1_lYz_0-T5hDXHzkvmtNREe5P3VJuNJHVuGVDsLNAr7ZE",
    "role": "Recruiting agent",
    "capabilities": [
      { "action": "https://vocab.example/hr#publishJobPosting" },
      { "action": "https://vocab.example/hr#scheduleInterview" },
      { "action": "https://vocab.example/hr#queryApplicationStatus" }
    ]
  },
  "credentialStatus": { "id": "https://corp.example/credentials/status/3#94568", "type": "BitstringStatusListEntry",
                        "statusPurpose": "revocation", "statusListIndex": "94568",
                        "statusListCredential": "https://corp.example/credentials/status/3" },
  "proof": { "type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022", "created": "2026-09-01T00:00:00Z",
             "verificationMethod": "did:wba:corp.example:issuer:e1_jp0UC2iDyHyfM23uwWm480i4fC9QwHPTzQoVvdXgR1Y#assert-1",
             "proofPurpose": "assertionMethod", "proofValue": "ISSUER_PROOF_VALUE_PLACEHOLDER" }
}
```

Carrier and session rules:
- **No new HTTP auth scheme and no `Authorization` header** for VP transport. The carrying interface's ANP-07 description defines where the request and VP travel. The interface declares VC capability in ANP-07.
- One-time challenge use does not make the business operation idempotent. Retries and dedup belong to the application protocol.
- **Session mode** requirements:
  - Retain: local principal, holder DID, profile, credential type, resource, accepted actions and entries with constraints, credential id, issuer, proof key reference, validity, status refs and a **fixed** expiry.
  - Every later request MUST re-authenticate as the bound holder. The session reference only selects the context and is not identity evidence.
  - Re-evaluate permissions and constraints on **every operation** against its actual parameters (amount, currency, target).
  - The expiry has a finite local maximum and is ≤ `validUntil`. It MUST NOT slide. Renewal needs a fresh challenge and VP.
  - Recheck status periodically. Stop on revocation, suspension or expiry, an inactive issuer/holder DID, or removal of the issuer key from `assertionMethod`.
  - The session reference is not an OAuth token. No wire format is defined.

**Lifecycle and privacy (11.7)**
- Revocation is via the status bit plus republishing. The status-list validity should be short and republished before expiry.
- When the issuer removes a key from `assertionMethod`, credentials signed with it fail and must be reissued.
- Rotating the Agent's auth key keeps credentials valid, because they bind the DID.
- **When the Agent DID changes (including did:wba binding-key rotation), credentials must be reissued.**
- Role changes or Agent retirement: revoke immediately (SHOULD). Role credentials should be short-lived.
- Privacy:
  - The verifier sees the whole credential, so issue a separate credential per verifier when privacy matters.
  - Status-list fetches reveal the verifier's IP to the status-list host.
  - Do not log full VPs; log only the credential `id` and the result.

### 2.11 Key, identity and grant lifecycle (§10)

- For e1_, keep the fingerprint-binding key for document control and use a **separate runtime authentication key** for assertions (SHOULD). The runtime key goes into JWKS and `anp_oauth_keys`.
- Runtime-key rotation with the same DID and URL is **not** a new client.
  - Update the DID `authentication`, `anp_oauth_keys`, JWKS and digest coherently. Inconsistent intermediate states fail closed.
  - Removing a key blocks assertions once the verifier observes it, even for assertions whose `iat` predates removal.
- Ordinary CIMD AS: removing a key only from the DID is not enough. The publisher MUST also remove it from JWKS and use the AS's client/grant controls.
- Identity-change table:

| Change | Treatment |
|---|---|
| Runtime key rotation (same DID + URL) | Revalidate. Retain grants per AS policy. |
| Same DID, new CIMD URL | **New OAuth client.** No automatic transfer of records, codes, refresh tokens or grants. |
| Same URL, new DID (including WBA successor) | Enhanced AS MUST invalidate the old binding and require explicit rebind or admission. No silent inheritance via Handle, `stableSubjectId` or unverified `successorDid`. |
| Compromise | Disable the client/binding, block issuance and refresh, revoke per policy. |

- DID or JWKS key revocation does **not** revoke issued tokens. Deployments MUST document expiry, revocation and invalidation latency.
- RFC 7009 and 7662 MAY be used, each with its own auth policy.
- Revoking a grant MUST block issuance and refresh under it. Revocation at one service doesn't deactivate the DID elsewhere.
- No automatic DID/URL grant-migration protocol. ANP-03's HTTP 409 successor hint is **not** an OAuth error.

### 2.12 Errors (§12)

OAuth Profile: use OAuth errors only. Never return ANP-02 `DIDWba` challenges, a `did_superseded` payload, or an invented DID grant type from the token endpoint.

| Condition | Error |
|---|---|
| Missing fields, duplicate security params, multiple auth methods | `invalid_request` |
| Discovery/admission/binding fail, bad assertion, DID/key/claim/alg/time, replay | `invalid_client`. An unknown URL is not a failure when first contact is enabled, but a required DID binding must still validate. |
| Client not permitted for the grant | `unauthorized_client` |
| Bad, expired, used, revoked or mis-bound code or refresh token | `invalid_grant` |
| Unknown grant type | `unsupported_grant_type` |
| Bad scope | `invalid_scope` |
| Bad target | `invalid_target` (RFC 8707) |
| User denies | `access_denied` (authorization endpoint) |
| Metadata/JWKS/resolver/replay-store outage | Fail closed. HTTP 503 with no token is permitted. |

- Token errors normally use HTTP 400 with the RFC 6749 §5.2 JSON format.
- `invalid_client` descriptions SHOULD be generic.
- RS errors follow Bearer/DPoP rules.
- VC errors are defined by the carrying interface. Any failed check MUST reject, and errors should not reveal which step failed. **No new OAuth error codes.**
- Never redirect an invalid authorization request to an unapproved URI.

### 2.13 Security and privacy (§13), condensed

- **SSRF:** CIMD, JWKS, DID, context and status-list fetches are SSRF boundaries.
  - Restrict schemes and destinations. Block loopback, link-local, private, cloud-metadata and IPv6 equivalents.
  - **No CIMD redirects.** Validate every hop for other fetches.
  - Enforce time, size, redirect and recursion limits. Prevent DNS rebinding.
  - CIMD draft-02 §8.6 overrides the general exception: **no special-use IP fetches in production**. The only exception is dev/test where the AS itself is on the same loopback interface.
- Bind issuer, client, resource and transaction. Use anti-mix-up and CSRF protection. Assertion claims, NL instructions, Agent Descriptions and DID services cannot override these bindings.
- **Deterministic server-side policy, never LLM inference.**
- Separate long-lived DID control keys from runtime keys. Never copy a human's key or token to an Agent.
- DID signatures don't attest software integrity, human presence or intent.
- Correlation risk from stable DID/URL: disclose identifier use and minimize claims and logs.
- VC issuer trust is scoped by credential type **and** resource. Natural-language text in credentials isn't authority.

### 2.14 Validation scenarios (docs/anp-05-validation-guide.md)

- Informative. IDs are stable evidence references, not an ordered list.
- **Retired:** 03, 19, 24, 25, 28, 34–40, 51, 52, 58.
- Numbering history: 41+ added in v0.4. 51+ are VC (61–64 role credentials). 65–75 are direct presentation (added v0.6). **76–83** are new CIMD/binding scenarios in v0.7.
- Evidence must record: protocol revision, selected mode (`cimd`/`did_bound`), AS capabilities and policy choices (algorithm, aud/typ, redirect, resource, mix-up defense), and unsupported optional features ("record, don't report as pass").

Grouped:
- **Happy paths:** 01/02 (did_bound client credentials, per DID method), 04 (authorization code + PKCE keeps the user subject), 29 (first contact without a registration API), 42 (loopback with ephemeral port), 44 (runtime-key rotation keeps grants), 47 (two-resource isolation), 61 (role credential accepted), 65 (positive direct presentation), 75 (personal data with an independent basis), 76 (plain `cimd` with no ANP extensions).
- **Assertion/crypto:** 05 (bad sig, `none`/`HS*`, curve), 06 (key not in `authentication`/`anp_oauth_keys`, wrong `id`, JWS-injected key; `kid` ≠ authorization), 07 (client_id/iss/sub/fetch-URL mismatch; aud/typ outside policy), 08 (time bounds, `nbf`), 09 (jti replay across keys/replicas), 16 (duplicate params), 45 (typ/aud pinned, no weaker retry), 49 (algorithms outside policy; cimd doesn't need Ed25519).
- **Binding/metadata:** 18, 31 (redirected/oversized/duplicate-field CIMD; missing `ANPCIMD`, backlink or digest), 32 (pending code aborted on metadata change), 41 (tampered metadata without a digest update), 77 (exact same HTTPS string; no 3xx repair), 78 (copied victim key / self-asserted `anp_did`), 79 (`anp_oauth_keys` vs actual JWKS key), 80 (`jwks_uri` digest covers only the URI; both `jwks` and `jwks_uri` → reject), 81 (≤300 s freshness), 82 (no fallback to `cimd`; no opt-out), 83 (new URL = new client).
- **Grant/flow:** 10, 11, 15, 21 (RFC 9207 iss), 22 (resource binding), 23 (A→B token forwarding), 26 (public client ≠ confidential), 27 (scope challenge), 30 (admission disabled; cache eviction), 33 (metadata scopes ≠ grants), 43 (loopback ≠ AS fetch), 46 (client_id = URL, sub = user), 48 (high-risk approval), 50 (no roadmap claims).
- **Transport/SSRF/tokens:** 12, 13, 14 (assertion or ANP-02 token as resource token), 17 (DPoP downgrade), 20 (metadata mismatch).
- **VC:** 53 (proof/key relationship/context), 54 (validity/status/status-list issuer/`validUntil`), 55 (issuer authority, self-issue), 56 (intersection/constraints/currency), 57 (challenge/domain/DID/op/mode), 59 (raw VC as Bearer or at the token endpoint), 60 (redelegation rejected), 62–64 (role mapping/limit/org trust/personal data), 66 (challenge single-use and concurrency), 67 (revocation stops sessions), 68 (5000 CNY limit), 69 (profile negotiation), 70 (type substitution), 71 (session reference ≠ identity), 72 (per-op checks in a session), 73 (session expiry/renewal), 74 (qualification credential alone).

### 2.15 Conformance gates (§14)

- **OAuth client:** DID→CIMD publication/discovery, URL id + JWKS, §6 assertions, trusted AS/capability selection, a declared grant and token handling.
- **Ordinary AS:** CIMD + selected OAuth features only. No ANP resolver required.
- **`did_bound` AS:** enforce the advertised extension, method/URL/digest/actual-key validation, bounded freshness, replay protection and lifecycle.
- **RS:** token validation + real policy enforcement.
- **Report the mode achieved.** Ordinary interoperability ≠ AS-verified DID.
- **VC holder:** 11.3 VP + 11.6 profile check. **VC verifier:** 11.6 + the full 11.4 order (+ session rules if used). **Issuer** conformance covers only format, proof and status-list publication. OAuth and VC conformance are independent.
- **Experimental claim:** one complete implementation + negative-test evidence, labeled experimental.
- **Stable v1 claim:** two independently developed client/AS implementations, cross-tests, RS tests, CIMD interop without ANP extensions, first-contact + restricted admission, metadata/JWKS updates, callback modes, key/URL lifecycle, multi-resource isolation and a security review. `did_bound` additionally needs tamper, key-substitution, digest, lifecycle and downgrade evidence. VC needs holder↔verifier cross-tests. Spec text and doc tests alone are insufficient.

### 2.16 W3C-proposal documents (context only, superseded)

`standard/W3C-proposal/DID-OAuth-Compatibility Discussion.md` and `DID-OAuth-Integration-Solution.md` describe an **earlier, different design**:
- DID-auth acts as an OIDC IdP that verifies VPs and issues an **ID Token with `vc_claims`**.
- The Agent then uses **RFC 8693 token exchange** (or simulates an authorization-code flow via `POST /authorize` with a VP) to get an access token with **RAR `authorization_details`** (`anp.social_graph_discovery`, `anp.resource_access`, …) and DPoP binding.
- It uses ad-hoc `grant_type: "vp_token"`, `Ed25519Signature2020` proofs, VC DM 1.1 and pre-registered client_ids.

ANP-05 v0.7 **explicitly rejects** most of this for v1:
- no VC→token exchange (removed in v0.6)
- no invented DID grant types
- RAR and RFC 8693 are only roadmap items
- CIMD URL clients replace pre-registration

Shared ideas: DID enhances authn/client identity, RS stays standard OAuth, DPoP is recommended, and the A2A (native DID/VC) vs A2R (OAuth) split resembles the v0.7 VC-vs-OAuth split. **Do not implement the W3C-proposal wire formats as ANP-05.**

---

## 3. Consolidated MUST / MUST NOT checklist by role

### 3.1 Handle Provider (ANP-04, released)
- [ ] Serve `GET https://{domain}/.well-known/handle/{local}` over HTTPS with a valid TLS certificate. Return `application/json`.
- [ ] Return `handle`, `did`, `status` (`active`/`suspended`/`revoked`) and `binding_generation` (positive decimal string).
- [ ] Strictly increase `binding_generation` on **any** DID or status change. Never roll back or reuse a value. Persist it across Provider migration.
- [ ] Keep the Handle domain equal to the DID hostname (ignoring the DID port).
- [ ] Bind exactly one DID per Handle. Keep the local-part unique per domain.
- [ ] Enforce the syntax: `[a-z0-9-]`, 1–63 chars, no leading or trailing `-`, no `--`. Normalize to lowercase. No port in the domain.
- [ ] Never transfer or reallocate a Handle. On revocation keep a **permanent tombstone** and return 410 (or `status: revoked`). No ordinary, recovery or admin flow may reassign it.
- [ ] Rebind to a new DID only for the **same subject** after independent recovery or identity verification.
- [ ] Provider migration keeps the same Handle and domain, inherits the max generation, history and tombstones. Any redirect `Location` must verify under the input Handle domain.
- [ ] If `profile` is returned: `profile.subject_did == did`, and `profile.handle`, if present, `== handle`.
- [ ] (SHOULD) `Cache-Control` + `ETag`. Rate limiting. `429` + `Retry-After`. Lower TTL during rotation or migration. Publish reserved words. Normalize error bodies. No sensitive data.
- [ ] (MAY) `/.well-known/handle/by-did?did=…` returning `{did, confirmed:true, …}` without `handle`. Note: reserve the local-part `by-did`.

### 3.2 DID holder / publisher (ANP-04 + ANP-05)
- [ ] Publish `ANPHandleService` with an absolute HTTPS `serviceEndpoint` under the Handle domain. Public mode uses the exact `/.well-known/handle/{local}` (SHOULD); private mode uses the by-did URL (MAY).
- [ ] Update `ANPHandleService` after Provider migration (SHOULD) and in rotated DID Documents.
- [ ] Publish exactly one `ANPCIMD` service: `id` = DID#fragment, `serviceEndpoint` = the exact CIMD URL.
- [ ] For did_bound: `anp_oauth_keys` (non-empty, distinct, ⊆ `authentication`) and `anp_metadata_sha256` (lowercase hex over the exact served bytes). Recompute the digest on **any** byte change.
- [ ] CIMD: HTTPS with a path, no query, userinfo, fragment or dot segments. `client_id` = its own URL. Non-empty `client_name`. Exactly one of `jwks` or `jwks_uri`. Public keys only. No secrets. 200 + JSON with no redirect.
- [ ] Never use a DID as `client_id`.

### 3.3 Client / Agent (ANP-04 verifier role + ANP-05 OAuth client + VC holder)
WNS verifier:
- [ ] Strip `wba://` if you accept it. Lowercase. Validate the syntax.
- [ ] Resolve the DID Document per ANP-03 or ANP-02-Web. Never infer endpoints or keys from the Handle.
- [ ] Run the bidirectional verification before authn, authz, IM recipient resolution or state-changing calls. Require **`exact-handle`** where a specific Handle matters. `provider-confirmed` is insufficient.
- [ ] Re-verify after 301/308 redirects and after DID rotation. Never accept a binding from a redirect alone.
- [ ] Ignore a mismatched `profile`. Never use profile fields for routing, authn, authz, E2EE or endpoint selection. Invalidate profile cache on DID change.
- [ ] Don't treat DIDs as the same subject based on Handle or prefix. Use the ANP-03 `successorDid` and proof chain.

OAuth client:
- [ ] Pin issuer, `client_id` URL, mode, auth policy, assertion `aud`/`typ`, resource-binding mechanism and mix-up defense **before** starting. Never fall back from `did_bound` to `cimd`, change `client_id`, or weaken authentication after a failure.
- [ ] Validate the RFC 9728 resource ↔ AS association and the exact RFC 8414 issuer before sending credentials.
- [ ] Assertion: `iss = sub = client_id` URL, one exact `aud`, integer `iat`/`exp` with `0 < exp−iat ≤ 300`, `jti` ≥128-bit random and never reused. Asymmetric algorithm only. Keep it out of URLs and logs.
- [ ] Authorization code: S256 PKCE, fresh session-bound `state`, exact redirect, RFC 9207 `iss` check (mandatory for did_bound) or a preselected mix-up defense. Bind callbacks, including errors, to the transaction record.
- [ ] Loopback: `127.0.0.1`/`[::1]` only, explicit port, listener opened before the browser and bound to loopback only, no embedded webview. Redeem with the exact same redirect.
- [ ] One resource per token. Cache tokens by (issuer, tenant, user, client_id, resource, scopes, mode, sender key). Never select a token by DID.
- [ ] Never forward an inbound token downstream. Get a separate token per target.
- [ ] Bounded retries on `insufficient_scope`. Never silently switch to client credentials.
- [ ] Don't claim user delegation if only client credentials are implemented.

VC holder:
- [ ] Check that `profile` exactly matches `anp.authorization.vc.v1-draft2`. No downgrade.
- [ ] Check the credential type is in `credential_types`.
- [ ] Check `domain` equals the HTTPS origin you called or the authenticated peer DID. Never sign a VP for another verifier.
- [ ] Put exactly one authorization credential in the VP. Proof purpose is `authentication` with your `authentication` key. Include `domain`, `challenge` and `created`.
- [ ] Never forward a VP. Never send a VC/VP as Bearer or to a token endpoint. Never self-issue or re-delegate.

### 3.4 Authorization server
- [ ] Use OAuth 2.0 + RFC 9700. No implicit grant, ROPC, PKCE `plain` or tokens in URLs.
- [ ] Use the CIMD URL as `client_id`. Compare by exact string. Don't follow redirects when fetching CIMD. Reject error or invalid responses. Apply the CIMD draft-02 §8.6 SSRF rules: no special-use IPs in production, DNS-rebinding protection, size and time limits.
- [ ] Check the admission policy before any fetch. A cache miss doesn't clear a block. Rate-limit and bound unauthenticated work.
- [ ] Verify a fresh assertion at `/token`: signature with an accepted key, exact `iss`/`sub`, pinned `aud`, time bounds. Reject `jwk`/`jku`/`x5u`/`x5c` header keys, `none` and `HS*`.
- [ ] Independently validate the grant, resource owner, target and scopes. Client auth alone never issues a token. Never copy the assertion `sub` into a user token.
- [ ] Atomically consume codes, bound to client, redirect, PKCE, resource and transaction.
- [ ] Refresh: same client, fresh assertion, same target, no scope increase, rotation with reuse detection (or sender-constrained). No refresh for client credentials.
- [ ] Token response: `access_token`, `token_type`, `expires_in`, `scope`, `Cache-Control: no-store`, `Pragma: no-cache`. Finite lifetime. JWT tokens follow RFC 9068 with `client_id` = URL.
- [ ] Scope records, grants and caches by (issuer, tenant, client_id).
- [ ] Use OAuth error codes only (§12). Fail closed with 503 on dependency outage.
- [ ] Retain the user-delegated grant record fields listed in §1.3 of the spec.
- [ ] Document token expiry, revocation and invalidation latency.

If advertising `anp_cimd_binding` (did_bound):
- [ ] Enforce it for **every** CIMD client at those endpoints. No opt-out. Use separate issuer/endpoints for plain CIMD.
- [ ] Candidate DID from trusted state or the `anp_did` hint only, never from the JWT header. Method-validate it (did:wba e1_/bare-domain with proof, no k1_; did:web per ANP-02).
- [ ] Exactly one `ANPCIMD` with `serviceEndpoint == client_id`. Digest equals SHA-256 of the exact bytes. Actual verification key ∈ `anp_oauth_keys` ∩ `authentication`, compared by key material or thumbprint.
- [ ] Support Ed25519 in addition to RS256. Enforce skew ≤60 s and the `nbf` rules.
- [ ] Replay store on (issuer, client_id, jti) until exp+skew. Atomic, cross-replica, fails closed.
- [ ] Freshness ≤300 s for DID, CIMD and key material. Revalidate when stale. Immediately invalidate on known deactivation or removal.
- [ ] Require RFC 9207 and RFC 8707 (explicit `resource` on every request).
- [ ] On a DID change at the same URL, invalidate the binding and require an explicit rebind. Never inherit grants.

### 3.5 Resource server / VC verifier
OAuth RS:
- [ ] Validate trusted AS, validity, revocation/status, audience = this resource, scope and business policy on **every operation**.
- [ ] Never accept: client assertions, ANP-02 cache tokens, tokens for other audiences, raw VC/VP as Bearer.
- [ ] Get the client identity only from trusted token or introspection state. Never infer a verified DID from `anp_did`, `kid` or a URL. Refuse DID-dependent decisions without trusted evidence.
- [ ] `401` with `resource_metadata` (SHOULD) when there's no token. `403 insufficient_scope` for missing permissions.
- [ ] If DPoP is required: RFC 9449 (`ath`, `cnf.jkt`) and no Bearer downgrade.
- [ ] High-risk operations: verify the exact operation approval (one-time, expiry) or reject. Login, scope, DID signature or DPoP never substitute.
- [ ] Deterministic server-side policy only.

VC verifier [v0.6-recovered]:
- [ ] Requester authenticated via ANP-02 or messaging first. Store the presentation transaction (requester DID, profile, credential_types, domain, resource, actions, mode, expiry, pending operation). The challenge is ≥128-bit and expires in ≤300 s.
- [ ] Run the 11.4 order: size ≥16 KiB support, allowlisted contexts, `eddsa-jcs-2022` → VP proof/domain/challenge/created (±300 s, skew ≤60 s) → holder == authenticated DID == `credentialSubject.id` → **then** consume the challenge → issuer proof in `assertionMethod`, issuer ≠ holder → validity → status list (same issuer, has `validUntil`, fail closed, cache ≤300 s) → issuer authority via local binding or trust policy → permission intersection, rejecting unknown constraints → record.
- [ ] Never widen `operation` into a session. Sessions: fixed non-sliding expiry ≤ `validUntil`, re-authenticate the holder on every request, re-check every operation, periodic status rechecks, stop on revocation.
- [ ] Reject redelegation, self-issued credentials, role-name-only authorization and unmapped action URIs. Reject currency mismatches or undocumented amounts.
- [ ] Never mint an OAuth token from a VC. Never let a VC bypass an OAuth-only interface.
- [ ] Log only the credential `id` and the result, not full VPs.

---

## 4. Released vs draft — what to treat as stable today

| Document | Status | Treat as |
|---|---|---|
| ANP-04 WNS v1.2 | **Released** (part of ANP 1.2) | **Stable.** Implement fully: Handle syntax, `/.well-known/handle/{local}`, Resolution Document incl. `binding_generation`, status values, HTTP codes, `ANPHandleService` bidirectional verification with `exact-handle`/`provider-confirmed`/`unverified`, permanence/tombstones, migration and rotation rules. |
| Appendix B (did:web) v1.2 | **Released** | Stable. The B.4 domain-only Handle check is a weaker, separate result. |
| ANP-02, ANP-03, Appendix A | Released v1.2 | Stable dependencies (ANP-03 owns `e1_`/`k1_` and `successorDid`; ANP-02 owns the Web binding). |
| ANP-05 v0.7 | **Draft / not released**, outside ANP 1.2 | **Experimental.** Profile strings end in `-draft1`/`-draft2`. The repo says publication "does not establish SDK, AS or product support". Stable v1 needs two independent interoperable implementations plus a security review (§14). |
| ANP-05 VC Profile §11 | Draft. **Body missing at HEAD**; last full text is v0.6 (`63a99ddf72`) | Experimental, and the normative text is currently not in the published document. |
| Validation guide | Informative | Use as a test plan. No results are recorded. |
| W3C-proposal docs | Proposal/discussion | Historical context only. Superseded design. |

**Pragmatic guidance (Note):**
- **Build WNS to production grade now.** It is released and self-contained.
- For ANP-05, the low-risk "stable today" subset is plain standards: OAuth 2.0 + RFC 9700 + RFC 7523 `private_key_jwt` + RFC 7636 S256 + RFC 8707 + RFC 9207 + RFC 9728/8414 + RFC 9068/7662 + optional RFC 9449.
  - That subset is what `cimd` mode is, with the CIMD draft-02 dependency (an IETF draft, still moving).
  - Publishing an `ANPCIMD` service + CIMD + JWKS from the DID is cheap and harmless.
- Treat the following as experimental and feature-flagged, and expect wire changes:
  - `did_bound` (`anp_cimd_binding`, `anp_oauth_keys`, `anp_metadata_sha256`, `anp_did`)
  - the VC Profile (`ANPAgentDelegationCredential`, `ANPAgentRoleCredential`, `ANPPresentationRequest`, the `https://agent-network-protocol.com/contexts/authorization/v1` context, which is not yet published or fixed)
- Pin exact Profile identifiers. On a revision change, revalidate metadata and pending transactions. A changed `client_id` is a new client.
- The VC context URL is not published or fixed, and §11 is missing. Interop with other VC implementations is therefore not achievable from the spec alone today.

---

## 5. Ambiguities and open questions

**ANP-05**
- **Q1 (blocking for VC).** v0.7 §11 body is empty in HEAD and upstream main. Upstream commit `6683793dc1` deleted 364 lines, and the repo's own tests fail (38 of 103 tests fail, mostly VC). Is this intentional (VC moving elsewhere) or accidental? The rest of v0.7 still normatively references §11.2–11.9. Confirm with maintainers before building the VC verifier.
- **Q2.** The VC context `https://agent-network-protocol.com/contexts/authorization/v1` is not published or fixed, so the allowlist content is unknown. `eddsa-jcs-2022` doesn't need RDF expansion, but the allowlist check needs a stable URL and content.
- **Q3.** How does an RS learn that a token was issued under `did_bound` with a verified DID? There is no claim (§3: "no new token claim is mandated"), so a deployment-specific trusted channel or extension is needed. Interop gap for RSs that want DID-based policy.
- Q3a. Section 9 uses `typ=JWT`, but rfc7523bis's `client-authentication+jwt` is only "when supported". Pick per AS and record it (AUTHZ-45).
- Q3b. `aud` = issuer vs token-endpoint URL is AS-specific with no discovery signal. It must come from configuration.
- Q3c. VC 11.3 says `created` must be "within 300 seconds of the verifier's current time". Is that past-only, or also future? Skew ≤60 s is given, but the direction is unstated.
- Q3d. Session-mode wire format, session-reference format, and how the presentation request/VP are carried are all delegated to the ANP-07 interface description. That means no interop without a profile of ANP-07.
- Q3e. The DID-bound freshness cap of 300 s versus HTTP caching headers on CIMD/JWKS: the stricter one wins, but it's unclear whether the AS must refetch the CIMD on every token request after 300 s, even under load. Effectively yes.
- Q3f. An org-identity credential format for role-credential issuers is "not defined". Verifier onboarding policy is entirely out of band.

**ANP-04**
- **Q4.** IDN/punycode handling of the domain part is unspecified (only "valid FQDN, RFC 1035"). It is also unspecified whether trailing dots (`alice.example.com.`) are allowed or stripped.
- **Q5.** The `by-did` path segment collides with a possible local-part `by-did` (valid syntax). It is not in the reserved-word list.
- **Q6.** No explicit verifier MUST to persist and enforce the highest seen `binding_generation`. Only the Provider obligation and the stated purpose exist. Recommend implementing it, and decide the policy when a lower generation is seen (reject, alert).
- **Q7.** `suspended` has no HTTP code mapping (404? 200 with status?). The §6 verification algorithm doesn't check `status`.
- **Q8.** Whether one DID may be bound to multiple Handles (in the same or different domains) isn't stated. "One-to-one correspondence" in §4.4 implies no, but there's no explicit rule. Private by-did confirmation assumes the Provider can answer per DID.
- **Q9.** URI comparison for step 7 ("exactly the same") has no normalization rules: trailing slash, default port `:443`, percent-encoding of the local-part, host case.
- **Q10.** Multiple `ANPHandleService` entries in one DID Document (several Handles, or both public and private modes) aren't addressed.
- **Q11.** Squatting disputes vs permanence: the spec mandates non-transferable and never-reused Handles, yet suggests "dispute resolution processes". Remedies can only be revocation plus tombstone, never reassignment. Trademark or legal reassignment is impossible under the protocol commitment.
- **Q12.** ABNF requires ≥2 characters, but the prose and examples allow 1. The ABNF doesn't encode the `--` ban.
- **Q13.** The error body schema (`error`, `message`) and codes beyond `handle_not_found` are not enumerated. No `Content-Type` is specified for error bodies (presumably JSON).
- **Q14.** No SSRF or fetch-limit guidance in ANP-04 for dereferencing `ANPHandleService.serviceEndpoint`. The hostname must equal the Handle domain, which limits the risk, but the domain can resolve to private IPs.
- **Q15.** `ttl` absent: no default. `profile.proof` cryptosuite: the example uses `eddsa-jcs-2022`, but no MUST-support suite is named.
- **Q16.** Appendix B did:web compatibility returns a result that is neither `exact-handle` nor `provider-confirmed`, and it has no name. Implementations need their own label and policy for whether it is acceptable for security-sensitive operations. The ANP-04 header implies it is not equivalent.
