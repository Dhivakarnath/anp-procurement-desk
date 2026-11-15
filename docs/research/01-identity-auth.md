# ANP 1.2 Identity and Authentication Layer: Implementation Notes

Sources (all read in full, repo at `/tmp/anp-research/AgentNetworkProtocol`, HEAD `0837cfd`; vectors generated from `b7ba3ff8`):

- `02-anp-did-authentication-protocol-specification.md` (ANP-02, Status: Released, v1.2), 521 lines
- `03-did-wba-method-design-specification.md` (ANP-03, Status: Released, v1.2), 664 lines
- `appendix-a-did-wba-k1-compatibility-extension.md` (Released, v1.2)
- `appendix-b-compatibility-with-native-did-web.md` (Released, v1.2)
- `examples/did-authentication-vnext/{README.md, manifest.json, identities.json, byte-vectors.json, scenario-vectors.json}`
- `docs/did-wba-server-test-interface.md` (legacy, see §8)
- Cross-checked: `scripts/anp02-vector-utils.mjs` (reference helpers used to generate vectors), `message/02-identity-and-discovery.md` §4.1.1–4.2

Key words: MUST / SHOULD / MAY per BCP 14 (ANP-02 §1). Section references below are to the spec's own numbering.

I independently re-verified the vectors with Python `cryptography` 50.0.0 (no Node 22 available locally):

- All E1 DIDs' `e1_` fingerprints match the RFC 7638 thumbprint of the `proof.verificationMethod` key.
- All `Content-Digest` values equal `sha-256=:base64(SHA-256(payload bytes)):`.
- All HTTP/JSON request signatures verify as Ed25519 over the UTF-8 signature base (64-byte signatures).
- All `DOCUMENT-*` E1 proofs verify under `eddsa-jcs-2022` with `hashData = SHA-256(JCS(proofConfig incl. @context)) || SHA-256(JCS(document without proof))`.

---

## 0. Layering (who owns what)

ANP-02 is DID-method-independent. It owns: HTTP request signatures (RFC 9421), body digests (RFC 9530), authentication-key authorization (`authentication` relationship), challenges/errors, optional access tokens, and JSON carriage of the same fields.

The DID method owns: identifier syntax, resolution, Document validation, identity binding, lifecycle (update/deactivate/continuity).

| DID method | Identity-material validation | Request authentication |
|---|---|---|
| `did:wba` | ANP-03 (+ Appendix A for `k1_`) | ANP-02 Ch. 3 and 4 |
| `did:web` | native did:web spec + ANP-02 Appendix B rules (+ repo Appendix B) | ANP-02 Ch. 3 and 4 |
| `did:webvh` | Informative only (ANP-02 App. C); "does not define an immediately enabled WebVH binding" | n/a |
| others | Informative (ANP-02 App. D) | n/a |

Server-side flow is therefore: parse `keyid` -> method-specific resolve+validate -> common checks (VM exists, in `authentication`) -> RFC 9421/9530 verification -> time window -> replay -> authorization (separate) -> optional token.

ANP-02 §1: ordinary HTTP APIs may adopt this authentication without implementing ANP Messaging, WNS, or a device Manifest. Authentication alone does not imply business authority.

---

## 1. did:wba identifiers (ANP-03 §2.1–2.2.3)

### 1.1 Method name and forms

- Prefix `did:wba` (lowercase, MUST per DID Core).
- Method-specific id = FQDN protected by TLS, optionally followed by colon-separated path segments.
- MUST NOT contain IP addresses (reject IPv4/IPv6 literals).
- Port allowed; the host:port colon MUST be percent-encoded as `%3A` (e.g. `example.com%3A3000`).
- Path separators are `:` (instead of `/`).

Two forms:

1. **Root / naked-domain DID** `did:wba:{domain}` → identifies the whole domain subject or a domain-level service identity. Use for cross-domain service-to-service HTTP authentication. `ANPMessageService.serviceDid` SHOULD prefer the naked-domain DID. No `e1_` binding rules apply. Request authentication is NOT relaxed: digest, coverage, `authentication` purpose, time, and replay all still apply (ANP-03 §2.2 "How to use naked domain name DID" item 5).
2. **Path DID**: identifies a user/agent/sub-identity. For newly created path DIDs the last segment MUST be `e1_<fingerprint>` (ANP-03 §2.2.1). Parsers MAY support historical path DIDs without fingerprint segment; new ones SHOULD use the default scheme.

ABNF (ANP-03 §2.2):

```abnf
base64url-char = ALPHA / DIGIT / "-" / "_"
path-segment   = 1*(ALPHA / DIGIT / "-" / "_" / ".")
e1-fingerprint = "e1_" 43base64url-char

wba-root-did = "did:wba:" domain-name
wba-path-did = "did:wba:" domain-name 1*(":" path-segment) ":" e1-fingerprint
wba-did      = wba-root-did / wba-path-did
```

Appendix A extension:

```abnf
k1-fingerprint = "k1_" 43base64url-char
wba-k1-path-did = "did:wba:" domain-name 1*(":" path-segment) ":" k1-fingerprint
```

Notes on the ABNF (see §8 ambiguities): `domain-name` is not defined in-line (refers to RFC 1035/1123/2181), the `%3A` port is not in the ABNF, and a path DID requires at least one namespace segment before the fingerprint (`did:wba:example.com:e1_...` does not match `wba-path-did`).

Examples:

```text
did:wba:example.com
did:wba:example.com:user:alice:e1_<fingerprint>
did:wba:example.com%3A3000:user:alice:e1_<fingerprint>
did:wba:identity-wba.example:api:api-wba:e1_TzEBgIcHmLjwuFomfsQSV6cifXvw-DW5MpIl4Q2I6ik   (vector)
```

### 1.2 TLS identity binding of the identifier

ANP-03 §2.2: the method-specific identifier must match the server certificate per modern TLS service-identity rules (RFC 9525). Matching MUST use `dNSName` in `subjectAltName`; implementations MUST NOT rely on the certificate CN.

### 1.3 Resolution URL rules (ANP-03 §2.5.1 / §2.5.2)

Algorithm ("must be performed"):

1. Take the method-specific identifier; replace `:` with `/` to get FQDN + optional path.
2. If the domain contains a port, percent-decode the colon (`%3A` → `:`).
3. Prepend `https://`.
4. If no path, append `/.well-known`.
5. Append `/did.json`.
6. HTTP GET over HTTPS with security per did:web §2.6.
7. Verify the resolved Document `id` matches the DID being resolved (exact string).
8. Apply method/profile validation (E1 proof binding etc., §2 below).
9. DNS: clients should use DoH (RFC 8484) to avoid tracking.

Mappings:

```text
did:wba:example.com
  -> https://example.com/.well-known/did.json
did:wba:example.com:user:alice:e1_<fp>
  -> https://example.com/user/alice/e1_<fp>/did.json
did:wba:example.com%3A3000:user:alice:e1_<fp>
  -> https://example.com:3000/user/alice/e1_<fp>/did.json
```

Implementation hardening (scenario vectors `RESOLUTION-*`, illustrative policy):

- Certificate must match the DID host (`RESOLUTION-*-TLS-IDENTITY` → reject).
- Do not follow redirects to disallowed/internal addresses (SSRF) (`REDIRECT-INTERNAL`).
- Never forward origin credentials across origins on redirect (`REDIRECT-CREDENTIAL`). ANP-02 §7.3: avoid unconditional following of untrusted cross-origin redirects.
- Bound response size before parsing (`RESPONSE-BUDGET`).
- Do not commit partial trust to cache when evidence is invalid (`PARTIAL-VALIDATION-CACHE`).
- Reject path segments `.` / `..` (the ABNF allows `.` characters, which would otherwise allow URL path traversal; not stated in spec, my recommendation).

### 1.4 `e1_` fingerprint profile (ANP-03 §2.2.2), exact algorithm

Binding key requirements (MUST): Ed25519 public key; represented as `Multikey` with `publicKeyMultibase`; authorized by `authentication`.

1. `publicKeyMultibase` is multibase base58-btc (`z` prefix) of the Ed25519 Multikey. Decode base58btc → bytes `0xED 0x01 || pk32` (multicodec ed25519-pub varint prefix; the spec says "After decoding, the original 32 bytes of the Ed25519 public key are obtained", meaning after stripping the 2-byte multicodec prefix; verified in vectors: decoded length 34, prefix `ed01`).
2. Build the RFC 7638 required-member JWK: `{"crv":"Ed25519","kty":"OKP","x":"<base64url-nopad(pk32)>"}`.
3. RFC 7638 serialization: only required members, lexicographic member order (`crv`, `kty`, `x`), no whitespace, UTF-8.
4. `digest = SHA-256(utf8_bytes)` (32 bytes).
5. `fp = base64url(digest)` without `=` padding → always 43 chars.
6. Path segment = `"e1_" + fp`. The prefix is not hashed.

Recommendation (non-normative): use the thumbprint (without `e1_`) as the VM fragment/`kid`. The vectors do not do this; they use `#root`.

Verified example (from vectors):

```text
publicKeyMultibase  z6MkoHgciEnM1XCKwYmF4fdsDyukxwpXtyihKaCw8jD3YhEg
x                   g0UoJP1oc-BCiT8pJa8lfekejLLEzPjheYJBn4jj8TE
thumbprint input    {"crv":"Ed25519","kty":"OKP","x":"g0UoJP1oc-BCiT8pJa8lfekejLLEzPjheYJBn4jj8TE"}
e1 segment          e1_TzEBgIcHmLjwuFomfsQSV6cifXvw-DW5MpIl4Q2I6ik
```

Python reference used to check:

```python
raw = b58decode(mb[1:]); assert raw[:2] == b'\xed\x01'
x = b64url_nopad(raw[2:])
tp = '{"crv":"Ed25519","kty":"OKP","x":"%s"}' % x
fp = b64url_nopad(sha256(tp.encode()).digest())   # 43 chars
```

### 1.5 `k1_` profile (Appendix A; non-default, opt-in)

Binding key: secp256k1, represented as `publicKeyJwk` (NOT Multikey), in `authentication`. Thumbprint input: `{"crv":"secp256k1","kty":"EC","x":"...","y":"..."}` (RFC 7638 order `crv`,`kty`,`x`,`y`) → SHA-256 → base64url nopad (43 chars) → `k1_` prefix. Recommended VM shape:

```json
{
  "id": "did:wba:example.com:user:alice:k1_<fingerprint>#key-1",
  "type": "EcdsaSecp256k1VerificationKey2019",
  "controller": "did:wba:example.com:user:alice:k1_<fingerprint>",
  "publicKeyJwk": { "crv": "secp256k1", "kty": "EC", "x": "...", "y": "...", "kid": "<fingerprint>" }
}
```

(`kid` is not part of the RFC 7638 thumbprint input.) Details in §5.

### 1.6 Stable subject path (ANP-03 §1.2, §2.2.3)

Definition: the domain name plus every path segment before the final binding-fingerprint segment. `did:wba:example.com:user:alice:e1_<fp>` → `example.com:user:alice`.

- It is not a DID and cannot be resolved independently.
- Once assigned to a continuing subject it MUST NOT be modified, recycled, or reassigned.
- On root binding-key change, old and new DIDs MUST have identical stable subject paths.
- A verifier MUST NOT conclude same-subject from equal stable subject paths alone, and MUST NOT merge DIDs by stripping the last segment (ANP-03 §7).
- Continuity MUST be verified via the old document's `successorDid`, its document-wide `proof`, and the new DID's binding fingerprint (ANP-03 §2.5.2–2.5.5; see §4 here).

---

## 2. DID Document (ANP-03 §2.4–2.5.5)

### 2.1 Document processing (ANP-03 §2.4)

`did.json` is likely served as `application/json`.

1. If `@context` is at the root → process per JSON-LD; if processing fails → reject as a did:wba document.
2. If `@context` processes and includes `https://www.w3.org/ns/did/v1` → process per DID Core §6.3.2 (JSON-LD consumption).
3. If no `@context` → plain JSON per DID Core §6.2.2.
4. References to external resources, external DIDs, or `serviceEndpoint` MUST be absolute URIs (prevents key-obfuscation attacks).
5. Internal VM references MAY be relative DID URLs (`#key-1`); the parser MUST expand them against the document root DID.

Note: E1 documents MUST carry `@context` (they need data-integrity/v2 and multikey/v1), so item 3 only applies to non-E1 profiles in practice. Full JSON-LD expansion is not needed for the `eddsa-jcs-2022` proof itself (JCS-based), but rule 1 says a document whose `@context` can't be JSON-LD-processed should be rejected. Most implementations will pin/allowlist known context URLs rather than fetch them (my recommendation, not spec text).

### 2.2 Recommended E1 path DID Document (verbatim from ANP-03 §2.5)

```json
{
  "@context": [
    "https://www.w3.org/ns/did/v1",
    "https://w3id.org/security/data-integrity/v2",
    "https://w3id.org/security/multikey/v1",
    "https://w3id.org/security/suites/x25519-2019/v1"
  ],
  "id": "did:wba:example.com%3A8800:user:alice:e1_<fingerprint>",
  "verificationMethod": [
    {
      "id": "did:wba:example.com%3A8800:user:alice:e1_<fingerprint>#key-1",
      "type": "Multikey",
      "controller": "did:wba:example.com%3A8800:user:alice:e1_<fingerprint>",
      "publicKeyMultibase": "z6Mk..."
    },
    {
      "id": "did:wba:example.com%3A8800:user:alice:e1_<fingerprint>#key-x25519-1",
      "type": "X25519KeyAgreementKey2019",
      "controller": "did:wba:example.com%3A8800:user:alice:e1_<fingerprint>",
      "publicKeyMultibase": "z9hFgmPVfmBZwRvFEyniQDBkz9LmV7gDEqytWyGZLmDXE"
    }
  ],
  "authentication": ["did:wba:example.com%3A8800:user:alice:e1_<fingerprint>#key-1"],
  "assertionMethod": ["did:wba:example.com%3A8800:user:alice:e1_<fingerprint>#key-1"],
  "keyAgreement": ["did:wba:example.com%3A8800:user:alice:e1_<fingerprint>#key-x25519-1"],
  "service": [
    { "id": "...#ad", "type": "AgentDescription",
      "serviceEndpoint": "https://agent-network-protocol.com/agents/example/ad.json" },
    { "id": "...#handle", "type": "ANPHandleService",
      "serviceEndpoint": "https://example.com/.well-known/handle/alice" },
    { "id": "...#anp", "type": "ANPMessageService",
      "serviceEndpoint": "https://example.com/anp",
      "serviceDid": "did:wba:example.com%3A8800" }
  ],
  "proof": {
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "created": "2025-01-01T00:00:00Z",
    "verificationMethod": "did:wba:example.com%3A8800:user:alice:e1_<fingerprint>#key-1",
    "proofPurpose": "assertionMethod",
    "proofValue": "z..."
  }
}
```

(Service `id`s abbreviated here; in the spec they are full DID URLs.)

### 2.3 Field requirements

| Field | Status | Rules |
|---|---|---|
| `@context` | required | MUST include `https://www.w3.org/ns/did/v1`. E1 docs using the standard Ed25519 proof also require `https://w3id.org/security/data-integrity/v2` and `https://w3id.org/security/multikey/v1`. Add others (`x25519-2019/v1`, `jws-2020/v1`) as needed. |
| `id` | required | No IP; port as `%3A`; colon-separated path; new path DIDs MUST end in `e1_<fp>`. MUST equal the resolved DID. |
| `verificationMethod` | required | Array. E1 path DIDs: at least one Ed25519 `Multikey` binding key whose RFC 7638 thumbprint equals the `e1_` segment. Subfields `id`, `type`, `controller`, `publicKeyJwk` or `publicKeyMultibase`. |
| `authentication` | required | Strings or embedded objects. E1 binding key MUST be in it. Cross-platform auth should prefer signing with the binding key. |
| `assertionMethod` | optional | For E1 with standard proof, the key that generates `proof` MUST be authorized by `assertionMethod`. |
| `keyAgreement` | optional | X25519 (`X25519KeyAgreementKey2019` or equivalent). Absence means no E2EE capability. Key separation recommended (signing keys never used for KA and vice versa). |
| `service` | optional | See 2.5. (Messaging P2 §4.2 makes `service` MUST for DIDs that are actively discovered/interacted with.) |
| `alsoKnownAs` | optional | New DID MAY reference direct predecessor. Reverse claim only, not proof of continuity. |
| `deactivated` | optional, did:wba extension | `true` = this complete DID is no longer used for new authentication or routing; document stays available for historical verification and successor lookup. |
| `successorDid` | optional, did:wba extension | MUST be a complete DID string (not a DID URL) pointing to the direct successor. MUST NOT skip intermediates or be rewritten later. |
| `proof` | required for active E1; optional/profile-defined otherwise | `DataIntegrityProof` + `eddsa-jcs-2022`. |

Messaging P2 (`message/02-identity-and-discovery.md` §4.2) adds for ANP messaging use: `id` MUST; `authentication` MUST for any DID appearing as business originator; `assertionMethod` SHOULD if declarative signature objects are used; `keyAgreement` SHOULD if an encryption overlay is supported; `deviceManifest` MUST if a device-addressed E2EE profile is advertised. Not required for ordinary API authentication.

### 2.4 Verification method types seen in the spec and vectors

| Type | Key repr. | Use |
|---|---|---|
| `Multikey` (Ed25519, `z6Mk...`, multicodec `0xed01`) | `publicKeyMultibase` | E1 binding key; authentication; assertion; recommended. |
| `Multikey` (X25519, `z6LS...`, multicodec `0xec01`) | `publicKeyMultibase` | keyAgreement (vectors use this for device KA keys). |
| `X25519KeyAgreementKey2019` | `publicKeyMultibase` | keyAgreement (spec example). |
| `JsonWebKey2020` (OKP/Ed25519) | `publicKeyJwk` | Allowed as an additional `authentication` key (vector `#auth-jwk`, needs `jws-2020/v1` context). |
| `EcdsaSecp256k1VerificationKey2019` | `publicKeyJwk` (EC/secp256k1) | `k1_` binding key (Appendix A). |

ANP-02 §3.1.2/§3.2.2: Ed25519 Multikey → Ed25519, 64-byte signature. "Other algorithms are defined by corresponding verification method types." The `alg` parameter is not required; the verifier infers the algorithm from the VM type.

### 2.5 Service types (ANP-03 §2.5 `service`)

- `AgentDescription`: `serviceEndpoint` → ANP-07 Agent Description document.
- `ANPHandleService`: WNS bidirectional binding. `serviceEndpoint` MUST be a dereferenceable absolute HTTPS URI under the Handle Provider's domain.
  - Disclosed handle: SHOULD be the handle's Resolution Endpoint, e.g. `https://example.com/.well-known/handle/alice`.
  - Undisclosed: MAY be a DID Confirmation Endpoint, e.g. `https://example.com/.well-known/handle/by-did?did=...`, returning at least `did` and `confirmed = true`.
  - If the returned doc contains `handle` exactly equal to the input handle → exact reverse verification.
  - Confirmation-only result proves only the provider relationship; it MUST NOT be treated as proof that a specific handle is bound.
- `ANPMessageService`: single unified messaging endpoint (`serviceEndpoint` MAY point there). For cross-domain service-to-service calls SHOULD include `serviceDid` = a DID string (not DID URL) whose key verifies the outer HTTP signature; for did:wba normally a naked-domain DID (`did:wba:example.com` or `did:wba:example.com%3A8800`). Vectors add `profiles: [...]` and `securityProfiles: ["transport-protected","direct-e2ee","group-e2ee"]` (defined by messaging profiles, out of scope here).

Appendix B.6: when federation authenticates a service, it resolves and verifies `serviceDid` independently of the Agent DID, under that service DID's own method. Naming somebody else's endpoint grants no hosting authority.

### 2.6 DID Document proof, E1 profile (ANP-03 §2.5.5)

MUST conform to W3C VC Data Integrity 1.0 and Data Integrity EdDSA Cryptosuites v1.0 (`eddsa-jcs-2022`). Upstream W3C spec wins on conflict.

Proof fields:

| Field | Req. | Value |
|---|---|---|
| `type` | required | `DataIntegrityProof` |
| `cryptosuite` | required | `eddsa-jcs-2022` |
| `created` | required | XML Schema dateTime |
| `verificationMethod` | required | full DID URL of the Ed25519 `Multikey` used |
| `proofPurpose` | required | `assertionMethod` |
| `proofValue` | required | multibase base58-btc (`z...`) of the 64-byte Ed25519 signature |
| `domain`, `challenge` | optional | |

Constraints:

1. Active E1: `proof.verificationMethod` MUST be the `e1_` binding key.
2. Parser MUST recompute RFC 7638 thumbprint of the key at `proof.verificationMethod` and compare to the `e1_` segment. Do NOT pick an arbitrary Ed25519 key from `authentication` (ANP-03 §3.1.2).
3. Key MUST be in `assertionMethod` (Field table + §2.5 "assertionMethod").
4. Active E1 with missing proof, failing proof, or proof key whose thumbprint mismatches → resolution MUST fail. No relaxed mode for active E1, and local policy switches cannot disable it.

`eddsa-jcs-2022` algorithm as implemented by the vector generator (`scripts/anp02-vector-utils.mjs` `proofParts`/`withProof`), which matches W3C:

```text
unsecured   = document minus top-level "proof"
proofConfig = proof minus "proofValue", plus "@context" = unsecured["@context"] (if present)
hashData    = SHA-256(JCS(proofConfig)) || SHA-256(JCS(unsecured))     // 64 bytes
signature   = Ed25519.sign(sk, hashData)                                // 64 bytes
proofValue  = "z" + base58btc(signature)
```

Vector `DOCUMENT-api-wba` gives `proof_config_jcs`, `document_jcs`, `hash_data_hex` (`c041fad4...cf7d72d5`) for byte-exact testing. The `@context` copy into proof config is required: the vector's `proof_config_jcs` begins with `{"@context":[...],"created":...`.

Non-E1 profiles: if local policy enables proof verification and a `proof` exists, verify per that profile. Relaxed mode (missing proof OK) or strict mode (missing proof = failure) by local policy. Bare-domain DIDs: only `id` consistency, no E1 binding (vector `service-wba` has no proof).

### 2.7 Resolver validation steps (consolidated)

For `did:wba`:

1. Syntax check (ABNF; no IP; `%3A` port; known profile suffix `e1_`/`k1_` or root; optionally legacy unprefixed path).
2. Build URL (§1.3); HTTPS GET with SAN `dNSName` matching, CA validation, redirect policy, size budget, DoH recommended.
3. Parse JSON; JSON-LD/context handling (§2.1); absolute URI rules; expand relative refs.
4. `doc.id == did` exactly, else fail (scenario error `invalid_did`).
5. If `e1_` and not `deactivated: true`: proof present; `type`/`cryptosuite`/`proofPurpose` exact; VM at `proof.verificationMethod` exists, is Ed25519 Multikey, is in `assertionMethod`; Data Integrity signature verifies; RFC 7638 thumbprint of that key == `e1_` segment; binding key also in `authentication`.
6. If `e1_` and `deactivated: true`: transition rules (§4). No new authentication.
7. If `k1_`: Appendix A rules (§5.2).
8. Reject ambiguous VM ids (duplicate `id`, no first/last fallback: scenario `AUTH-*-AMBIGUOUS-KID`).
9. Only then cache the result.

### 2.8 Caching

The spec says little about document caching. What it does say:

- ANP-03 §2.6: clients SHOULD cache only successor edges with assurance `verified` or `recovery_verified`. `provider_asserted` and `unverified` edges MUST NOT enter the verified-edge cache. Validation failures before cache commit (invalid final proof, cycle, hop limit) MUST NOT leave prefix edges. Disagreement between a cached verified edge and a newly observed `successorDid`, a cycle, or a stable-subject-path mismatch → MUST reject the migration and report the conflict.
- ANP-02 §7.2: replay cache retention should be longer than signature expiry.
- Scenario policy (illustrative): `AUTH-*-RESOLUTION-TEMPORARY` → temporary resolver failure rejects with `invalid_did` but MUST NOT cache as deactivated; `WEB-KEY-UPDATE-STALE-CACHE` → when the host removes an auth key, a retry with the old key is rejected and the key cache invalidated; `AUTH-web-DOCUMENT-REMOVED` → no stale-cache fallback; `AUTH-wba-DEACTIVATED` → `refresh_required: true`, reject with `invalid_did`.
- No TTL, `Cache-Control` handling, or negative-cache rules are specified. Choose a short TTL and honour HTTP caching headers; refetch on signature failure with a cached key (my recommendation).

### 2.9 HTTPS/TLS requirements

- HTTPS MUST be used (ANP-02 §7.3); client MUST strictly validate the peer CA chain.
- Service identity MUST match `dNSName` in `subjectAltName`, not CN (ANP-02 §7.3; ANP-03 §2.2; RFC 9525).
- DID resolution should use DoH (RFC 8484) (ANP-02 §7.3 "should"; ANP-03 §2.5.2 "should").
- Avoid unconditionally following untrusted cross-origin redirects.
- ANP-03 §3.2: a transparent 301/302 should not replace successor verification.
- Inherit did:web §2.6 security & privacy considerations.

---

## 3. ANP-02 HTTP request authentication

### 3.1 Headers on the initial request (ANP-02 §3.1.1)

- Clients MUST send `Signature-Input` and `Signature` (RFC 9421).
- With a message body, clients MUST also send `Content-Digest` (RFC 9530).
- Minimum covered components: `@method`, `@target-uri`, and `content-digest` when a body exists.
- Recommended additional components: `@authority`, `content-type`, `content-length`.

`Signature-Input` parameters:

| Param | Requirement | Notes |
|---|---|---|
| `keyid` | MUST | Complete DID URL pointing at a VM in the DID Document (e.g. `did:web:identity.example:alice#key-1`). A bare fragment is not acceptable. |
| `created` | MUST | Unix seconds (RFC 9421 integer). |
| `expires` | SHOULD | Unix seconds. |
| `nonce` | MAY | If the server issued a challenge `nonce`, the client MUST use it. |
| `alg` | not required | Verifier determines algorithm from VM type. If present and inconsistent/unsupported → scenario maps to `invalid_verification_method`. |
| `tag` | not mentioned | ANP-02 does not define a `tag` value. |

Label: examples always use `sig1`. The spec does not fix the label; replay detection must not depend on it (`AUTH-*-NONCELESS-REPLAY-LABEL`).

Spec example:

```http
POST /orders HTTP/1.1
Host: api.example.com
Content-Type: application/json
Content-Digest: sha-256=:BASE64_SHA256_DIGEST:
Signature-Input: sig1=("@method" "@target-uri" "@authority" "content-digest");created=1733402096;expires=1733402156;nonce="abc123";keyid="did:web:identity.example:alice#key-1"
Signature: sig1=:BASE64_SIGNATURE:
```

Byte-exact vector `HTTP-wba-POST` (Ed25519, verified):

```text
method      POST
target-uri  https://api.example/orders
body        {"action":"create","orderId":"12345"}
Content-Digest: sha-256=:7R4Jg2ES+xDfzB2yYbqCL5I1eG0sbY0S/N0WiXAafJM=:
Signature-Input: sig1=("@method" "@target-uri" "content-digest");created=1788768000;expires=1788768060;nonce="HTTP-wba-POST";keyid="did:wba:identity-wba.example:api:api-wba:e1_TzEBgIcHmLjwuFomfsQSV6cifXvw-DW5MpIl4Q2I6ik#root"
Signature: sig1=:ocOgNmIyxOHwFqhhCci39qRhh4tVjSrSKBJhDR4LxWLZZ3xm4p5lEqHKgZGI9rduWzxdmxIIzPUKR66iANVWAw==:

signature base (UTF-8, LF separated, no trailing newline):
"@method": POST
"@target-uri": https://api.example/orders
"content-digest": sha-256=:7R4Jg2ES+xDfzB2yYbqCL5I1eG0sbY0S/N0WiXAafJM=:
"@signature-params": ("@method" "@target-uri" "content-digest");created=1788768000;expires=1788768060;nonce="HTTP-wba-POST";keyid="did:wba:identity-wba.example:api:api-wba:e1_TzEBgIcHmLjwuFomfsQSV6cifXvw-DW5MpIl4Q2I6ik#root"
```

Parameter order in vectors: `created;expires;nonce;keyid`. RFC 9421 signs the exact serialized `@signature-params`, so the verifier must use the received serialization verbatim, not re-serialize.

`Content-Digest` (RFC 9530): `sha-256=:<standard base64 with padding of SHA-256(body bytes)>:` (structured-field byte sequence). Vectors use only `sha-256`. RFC 9530 also allows `sha-512`; ANP-02 does not restrict algorithms. The digest is over the exact transmitted content bytes. A single appended space must fail (`AUTH-*-HTTP-JSON-WHITESPACE`).

### 3.2 Client signing procedure (ANP-02 §3.1.2)

1. If there's a body: compute `Content-Digest` (RFC 9530).
2. Choose the VM under method rules and local policy. For `did:wba` E1 the client SHOULD use the `e1_` binding key by default (ANP-03 §3.1.1). For `k1_`, the secp256k1 binding key (App. A.6). Other `authentication` keys are allowed only if the server's local policy accepts them (vectors: `allow_nonbinding_authentication_keys: true`).
3. Build `Signature-Input` covering at least `@method`, `@target-uri` (+ `content-digest` if body), with `created`, `expires`, `nonce` (server-supplied if challenged), and `keyid`.
4. Build the RFC 9421 signature base.
5. Sign with the private key (Ed25519 → 64 bytes; secp256k1 → ECDSA-SHA256, fixed 64-byte `r||s`).
6. Send `Signature-Input`, `Signature`, and `Content-Digest` if applicable.

### 3.3 Server verification (ANP-02 §3.2.1 + §3.2.2 + method bindings), consolidated step-by-step

ANP-02's ordering, with the method rules and vector policy merged in:

1. **Format**: `Signature-Input` and `Signature` present; if body present, `Content-Digest` present. Parse as RFC 8941 structured fields; select the signature label (spec doesn't say what to do with multiple labels; pick the one whose `keyid` is a DID URL, or require exactly one). Missing/garbled → 401 `invalid_request`. Missing digest with body → `invalid_request` (`AUTH-*-MISSING-DIGEST`).
2. **Coverage policy**: the covered component list MUST include `@method`, `@target-uri`, and (if body) `content-digest`. Missing `@target-uri` → `invalid_request` (`AUTH-*-UNCOVERED-TARGET`). `created` MUST be present. `keyid` MUST be a full DID URL.
3. **Body integrity**: recompute digest over the received body bytes; compare to `Content-Digest`. Mismatch → `invalid_content_digest`.
4. **Parse `keyid`** → DID + fragment. Unsupported/disabled DID method → `invalid_did` (`AUTH-UNSUPPORTED-DID-METHOD`, `AUTH-*-DISABLED-METHOD`, `WEBVH-DESIGN-NOT-ENABLED` "no implicit web fallback").
5. **Resolve and validate the DID Document** under the method (§2.7 for WBA; Appendix B for did:web). Failure/`id` mismatch/E1 proof failure → `invalid_did`. WBA: if `deactivated: true` → MUST NOT continue with new authentication; if `successorDid` present the server should return `409 did_superseded` (§4.4).
6. **Binding/authorization of the key**: VM for `keyid` exists (else `invalid_verification_method`); VM is referenced by `authentication` (else `invalid_verification_method`; an `assertionMethod`-only key is rejected, `AUTH-*-ASSERTION-ONLY`); method binding checks (k1: thumbprint of `keyid` VM == `k1_` segment, App. A.6). Ambiguous duplicate VM ids → reject.
7. **Signature**: rebuild the signature base from the actual request per RFC 9421, using the received `@signature-params` string; choose the algorithm from the VM type (Ed25519 Multikey/JWK OKP → Ed25519 64-byte; secp256k1 → ECDSA P-256K/SHA-256 `r||s`); verify. Fail → `invalid_signature`. Note `@target-uri` must be reconstructed as the client saw it (scheme+authority+path+query). Behind TLS-terminating proxies you need trusted `Forwarded`/`X-Forwarded-*` or a configured external base URL.
8. **Time window**: check `created` / `expires`. Recommended window 1–5 minutes, configurable. Reject future `created` beyond skew and passed `expires` → `invalid_timestamp`. Vectors: `created=1788768000`, `expires=+60`, verifier time `1788768030`, skew 0; clock `1788768200` = expired, `1788767800` = future.
9. **Replay**:
   - "Direct connection proof profile" (client-chosen nonce): short-term replay cache keyed on `(keyid, nonce)` or an equivalent key. ANP-02 §7.2 also mentions `(keyid, jti)`. Replay → `invalid_nonce`.
   - "Challenge profile": server-issued nonce MUST be single-use. Wrong nonce → `invalid_nonce`.
   - Nonce-less requests (allowed, `nonce` is MAY): vectors still expect the second identical request to be rejected (`AUTH-*-NONCELESS-REPLAY`). So key the replay cache on something like `(keyid, signature bytes)` or a hash of the covered signed statement, independent of the label (`-LABEL` scenario).
   - Concurrency: at most one of two concurrent identical requests may succeed (`AUTH-*-CONCURRENT-REPLAY`). Use an atomic insert-if-absent.
   - Only consume a challenge nonce after the signature verifies (`AUTH-*-INVALID-SIGNATURE-NONCE`: a bad-signature request must not burn the issued nonce).
   - Retention: longer than the signature validity window (§7.2).
10. **Authorization (separate from authentication)**: does this DID have permission for the resource? No → `403 Forbidden`, `forbidden_did`.
11. **Result**: success → proceed (optionally issue a token); otherwise `401 Unauthorized` + challenge.

(ANP-02 orders "digest" before "resolve", and "signature coverage" after "binding". The order is not normative. A sensible production order checks cheap things first: format → coverage → time → digest → resolve → key → signature → replay insert → authorization. That keeps signature-unverified requests out of the replay cache and avoids remote fetches for stale requests.)

### 3.4 Access tokens (ANP-02 §3.2.3), optional

- Server MAY issue a token after successful verification. JWT (RFC 7519) recommended; the generation details are "for reference only".
- Server MUST return it in the `Authentication-Info` response header, NOT in an `Authorization` response header.

```http
Authentication-Info: access_token="eyJhbGciOi...", token_type="Bearer", expires_in=3600, scope="orders.read orders.write"
```

- Payload example (spec, verbatim; note ISO date strings, not NumericDate; see §8):

```json
{ "sub": "did:web:identity.example:alice", "iat": "2024-12-05T12:34:56Z", "exp": "2024-12-06T12:34:56Z", "scope": "orders.read orders.write" }
```

- Client sends `Authorization: Bearer <access_token>` in subsequent requests. If `token_type` ≠ `Bearer`, the client MUST follow the corresponding extension spec.
- Server verifies signature, expiry, payload fields per RFC 7519. Failure → `invalid_access_token`.
- Sender-constrained tokens recommended (`cnf` or equivalent, proof per request, distinct `token_type`) but not yet profiled; `Bearer` is the default for compatibility.
- MUST store tokens properly and set a reasonable expiry; SHOULD only return tokens over HTTPS via `Authentication-Info`; IP/User-Agent only as auxiliary risk signals, never sole binding (§7.4).
- Vector token policy (illustrative): JWT with `iss`, `aud` (resource URL), `sub` (DID), `scope`, `iat`/`exp` as NumericDate; wrong issuer/audience/expired → `invalid_access_token`; insufficient scope → `forbidden_did` (authenticated-but-forbidden). Tokens are optional: `TOKEN-*-OPTIONAL` expects `accepted-without-token`.

### 3.5 Errors and challenges (ANP-02 §3.2.4)

401 when: signature fails, digest fails, signature expired, replay risk, or server wants a re-sign with its nonce. A server MAY 401 the very first request just to issue a nonce (challenge profile).

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: DIDWba realm="api.example.com", error="invalid_signature", error_description="Signature verification failed.", nonce="xyz987"
Accept-Signature: sig1=("@method" "@target-uri" "@authority" "content-digest");created;expires;nonce;keyid
Cache-Control: no-store
```

`WWW-Authenticate` scheme name: `DIDWba`. Params:

- `realm` (optional)
- `error` (required), one of:
  - `invalid_request`: malformed, missing required fields, unsupported params
  - `invalid_nonce`: used, invalid, or not matching the challenge
  - `invalid_timestamp`: out of range
  - `invalid_did`: bad DID format or document not found
  - `invalid_signature`: signature verification failed
  - `invalid_verification_method`: no public key for `keyid`
  - `invalid_content_digest`: digest mismatch
  - `invalid_access_token`: token verification failed
  - `forbidden_did`: no permission (used with 403)
- `error_description` (optional)
- `nonce` (optional): if present, client MUST re-sign with it; else client may generate a new local nonce and retry.

`Accept-Signature` (RFC 9421 §5.1) MAY indicate the components/params expected next time.

Both client and server MUST bound retries (spec: "need to limit the number of retries") to avoid loops.

403: authenticated but not authorized (`forbidden_did`).

JSON mirrors (for HTTP the headers remain authoritative):

```json
{ "code": 401, "error": "invalid_nonce", "error_description": "Nonce has already been used. Please provide a new nonce.", "nonce": "1234567890" }
{ "code": 403, "error": "forbidden_did", "error_description": "did not have permission to access the resource." }
```

Method-specific responses (§3.2.4.3): WBA defines `409 Conflict` `did_superseded` (§4.4 here).

### 3.6 JSON (non-header) carriage (ANP-02 §4)

For cases where metadata and payload can be separated (HTTP body envelope, WebSocket first frame, bus envelope, RPC wrapper). Not applicable to pure JSON transports that cannot separate the two. It does not define a new signed-field set.

```json
{
  "auth": {
    "contentDigest": "sha-256=:BASE64_SHA256_DIGEST:",
    "signatureInput": "sig1=(\"@method\" \"@target-uri\" \"@authority\" \"content-digest\");created=1733402096;expires=1733402156;nonce=\"abc123\";keyid=\"did:web:identity.example:alice#key-1\"",
    "signature": "sig1=:BASE64_SIGNATURE:"
  },
  "payload": { "orderId": "12345", "action": "create" }
}
```

Rules:

- `auth.contentDigest` ↔ `Content-Digest`, `auth.signatureInput` ↔ `Signature-Input`, `auth.signature` ↔ `Signature`.
- `contentDigest` covers only `payload`, not `auth` or the envelope.
- If `payload` is a JSON object, fix serialization locally; RFC 8785 JCS recommended. Vector `JSON-wba-POST`: payload digest is over `JCS(payload)` = `{"action":"create","orderId":"12345"}` (same digest `7R4Jg2…` as the HTTP vector; signature differs only by nonce).
- Over HTTP, `@method`/`@target-uri` keep their HTTP meaning. Over non-HTTP, the application protocol MUST define equivalent components (`JSON-*-UNBOUND-TRANSPORT`: a WebSocket frame without a defined binding is rejected, "no-authenticated-component-source").
- Do not apply the payload-only digest as the HTTP `Content-Digest` of the full body (`JSON-*-WRONG-BOUNDARY` → `invalid_content_digest`).
- Server: extract the three fields from `auth`, verify the digest against `payload` only, and otherwise follow §3.3. Over HTTP return tokens via `Authentication-Info`. Non-HTTP token return is undefined (left to the upper layer).
- Messaging P1 "ORIGIN" signatures use a different target mapping (`@method: direct.send`, `@target-uri: anp://agent/<pct-encoded DID>`) and are not interchangeable with HTTP or JSON-carriage signatures.

### 3.7 Authentication vs. authorization (ANP-02 §5)

- No `humanAuthorization` field in DID Documents. Human-confirmation requirements belong to upper-layer policy (e.g. Agent Description `authorizationLevel: normal` | `user-presence-required`).
- The user agent performs local confirmation first, then signs with a policy-permitted `authentication` key. The server checks the policy, not "a human signed this".

### 3.8 Privacy (ANP-02 §6)

Multi-DID strategy (master DID + scenario sub-DIDs, rotate/deactivate periodically). Use name services (WNS/Handle) for stable human-readable names.

---

## 4. DID transitions, key rotation, identity continuity (ANP-03 §2.5.3–2.5.5, §2.6, §3.2, §7)

There is no separate "transition document" format. The superseded DID's own DID Document, with `deactivated: true` and `successorDid`, is the transition record. The chain is followed hop by hop.

### 4.1 Update without DID change

Same `e1_` binding key → same DID. Other contents may change: add/revoke other keys, change services. Re-sign `proof` with the binding key (it covers the whole document).

### 4.2 Binding-key rotation (DID changes), publisher rules (§2.5.3)

1. New DID MUST have exactly the same stable subject path.
2. Publish new DID Document. It MAY list the predecessor in `alsoKnownAs`. It is signed by the new binding key.
3. Old DID Document MUST remain retrievable with `deactivated: true` and `successorDid: <new DID>`. It MUST NOT be removed (§2.5.4).
4. `successorDid` MUST point to the direct successor only. Earlier documents' `successorDid` MUST NOT be rewritten on later rotations.
5. Old document's document-wide `proof` should cover `deactivated`, `successorDid`, everything else.
6. Update WNS/Handle too; the name mapping does not replace the migration proof.
7. Implementations SHOULD do an atomic compare-and-swap on the current complete DID (e.g. `expected_current_did`) to prevent forks (multiple successors), not on the stable subject path.

Permanent deactivation without successor: `did.json` may be removed or made unavailable.

Example old-document shape (my construction from the rules; spec gives no full example):

```json
{
  "@context": ["https://www.w3.org/ns/did/v1","https://w3id.org/security/data-integrity/v2","https://w3id.org/security/multikey/v1"],
  "id": "did:wba:example.com:user:alice:e1_<old-fp>",
  "verificationMethod": [{ "id": "did:wba:example.com:user:alice:e1_<old-fp>#key-1", "type": "Multikey", "controller": "did:wba:example.com:user:alice:e1_<old-fp>", "publicKeyMultibase": "z6Mk...old" }],
  "authentication": ["did:wba:example.com:user:alice:e1_<old-fp>#key-1"],
  "assertionMethod": ["did:wba:example.com:user:alice:e1_<old-fp>#key-1"],
  "deactivated": true,
  "successorDid": "did:wba:example.com:user:alice:e1_<new-fp>",
  "proof": { "type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022", "created": "...", "verificationMethod": "did:wba:example.com:user:alice:e1_<old-fp>#key-1", "proofPurpose": "assertionMethod", "proofValue": "z..." }
}
```

### 4.3 Verifying a hop (deactivated E1 document), §2.5.2 + §2.5.5

For each deactivated `e1_` document:

1. MUST still find a VM whose RFC 7638 thumbprint matches the DID's `e1_` segment (the original binding key).
2. If `successorDid` is present: MUST check old and new DIDs have the same stable subject path.
3. If a top-level `proof` is present it MUST verify as one of:
   - **old-binding proof**: signed by the original binding key (thumbprint == `e1_` segment) → hop assurance `verified`;
   - **recovery proof**: signed by a key that a *trusted pre-deactivation document* (already held by the verifier) authorized in `assertionMethod` → `recovery_verified`. The recovery key need not match the fingerprint, and MUST NOT be a key introduced only at deactivation.
   - A present but malformed, unauthorized, or invalid proof MUST invalidate the transition. It MUST NOT be downgraded to `provider_asserted` or `unverified` (`TRANSITION-WBA-INVALID-PROOF`).
4. If no `proof`:
   - standalone hop verifier MUST report `unverified`;
   - a complete-chain resolver MAY report `provider_asserted` only if: every document (predecessor and each successor) was fetched over authenticated same-origin HTTPS; stable subject path and direct-successor relation verified at every hop; the final DID is active `e1_` with a valid binding proof. A failed or incomplete chain MUST NOT produce `provider_asserted`.

Assurance levels (exact meanings, §2.5.5):

| Level | Meaning |
|---|---|
| `verified` | predecessor's original binding key signed the deactivation + direct-successor document |
| `recovery_verified` | pre-authorized recovery key (from trusted pre-deactivation doc's `assertionMethod`) signed it |
| `provider_asserted` | authenticated same-origin complete chain to a proof-valid active DID, or the provider asserted it via a separately authenticated recovery/transition authority channel. Not a document property. MUST NOT be promoted to `verified`/`recovery_verified` |
| `unverified` | only isolated `successorDid`, `alsoKnownAs`, Handle/WNS mapping, 409 hint, standalone unsigned hop, incomplete chain, or no authenticated provenance |

### 4.4 Chain following, caching, conflicts (§2.6, §7)

- MUST limit chain length (hop limit; value not specified) and detect cycles.
- MUST reject a chain whose stable subject paths differ or where the same old DID has multiple successors.
- Cache only `verified`/`recovery_verified` edges, and only after the whole resolution succeeds. No partial prefixes on failure.
- Conflict between a cached verified edge and a new `successorDid` → MUST reject and report to the upper layer.
- Continuity does not automatically carry over group roles, attachment grants, or E2EE state (`TRANSITION-WBA-PROVIDER-ASSURANCE`: `automatic_e2ee_state_copy: false`; App. B.7).

### 4.5 409 DID Superseded (ANP-03 §3.2)

When the target or authenticating DID is deactivated and has a successor, the server may return:

```http
HTTP/1.1 409 Conflict
Content-Type: application/json
Cache-Control: no-store
```

```json
{
  "code": "did_superseded",
  "requestedDid": "did:wba:example.com:user:alice:e1_<old-fingerprint>",
  "currentDid": "did:wba:example.com:user:alice:e1_<current-fingerprint>",
  "stableSubjectId": "example.com:user:alice"
}
```

Client rules:

- `currentDid` is an unverified hint. Client MUST NOT retry directly with it.
- MUST fetch the old document, verify `deactivated`, `successorDid`, and the proof, then resolve each successor in turn to the current active DID.
- Re-sign with the current DID and resend.
- A transparent 301/302 should not substitute for this.

Server rule: a document with `deactivated = true` MUST NOT be used for new authentication (ANP-03 §3.1.2). The vector scenario maps this to `invalid_did` when no 409 is used.

### 4.6 did:web continuity

Appendix B.7: current Handle resolution and current DID authentication do not establish cross-DID authority migration. No automatic Web transition-verification profile is registered. Same-DID key updates and cross-DID changes MUST remain distinct. `TRANSITION-WEB-HANDLE-HINT`: changing handle mapping + `alsoKnownAs` grants nothing automatically.

---

## 5. Native did:web (ANP-02 App. B, repo Appendix B) and `k1_` (Appendix A)

### 5.1 Native did:web

- Use as-is; no conversion to did:wba.
- Resolve per the did:web method spec (`did:web:identity.example:alice` → `https://identity.example/alice/did.json`; root → `/.well-known/did.json`).
- MUST at least: (1) parse per did:web; (2) check `id` exactly equals the requested DID; (3) per DID Core, check the VM exists and is in the correct relationship.
- MUST NOT require WBA-specific identifier binding (E1/K1 fingerprints), document proof, or lifecycle rules for did:web.
- If a did:web document carries a standard proof (e.g. Data Integrity), MAY verify it per its declared profile and local policy. Vector `WEB-NO-DOCUMENT-PROOF`: authentication succeeds without a document proof.
- Cross-platform auth: `keyid` MUST be a full DID URL; server MUST resolve, MUST check the VM exists, MUST check it is in `authentication`; then common RFC 9421/9530 flow. Same challenge, replay, token rules as WBA (App. B.3).
- Messaging profiles: missing WBA proof never excuses Bundle/Object Proof, MLS, or message-authentication checks (App. B.5).
- WNS (legacy compatibility, weaker than WBA mainline): Handle → DID; resolve DID; find `ANPHandleService`; check `serviceEndpoint` is `https` and its domain equals the handle's domain. Path need not match `/.well-known/handle/{local}`. No fingerprint checks. The scenario label `legacy-domain-binding-accepted` is just a test label.

### 5.2 `k1_` compatibility (Appendix A), opt-in

Identity:

- Binding key: secp256k1 `publicKeyJwk`, in `authentication`, VM type `EcdsaSecp256k1VerificationKey2019`.
- Thumbprint: RFC 7638 over `{"crv":"secp256k1","kty":"EC","x":...,"y":...}`, SHA-256, base64url nopad, `k1_` prefix.
- Document MUST: `id` equals DID; ≥1 secp256k1 `publicKeyJwk` binding key; key in `authentication`; thumbprint equals `k1_` segment.

Document proof (optional, non-W3C) `didwba-jcs-ecdsa-secp256k1-2025`:

- Fields: `type: DataIntegrityProof`, `cryptosuite: didwba-jcs-ecdsa-secp256k1-2025`, `created`, `verificationMethod`, `proofPurpose: assertionMethod`, `proofValue`, optional `domain`/`challenge`.
- Generate: `unsecured = doc - proof`; `options = {type, cryptosuite, created, verificationMethod, proofPurpose[, domain][, challenge]}`; `toSign = SHA-256(JCS(options)) || SHA-256(JCS(unsecured))`; ECDSA secp256k1 with SHA-256 over `toSign` → DER → fixed 64-byte `R||S` → `proofValue = base64url-nopad(R||S)` (not multibase).
- Note: unlike the E1 vector implementation, A.5 does not say to copy `@context` into the proof options (see §8).
- Verify: check fields present and fixed values; remove `proof` from doc and `proofValue` from options; JCS each; hash and concatenate; verify ECDSA-SHA256 with the key at `verificationMethod`.
- Policy: verification is optional by default (relaxed). If enabled (strict), MUST also check: VM type is `EcdsaSecp256k1VerificationKey2019`; its thumbprint equals the `k1_` segment; other secp256k1 keys must not substitute. Implementations not supporting the cryptosuite MAY ignore the proof.
- SHOULD use the `k1_` binding key as `proof.verificationMethod`.

Request authentication (A.6):

- Client SHOULD sign with the `k1_` binding key; `keyid` MUST point to it.
- Signature: ECDSA + SHA-256 on secp256k1, fixed-length `r||s` (64 bytes) in `Signature`.
- Server MUST check: VM exists; VM in `authentication`; VM thumbprint equals `k1_` segment. Under A.6 this binds the request key to the DID even without a document proof, which is stricter than E1, where non-binding authentication keys may be allowed by policy.
- Lifecycle (A.8): binding key change → DID MUST change. Rotate by deactivating the old DID and creating a new one. App. A does not specify successor/proof continuity for `k1_`.
- Low-S normalization is not mentioned (see §8).

---

## 6. Security considerations and normative checklist

### 6.1 Security considerations (ANP-02 §7, ANP-03 §2.6/§7)

- Key management: private keys must not leak; establish regular key refresh; use multiple DIDs with separate keys and roles. WBA binding key ideally in HSM/secure enclave.
- Server MUST implement replay protection (cache `(keyid, nonce)`, `(keyid, jti)` or equivalent; single-use challenge nonces).
- Server MUST enforce `created`/`expires` window (anti time-rollback). Replay cache lifetime > signature lifetime.
- Nonces MUST come from an OS CSPRNG (e.g. Python `secrets`).
- When a body is present, server MUST verify `Content-Digest`.
- Authentication ≠ authorization; MUST be handled separately.
- Transport: MUST use HTTPS; client MUST strictly validate CA; MUST use SAN `dNSName`, not CN; DoH recommended; avoid untrusted cross-origin redirects.
- Tokens: MUST protect and MUST set reasonable expiry; prefer sender-constrained; IP/UA only auxiliary; SHOULD only over HTTPS via `Authentication-Info`.
- WBA: name-service sync after rotation; stable subject path never recycled; bounded chain following with cycle detection.

### 6.2 MUST / MUST NOT checklist, CLIENT side (signer and DID resolver)

Signing requests:

- [ ] MUST send `Signature-Input` + `Signature` (RFC 9421) on authenticated initial requests. (ANP-02 §3.1.1)
- [ ] MUST send `Content-Digest` (RFC 9530) when there is a body, and cover `content-digest`. (§3.1.1, §3.1.2.3)
- [ ] MUST cover at least `@method` and `@target-uri`. (§3.1.1/§3.1.2)
- [ ] `keyid` MUST be a complete DID URL to a VM in the DID Document. (§3.1.1; App. B.2)
- [ ] MUST include `created`. SHOULD include `expires`.
- [ ] If the server issued a `nonce` (401 challenge), MUST use that nonce. (§3.1.1, §3.2.4.1)
- [ ] The selected VM must be authorized by `authentication`. (§3.1.1)
- [ ] If `token_type` ≠ `Bearer`, MUST send the token per that extension. (§3.2.3.4)
- [ ] MUST bound retries after 401 (spec: "need to limit"). (§3.2.4.1)
- [ ] MUST protect access tokens. (§7.4)
- [ ] MUST use HTTPS, strictly validate the CA, match SAN `dNSName` (not CN). (§7.3)
- [ ] MUST generate nonces with a CSPRNG. (§7.2; applies to whoever generates nonces)
- [ ] For `k1_`: `keyid` MUST point at the secp256k1 binding VM. (App. A.6)
- [ ] On 409 `did_superseded`: MUST NOT retry with `currentDid` directly; MUST verify the old doc and successor chain first. (ANP-03 §3.2)

Publishing DIDs (controller side):

- [ ] `did:wba` prefix lowercase; no IP; port colon `%3A`. (ANP-03 §2.1–2.2)
- [ ] New path DIDs MUST end with `e1_<fp>` (or `k1_` if Appendix A is used). (§2.2.1)
- [ ] E1 binding key MUST be Ed25519 `Multikey`/`publicKeyMultibase`, in `authentication`, thumbprint == segment. (§2.2.2, §2.5 note 7)
- [ ] Active E1 doc MUST carry a `DataIntegrityProof`/`eddsa-jcs-2022` proof by the binding key, `proofPurpose: assertionMethod`, key in `assertionMethod`, `proofValue` base58btc multibase. (§2.5.5)
- [ ] `@context` MUST include DID v1; E1 also data-integrity/v2 and multikey/v1. (§2.5)
- [ ] External references / `serviceEndpoint` MUST be absolute URIs. (§2.4)
- [ ] `ANPHandleService.serviceEndpoint` MUST be an absolute dereferenceable HTTPS URI under the Handle Provider's domain. (§2.5)
- [ ] `successorDid` MUST be a complete DID of the direct successor; MUST NOT skip or be rewritten. (§2.5, §2.5.3)
- [ ] On binding-key rotation: DID MUST change; same stable subject path MUST be kept; new doc MUST be published; old doc MUST remain retrievable with `deactivated: true` + `successorDid`; old doc MUST NOT be removed. (§2.5.3–2.5.4)
- [ ] Stable subject path MUST NOT be modified, recycled, or reassigned. (§2.2.3)
- [ ] Recovery proofs MUST NOT use a key introduced only at deactivation. (§2.5.5 #1)

### 6.3 MUST / MUST NOT checklist, SERVER side (verifier and resolver)

Request verification:

- [ ] Check presence of `Signature-Input`, `Signature`, and `Content-Digest` if body. (ANP-02 §3.2.1.1)
- [ ] MUST verify `Content-Digest` against the actual body when a body exists. (§3.2.1.2, §7.2)
- [ ] Resolve and validate the DID Document under the method. (§3.2.1.4)
- [ ] Verify the `keyid` VM exists AND is authorized by `authentication` (MUST for did:web per App. B.2.4; required step for all). (§3.2.1.5)
- [ ] Rebuild the RFC 9421 signature base from the actual request and verify. (§3.2.1.6, §3.2.2)
- [ ] Choose the algorithm from the VM type; Ed25519 → 64-byte signature. (§3.2.2.4)
- [ ] Enforce `created`/`expires` window (recommended 1–5 min). MUST prevent time rollback. (§3.2.1.7, §7.2)
- [ ] MUST implement replay protection; challenge nonces MUST be single-use. (§3.2.1.8, §7.2)
- [ ] MUST use a CSPRNG for issued nonces. (§7.2)
- [ ] MUST treat authorization separately; return 403 `forbidden_did` if unauthorized. (§3.2.1.9, §7.2)
- [ ] On auth failure return 401 with `WWW-Authenticate` carrying `error` (required param). (§3.2.4.1)
- [ ] MUST bound challenge/retry loops. (§3.2.4.1)
- [ ] If issuing tokens: MUST return them via `Authentication-Info`, NOT an `Authorization` response header. (§3.2.3.2)
- [ ] MUST protect tokens and MUST set a reasonable expiry. (§7.4)
- [ ] JSON carriage: digest only over `payload`. (§4.1.1, §4.2.1)

did:wba resolution and method rules:

- [ ] Resolution URL algorithm (ANP-03 §2.5.2, "must be performed").
- [ ] TLS: MUST match SAN `dNSName`, MUST NOT rely on CN. (§2.2)
- [ ] MUST verify document `id` equals the DID. (§2.5.2)
- [ ] JSON-LD processing failure with `@context` present → reject. (§2.4.1)
- [ ] Relative internal refs MUST be expanded against the document DID. (§2.4.5)
- [ ] Active E1: proof MUST exist and verify (`eddsa-jcs-2022`); `proof.verificationMethod` MUST be Ed25519 Multikey; its thumbprint MUST equal the `e1_` segment; otherwise parsing MUST fail. No relaxed mode; not affected by local policy switches. (§2.5.2, §2.5.5)
- [ ] MUST bind using the key at `proof.verificationMethod`, not an arbitrary Ed25519 key in `authentication`. (§3.1.2)
- [ ] Generation and verification MUST follow the `eddsa-jcs-2022` standard algorithm. (§2.5.5 #3)
- [ ] Deactivated doc: MUST NOT be used for new authentication. (§3.1.2)
- [ ] Deactivated E1: MUST still find the original binding key; if `successorDid` present, MUST check same stable subject path. (§2.5.2)
- [ ] Present proof on transition doc MUST verify as old-binding or pre-authorized recovery; otherwise MUST invalidate the transition and MUST NOT downgrade. (§2.5.5)
- [ ] Recovery proof: MUST confirm prior `assertionMethod` authorization from a previously trusted state. (§2.5.5)
- [ ] Unsigned hop: standalone verifier MUST report `unverified`. Failed/incomplete chain MUST NOT produce `provider_asserted`. `provider_asserted` MUST NOT be promoted. (§2.5.5)
- [ ] MUST NOT treat same stable subject path as same subject; MUST NOT merge DIDs by stripping the last segment. (§2.2.3, §7)
- [ ] MUST limit chain length, detect cycles, reject differing stable subject paths or multiple successors. (§7)
- [ ] `provider_asserted`/`unverified` edges MUST NOT enter the verified-edge cache; failed chains MUST NOT leave prefix edges; cached-vs-new successor conflict MUST be rejected and reported. (§2.6)
- [ ] Handle confirmation-only results MUST NOT be treated as a specific-handle binding. (§2.5 service)
- [ ] `k1_` (if enabled): binding checks per A.4; request auth checks per A.6 (MUST: VM exists, in `authentication`, thumbprint == `k1_`); strict proof mode MUST also check VM type and thumbprint and MUST NOT substitute other keys. Strict mode with missing proof MUST fail.
- [ ] Non-E1 strict mode with missing proof MUST fail. (§2.5.5)

did:web:

- [ ] MUST parse per did:web; check `id` exact; check VM existence and relationship. (ANP-02 App. B.1)
- [ ] MUST NOT require WBA fingerprint/proof/lifecycle rules for did:web. (App. B.1)
- [ ] MUST apply the ANP-02 Web binding before consuming Web identity material. (repo App. B.2)
- [ ] Same-DID key updates vs cross-DID changes MUST remain distinct. (repo App. B.7)

---

## 7. Test vectors (`examples/did-authentication-vnext/`)

Status: "offline fixtures and protocol scenario designs; no SDK or product conformance claim". Scenarios are `execution_status: design-only-not-run-against-sdk-or-product`. Auth scenarios carry `applicability: illustrative-implementation-policy-not-additional-anp02-conformance`: the error mappings, replay, cache and token behaviour illustrate one policy and are not extra normative requirements. ANP-02 text wins.

### 7.1 Files

| File | Contents |
|---|---|
| `manifest.json` | `source_commit b7ba3ff8…`, SHA-256 of each file, counts: 10 identity fixtures, 32 positive byte vectors, 80 negative byte vectors, 215 design scenarios; commands `node scripts/generate-anp02-vectors.mjs [--write]`, `node scripts/check-anp02-vectors.mjs` (Node ≥ 22). |
| `identities.json` | `fixed_time 2026-09-07T08:00:00Z`; keys = `SHA-256("ANP02-PUBLIC-TEST-ONLY:" + label)` used as the Ed25519/X25519 seed (test-only); `identities` keyed `api-wba, alice-wba, bob-wba, service-wba, group-wba, api-web, alice-web, bob-web, service-web, group-web`, each `{did, method, kind, root_kid, additional_authentication_kid, document}`. |
| `byte-vectors.json` | `positives[]` and `negatives[]` (see below). |
| `scenario-vectors.json` | `fixture_capabilities` (Ed25519; `Multikey`, `JsonWebKey2020-OKP-Ed25519`), `method_pairs` (wba/web × wba/web), `scenarios[]` each `{id, category, execution_status, applicability?, policy_note?, input, actions, expected, normative_refs}`. |

Identity fixture shape (api-wba): VMs `#root` (Ed25519 Multikey, binding key, signs E1 proof), `#auth-jwk` (`JsonWebKey2020` OKP Ed25519, in `authentication` only), `#assertion-only` (Multikey, in `assertionMethod` only). `authentication = [#root, #auth-jwk]`, `assertionMethod = [#root, #assertion-only]`. `@context` includes `jws-2020/v1`. Agents add `#device-{a,b}-sign`, `#device-{a,b}-ka` (X25519 Multikey `z6LS…`), `keyAgreement`, `deviceManifest`, `ANPMessageService` with `serviceDid` + `profiles` + `securityProfiles`. Service DIDs are bare domain (`did:wba:service-wba.example`, no proof). Group docs have `controller: did:wba:service-wba.example`. Web docs have no proof; `api-web#root` is a `JsonWebKey2020`.

### 7.2 Byte vectors

Positive request-signature vectors: `HTTP-{wba,web}-{POST,GET,JWK,NONCELESS}`, `JSON-{wba,web}-POST`, `ORIGIN[-GROUP]-{pair}` (P1 messaging). Fields: `id, kind, transport (http-headers | http-json-metadata | p1-origin), identity_fixture, subject_did, keyid, public_key_jwk, method, target_uri, payload_utf8, components, signature_params, signature_base_utf8, content_digest, signature_input, signature, signature_b64` (+ `envelope` for JSON, `signed_request_object` for ORIGIN).

Data-integrity vectors: `DOCUMENT-{api,alice,bob,group}-wba` (E1 document proofs) with `object, proof_config_jcs, document_jcs, hash_data_hex`; also P4/P5/P6 object proofs and P5 AEAD vectors (messaging, out of scope).

Negatives: `{id, base_id, mutation, replacement?, property?, expected_integrity:false}`; mutation kinds `request-target` (→ `https://attacker.example/other`), `request-content` (append space), `signature-byte` (flip), `object-property` (add `tampered: true`), `proof-purpose` (→ `authentication`), and AEAD ones.

### 7.3 How to use for conformance

1. **Primitive KATs**: base58btc multikey decode, RFC 7638 thumbprint → `e1_` (all E1 DIDs), SHA-256 `Content-Digest`, JCS output (`proof_config_jcs`, `document_jcs`, JSON payload), `eddsa-jcs-2022` `hashData` (`hash_data_hex`) and signature verify.
2. **Signer KAT**: Ed25519 is deterministic, so a signer given the fixture private key and the same params must reproduce `signature_input`, `signature_base_utf8`, and `signature` byte-for-byte. Private seed = `SHA-256("ANP02-PUBLIC-TEST-ONLY:" + "<identity-id>:<vm-fragment>")`, e.g. `ANP02-PUBLIC-TEST-ONLY:api-wba:root`, `...:api-wba:auth-jwk`, `...:alice-wba:device-a-sign` (X25519 for `-ka`). Verified: `api-wba:root` seed → public `x = g0UoJP1oc-BCiT8pJa8lfekejLLEzPjheYJBn4jj8TE`.
3. **Verifier KAT**: feed method + target + headers + body into the verifier with a stubbed resolver returning `identities.json` documents; fix the clock at `1788768030` (within `created=1788768000` / `expires=1788768060`). Positives must pass; every negative must fail.
4. **Scenario adapter**: for each `scenarios[]` entry, build the valid baseline from `input` (identity fixture, byte vector, `verifier_time`, `allowed_clock_skew_seconds`, `authorized`, `allow_nonbinding_authentication_keys`), apply `actions` (when a scenario changes a WBA doc to test a later layer, re-sign the E1 proof with the root key; tests aimed at E1 evidence must not repair it), compare to `expected.outcome`, `expected.public_error`, `expected.side_effect_count`. Use the scenario clock, never wall time. Record results in your own evidence store; do not rewrite the catalog.
5. Relevant scenario IDs for this layer (categories authentication 49, token 10, resolution-security 10, method-evidence 9, json-carriage 6, continuity 3, future-method 1):
   - Accept: `AUTH-*-ACCEPT`, `AUTH-*-JWK-ALLOWED`, `JSON-*-ACCEPT`, `WEB-NO-DOCUMENT-PROOF`, `TOKEN-*-OPTIONAL`.
   - `invalid_verification_method`: `NO-AUTH-RELATIONSHIP`, `ASSERTION-ONLY`, `UNKNOWN-KID`, `UNSUPPORTED-ALG`.
   - `invalid_did`: `DOCUMENT-ID-MISMATCH`, `RESOLUTION-TEMPORARY` (no deactivation cache), `DISABLED-METHOD`, `AUTH-UNSUPPORTED-DID-METHOD`, `WBA-E1-PROOF-MISSING`, `WBA-E1-PROOF-TAMPER`, `AUTH-wba-DEACTIVATED`, `AUTH-web-DOCUMENT-REMOVED`.
   - `WBA-E1-WRONG-BINDING-KEY`: reject even though the document signature is valid (thumbprint mismatch).
   - `invalid_signature`: `TARGET-TAMPER`. `invalid_content_digest`: `BODY-TAMPER`, `HTTP-JSON-WHITESPACE`, `JSON-*-WRONG-BOUNDARY`. `invalid_request`: `MISSING-DIGEST`, `UNCOVERED-TARGET`. `invalid_timestamp`: `EXPIRED`, `FUTURE`.
   - `invalid_nonce`: `REPLAY`, `NONCELESS-REPLAY`, `NONCELESS-REPLAY-LABEL`, `CHALLENGE-MISMATCH`, `CHALLENGE-ONCE`, `CONCURRENT-REPLAY`; `INVALID-SIGNATURE-NONCE` (bad sig must not consume the challenge).
   - `forbidden_did`: `FORBIDDEN`, `TOKEN-*-SCOPE`. `invalid_access_token`: `TOKEN-*-ISSUER`, `-AUDIENCE`, `-EXPIRY`.
   - `AMBIGUOUS-KID` (duplicate VM id → reject, no first/last fallback).
   - `RESOLUTION-*-{TLS-IDENTITY, REDIRECT-INTERNAL, REDIRECT-CREDENTIAL, RESPONSE-BUDGET, PARTIAL-VALIDATION-CACHE}`.
   - `TRANSITION-WBA-INVALID-PROOF`, `TRANSITION-WBA-PROVIDER-ASSURANCE`, `TRANSITION-WEB-HANDLE-HINT`, `WEBVH-DESIGN-NOT-ENABLED`.

Gaps in the vectors: no secp256k1/`k1_` vectors; no deactivated/successor-chain documents with real bytes (`verified`/`recovery_verified` hops); no `@authority`/`content-type` coverage vectors; no 401 challenge header byte vectors; no port-encoded DID resolution vectors.

---

## 8. Ambiguities, gaps, draft/candidate items

Status: ANP-02, ANP-03, App. A, App. B are all "Released, v1.2". Things explicitly not finalized:

1. **Sender-constrained tokens**: "does not yet fully define the specific profile"; `Bearer` is default. (ANP-02 §3.2.3.3)
2. **WebVH**: informative only; "does not define an immediately enabled WebVH binding". (ANP-02 App. C)
3. **Pure-JSON transports** without metadata/payload separation and **non-HTTP component mappings** are left to future/app-layer profiles; **non-HTTP token return** is unspecified. (ANP-02 §4, §4.2.1)
4. **Vectors README**: P6 "remains a candidate pending its registered MLS ExtensionType release gate"; scenarios are design-only.
5. **Token payload example** uses ISO strings for `iat`/`exp`, which conflicts with RFC 7519 NumericDate. Vectors use NumericDate and the README notes the original example was preserved verbatim. Use NumericDate.
6. **WWW-Authenticate scheme `DIDWba`** is used for all DID methods, including did:web. ANP-02 doesn't register it or define ABNF. `Accept-Signature` example lists `keyid` as a parameter to be included without a value.
7. **Legacy doc drift**: `docs/did-wba-server-test-interface.md` (and blog posts) describe the deprecated scheme `Authorization: DID <did> Nonce <..> Timestamp <..> VerificationMethod <..> Signature <..>`, return tokens in an `Authorization` response header, use `WWW-Authenticate: Bearer error=...`, and 403 for auth failure. All of that contradicts ANP-02 1.2 (`Signature-Input`/`Signature`, `Authentication-Info`, `DIDWba`, 401). The test server at `agent-network-protocol.com/wba/test` therefore probably tests the legacy scheme, not ANP-02 1.2. Do not use it for 1.2 conformance. The repo's `tests/release-doc-entrypoints.test.mjs` treats `Authorization: DIDWba did=` in guides as a "legacy auth header" error. Also, `docs/anp-getting-started-guide.md` says ANP-07's `didwba` declaration with an `Authorization` label is legacy.
8. **ABNF gaps**: `domain-name` is undefined; the `%3A` port isn't in the ABNF; the `.` in `path-segment` allows `.`/`..` (path traversal on URL mapping); case sensitivity of the host is unspecified; an E1 DID directly under the domain (`did:wba:host:e1_…`) does not match the ABNF (requires ≥1 namespace segment). Legacy unprefixed path DIDs are MAY-parse. What binding rules apply to them is unspecified (presumably none).
9. **Section numbering**: ANP-03 has two "2.5" sections ("DID Document Description" and "DID method operation") and no 2.3. References like "Sections 2.5.2 through 2.5.5" point to the operation subsections.
10. **Replay key for nonce-less requests**: the spec says `(keyid, nonce)` "or equivalent" but `nonce` is optional. The vectors expect nonce-less replays to be rejected and label-renames to count as replays. You need a signature- or statement-based replay key. "Direct connection proof profile" and "challenge profile" are named but not formally defined, and there is no way to advertise which a server requires (except an up-front 401).
11. **Multiple signatures/labels** in one request: unspecified which to verify.
12. **Time window**: "1 to 5 minutes recommended". Whether that applies to `now - created`, to `expires - created`, or as max skew is not specified. Behaviour without `expires` is unspecified. Vectors use skew 0 and reject `created` in the future.
13. **Non-binding authentication keys for E1**: ANP-03 §3.1.1 says other `authentication` keys are local policy. Vectors set `allow_nonbinding_authentication_keys: true`. For `k1_`, A.6 requires that the request key's thumbprint match `k1_` (stricter). Inconsistent across profiles.
14. **`@target-uri` behind proxies**: not addressed; deployments must reconstruct the external URI.
15. **`@context` in proof options**: E1 relies on W3C `eddsa-jcs-2022` (which copies `@context` into proof config; vectors confirm). A.5's k1 proof options list omits `@context`. Ambiguous whether k1 implementations copy it. No k1 vectors exist to settle it.
16. **secp256k1 low-S** normalization and DER→`r||s` padding rules are not stated for k1 request or proof signatures.
17. **JSON-LD processing**: "should be processed according to JSON-LD rules; if it cannot be processed … rejected". Remote context fetching policy is not addressed. Pin known contexts.
18. **Caching**: no document-cache TTL/invalidation rules beyond the successor-edge cache. Scenario policies imply refresh on deactivation and no stale fallback.
19. **Deactivated doc served for new auth**: ANP-03 says server "should" return 409 if `successorDid` is present. The vectors map deactivation to `invalid_did` (401). Both are acceptable; 409 is the WBA-specific path.
20. **Hop limit value** for successor chains is not specified.
21. **`k1_` continuity**: App. A defines no `successorDid`/recovery semantics for k1. Only "deactivate old, create new; name service maintains reference".
22. **did:web root/path resolution** details are referenced to the external did:web spec (archived copy at `references/did_web-method-specification.html`), not restated.
23. **`provider_asserted` "separately authenticated recovery/transition authority channel"**: no wire format defined.
24. **Handle confirmation endpoint** (`/.well-known/handle/by-did?did=...`) response format is in ANP-04, not here.
