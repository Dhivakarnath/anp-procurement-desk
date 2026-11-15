# 05 — AgentConnect (official ANP SDK) survey

Research date: 2026-10-30. Source: `/tmp/anp-research/AgentConnect` (origin `https://github.com/agent-network-protocol/AgentConnect.git`).
Read-only review. No tests were run (running `uv sync` would create a `.venv` inside the clone). Test counts below are static `grep` counts.

Cross-reference: ANP-02 HTTP auth requirements are in `01-identity-auth.md` §3. Section 9 of this file compares SDK behaviour against those requirements.

---

## 0. Snapshot and provenance

| Item | Value |
|---|---|
| Clone | shallow, 1 commit: `bab0a0e 2026-10-14 Merge reviewed release/1014 into master` (author Gaowei Chang) |
| Version in repo | `1.0.6` (`pyproject.toml`, `anp/__init__.py`, `rust/Cargo.toml`, `golang/version.go`, `rust/src/lib.rs`) |
| Latest PyPI `anp` | **1.0.7** (uploaded 2026-10-22). History: 0.9.0 (07-20) … 1.0.1 (09-07), 1.0.2, 1.0.3 (09-11), 1.0.4rc1, 1.0.4, 1.0.5 (09-24), 1.0.6 (10-13), 1.0.7 (10-22) |
| Latest crates.io `anp` | **1.0.7** (2026-10-22), 1,938 total downloads |
| Latest Go module | `github.com/agent-network-protocol/anp/golang` **v1.0.7** (2026-10-22, tag `golang/v1.0.7`; proxy origin repo is `github.com/agent-network-protocol/anp`, i.e. the repo was renamed/mirrored as `anp`) |
| npm `@awiki/anp-typescript-sdk` | **0.9.5** (2026-09-24); earlier 0.2.0, 0.9.3, 0.9.4 |
| pub.dev `anp` (Dart) | **0.8.7** (2026-05-07); repo `dart/pubspec.yaml` says 0.8.9 (unreleased) |
| Java `com.agentconnect:anp4j` | not on Maven Central (search returned 0 hits); local build `1.0.0` only |
| License | Apache-2.0 (NOTICE: was MIT "until 10 October 2025"; PyPI/crates 1.0.3 shipped MIT. The 2025 date conflicts with 1.0.3's 2026-09-11 release date, so NOTICE likely has a year typo) |
| Release cadence | Python/Go/Rust share one version via `skills/anp-multilang-release/scripts/release.py`. ~10 releases in 3 months. TS and Dart are versioned separately. |

The clone is one patch release behind the registries (1.0.6 vs 1.0.7). Pin `anp==1.0.7` and check its changelog before relying on repo-HEAD behaviour.

The repo is co-developed with the AWiki product: `AGENTS.md` points at `../../awiki-harness/rules/...` (not in this repo), the npm package lives under the `@awiki` scope, and the TS SDK ships an AWiki IM client. `AGENTS.md` also references `examples/ping_pong.py` and `python -m anp.meta_protocol.cli`, and neither exists.

---

## 1. Repository layout

| Path | Contents |
|---|---|
| `anp/` | Python package (~43k lines including tests). Submodules listed in §3. |
| `anp/unittest/` | Python unit tests per module (excluded from the wheel). |
| `examples/python/` | 12 example folders (§5). |
| `golang/` | Pure-Go module (no cgo, Go 1.22). Packages: `authentication`, `proof`, `wns`, `direct_e2ee`, `group_e2ee`, `cmd/anp-interop`, `integration/`, `examples/`, `docs/api.md`. |
| `rust/` | `anp` crate (edition 2021, MSRV 1.88). Modules: `authentication`, `proof`, `wns`, `direct_e2ee`, `group_e2ee` (OpenMLS 0.8), `sealed_handoff`. Features `jwt-pem`, `mls`, `network` (all default). ~33.6k lines in `src/`. |
| `typescript/ts_sdk/` | `@awiki/anp-typescript-sdk`, Node ≥20, ESM+CJS via tsup. Modules: `authentication`, `proof`, `wns`, `im` (AWiki IM client). ~8.4k lines. |
| `dart/` | `anp` package, Dart ≥3.8, Flutter smoke workspace. ~5.7k lines. |
| `java/` | Maven multi-module: `anp4j` (core), `anp-spring-boot-starter`, `anp-examples`. Java 17. ~13.5k lines including examples. |
| `docs/` | `did-web-sdk.md`, `did/device-manifest-vnext-sdk.md`, `e2e/direct-e2ee-p5-sdk.md`, `e2e/group-e2ee-p6-anp-mls.md`, `e2e/group-e2ee-p6-v2-sdk.md`, `ap2/`, `did_public/` (public test DIDs and keys), `jwt_rs256/` (demo JWT keys), `examples.md`. |
| `testdata/` | Shared cross-language vectors: `device_manifest/`, `did_transition/`, `direct_e2ee/` (P5 v1 + v2 wire), `group_e2ee/` (did_wba_binding golden, P6 v2 wire), `wns/binding_generation_vectors.json`. |
| `fixtures/did-method-lifecycle-v1.json` | DID method lifecycle fixture. |
| `tests/` | `system/` and `e2e/` (both only exercise the e1 auth example), `rust_interop_config.json` (baseline released Python = 0.7.1). |
| `skills/anp-agent/` | Claude-style skill: CLI to call remote ANP agents (§8). |
| `skills/anp-multilang-release/` | Release helper and policy. |
| `tools/` | `did_generater/generate_did_doc.py`, `generate_did_transition_vectors.py`, `migrate_anp_key_pem.py`. |
| `scripts/` | `release_sdks.py`, `run_all_examples.py`, `run_all_tests.py`. |
| `.github/workflows/rust-python-interop.yml` | Only CI workflow; `workflow_dispatch` (manual). Runs `cargo test`, Python `anp/unittest/rust_interop`, and a fixture smoke test on Python 3.13. |
| `anp_all_sdk_list.txt` (30 KB), `anp_analysis.py` | Generated API inventories. |

---

## 2. Feature matrix

Legend: ✅ implemented, 🟡 partial/wire-only/legacy, ❌ absent.

| Feature | Python `anp` | Go | Rust | TypeScript | Dart | Java |
|---|---|---|---|---|---|---|
| DID WBA doc create (e1 Ed25519 / k1 secp256k1 / plain) | ✅ `create_did_wba_document` | ✅ `CreateDidWBADocument` | ✅ `create_did_wba_document` (+ external-signer two-phase e1) | ✅ `createDidWbaDocument` | ✅ | 🟡 plain secp256k1 only, no e1/k1 binding, no proof |
| vNext DID / Device Manifest builders | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| DID resolve did:wba + did:web | ✅ (HTTPS only, no cache, no resolver injection in verifier) | ✅ (`DidResolutionOptions.BaseURLOverride`) | ✅ (`did_resolution_options`) | ✅ (`didResolver` injectable) | ✅ | 🟡 did:wba only |
| DID transition / successor chain | ✅ `resolve_current_did` | ✅ | ✅ | ? (not checked) | ? | ❌ |
| ANP-02 RFC 9421 HTTP signature **sign** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| ANP-02 RFC 9421 HTTP signature **verify** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Legacy `Authorization: DIDWba …` header | ✅ sign+verify | ✅ | ✅ | ✅ | ✅ | ✅ (only scheme Java supports) |
| Server verifier with JWT issue + Bearer verify | ✅ `DidWbaVerifier` | ✅ | ✅ | ✅ | 🟡 25-line facade: signature check against a caller-supplied DID doc; no JWT, nonce or time window | 🟡 Spring filter verifies legacy header; no token issuance |
| Client token cache + 401 challenge retry | ✅ `DIDWbaAuthHeader` | ✅ | ✅ | ✅ | ❌ (`DidWbaAuthenticator` only signs) | 🟡 token cache, no challenge |
| Federated service-to-service verify (`ANPMessageService.serviceDid`) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| W3C Data Integrity proof (eddsa-jcs-2022, secp256k1) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Appendix-B object proof / group receipt / did_wba_binding | ✅ | ✅ | ✅ | ❌ (not exported) | ✅ | ❌ |
| IM proof / RFC 9421 origin proof | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| WNS handles (validate, resolve, binding, `binding_generation`) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| ADP `ad.json` generation | ✅ OpenANP + FastANP | ❌ | ❌ | ❌ | ❌ | ✅ Spring `@AnpAgent` |
| OpenRPC `interface.json` from type hints + JSON-RPC 2.0 server | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ `OpenRpcGenerator` |
| Crawler / remote-agent client (ad.json → OpenRPC → call, OpenAI tools) | ✅ `RemoteAgent`, `ANPCrawler`, `ANPClient` | ❌ | ❌ | ❌ (has AWiki IM client instead) | ❌ | ✅ `RemoteAgent`, `ANPCrawler` |
| Meta-protocol (LLM negotiation) | 🟡 experimental, several TODOs | ❌ | ❌ | ❌ | ❌ | 🟡 concept example |
| Direct E2EE P5 v1 runtime (X3DH + ratchet) | ✅ `DirectE2eeSession` | ✅ | ✅ | ❌ | ❌ | ❌ |
| Direct E2EE P5 v2 | 🟡 wire models/builders/validators | 🟡 wire | ✅ wire + exact-device runtime `V2DirectE2eeSession` | ❌ | 🟡 wire | ❌ |
| Group E2EE P6 (MLS) | ❌ (only legacy HPKE sender-key `GroupE2eeSession`) | 🟡 wire models + exec provider contract | ✅ real OpenMLS typed ops v1 + persistent v2 (release-blocked codepoint, "hidden/test-only") | ❌ | ❌ | ❌ |
| Legacy E2EE (HPKE, v2 ECDHE, WebSocket) | 🟡 `e2e_encryption_hpke`, `e2e_encryption_v2`, `e2e_encryption` | ❌ | 🟡 `hpke` dep | ❌ | ❌ | ❌ |
| AP2 mandates (ES256K JWT, cart/payment/receipts) | ✅ `anp.ap2` | ❌ | ❌ | ❌ | ❌ | 🟡 concept example |

Summary: Python is the only SDK that covers the full application stack (identity + ADP/OpenRPC server + client + AP2). Go and Rust are protocol-core SDKs (identity, proof, WNS, E2EE) with no agent server or client framework. Rust has the deepest E2EE. TS and Dart cover core identity, proof and WNS. Java is a legacy-era port that lacks RFC 9421 signatures.

---

## 3. Python API reference

Install: `pip install "anp[api]==1.0.7"` (the `api` extra adds FastAPI, uvicorn and openai, and OpenANP/FastANP need it).

Python version: `requires-python = ">=3.8"` is not accurate. `anp/openanp/types.py:481` does `class RPCMethodCollection(dict[str, RPCMethodInfo])`, which fails on 3.8. Treat 3.10+ as the floor; CI uses 3.13.

Core deps: `cryptography>=43.0.3` (locked 46.0.1), `ecdsa`, `asn1crypto`, `base58`, `jcs`, `canonicaljson`, `pyjwt>=2.9`, `aiohttp>=3.10` (requests use aiohttp; `requests` is also a dep), `websockets`, `pydantic>=2.9,<3`, `jsonschema`, `python-dotenv`. Extras: `api` = `fastapi>=0.115.4,<1` (locked 0.117.1, starlette 0.48), `uvicorn`, `openai`; `dev` = pytest, pytest-asyncio, pytest-cov.

Top-level `anp` exports only `ANPClient`, the Direct E2EE classes and `__version__`. Import from submodules.

### 3.1 `anp.authentication`

**Create a DID document and keys**

```python
from anp.authentication import create_did_wba_document

did_document, keys = create_did_wba_document(
    hostname="example.com",              # no IP addresses allowed
    port=None,                            # encoded as %3A in the DID
    path_segments=["agents", "alice"],
    agent_description_url="https://example.com/agents/alice/ad.json",  # adds AgentDescription service
    services=None,                        # extra service entries; "#id" is prefixed with the DID
    did_profile="e1",                     # "e1" (default, Ed25519 Multikey), "k1" (secp256k1 JWK), "plain_legacy"
    enable_e2ee=True,                     # adds key-2 (P-256) and key-3 (X25519, keyAgreement)
)
# did_document["id"] == "did:wba:example.com:agents:alice:e1_<multikey-fingerprint>"
# keys == {"key-1": (private_pem, public_pem), "key-2": ..., "key-3": ...}
```

- e1: Ed25519 key `#key-1` in `authentication` and `assertionMethod`; `proof` is DataIntegrityProof / `eddsa-jcs-2022`. The fingerprint is appended as the last path segment `e1_<fp>`.
- k1: secp256k1 JWK, `k1_<RFC7638 thumbprint>`, cryptosuite `didwba-jcs-ecdsa-secp256k1-2025`.
- `plain_legacy`: secp256k1, no binding segment, legacy `EcdsaSecp256k1Signature2019` proof.
- Publish at `https://<host>/<path segments joined by />/did.json`, or `https://<host>/.well-known/did.json` when there are no path segments. The e1 segment is part of the path.
- Private keys are returned as unencrypted PKCS#8 PEM bytes. Persisting and protecting them is up to you.
- `create_did_wba_document_with_key_binding` is deprecated (use `did_profile="k1"`).
- Other builders: `build_vnext_did_document`, `add_device_to_did_document`, `update_device_in_did_document`, `remove_device_from_did_document`, `build_web_did_document` (did:web), `build_anp_message_service`, `build_agent_message_service`, `build_group_message_service`. `parse_device_manifest`, `validate_device_manifest` and `find_eligible_device` handle the vNext `deviceManifest`.
- CLI: `uv run python tools/did_generater/generate_did_doc.py <did> [--agent-description-url URL]`.

**Resolve**

- `await resolve_did_wba_document(did, verify_proof=False)`: always fetches `https://…`, 10 s timeout, checks `id` and e1/k1 binding. Returns `None` on any failure (logs the error), so the caller sees `None` and no reason.
- `await resolve_did_document(did, *, verify_proof, timeout_seconds, verify_ssl, base_url_override, headers)`: generic did:wba + did:web resolver. Raises on failure. Has `base_url_override` for local development. The did:web path uses a public-address resolver (SSRF guard) and a 1 MiB cap.
- No caching anywhere.
- DID transitions: `resolve_current_did`, `verify_transition_hop`, `parse_did_wba_e1`, `InMemoryTransitionCache`.

**Client signing (ANP-02)**

```python
from anp.authentication import DIDWbaAuthHeader
auth = DIDWbaAuthHeader(did_document_path="did.json", private_key_path="key-1_private.pem",
                        auth_mode="http_signatures")  # or "legacy_didwba" / "auto"
headers = auth.get_auth_header(url, method="POST", headers={"Content-Type": "application/json"}, body=body_bytes)
# -> {"Signature-Input": 'sig1=("@method" "@target-uri" "@authority" "content-digest");created=…;expires=…;nonce="…";keyid="did:…#key-1"',
#     "Signature": "sig1=:…:", "Content-Digest": "sha-256=:…:"}
auth.update_token(url, response_headers)   # reads Authentication-Info (or a Bearer Authorization header)
auth.should_retry_after_401(resp_headers); auth.get_challenge_auth_header(url, resp_headers, method, headers, body)
auth.clear_token(url); auth.clear_all_tokens()
```

- Default covered components: `@method @target-uri @authority`, plus `content-digest` when there is a body. `expires = created + 300`. A random 16-byte hex nonce is added. The key is the first `authentication` entry.
- Signatures: ECDSA DER signatures are normalised to raw `r||s`; Ed25519 is used as-is.
- Once a token is cached, `get_auth_header` returns `Authorization: Bearer <token>` for that host.
- Lower-level: `generate_http_signature_headers(did_document, request_url, request_method, sign_callback, headers, body, keyid, nonce, created, expires, covered_components)` with `sign_callback(content: bytes, vm_fragment: str) -> bytes`. Use it to sign with a KMS or HSM instead of a key file.
- Legacy: `generate_auth_header(did_document, service_domain, sign_callback, version="1.1")` produces `DIDWba v="1.1", did=…, nonce, timestamp, verification_method, signature`, signing the JCS of `{nonce, timestamp, aud, did}`.

**Server verification**

```python
from anp.authentication import DidWbaVerifier, DidWbaVerifierConfig, DidWbaVerifierError
verifier = DidWbaVerifier(DidWbaVerifierConfig(
    jwt_private_key=PRIV_PEM, jwt_public_key=PUB_PEM, jwt_algorithm="RS256",
    access_token_expire_minutes=60, nonce_expiration_minutes=6, timestamp_expiration_minutes=5,
    external_nonce_validator=None,          # (did, nonce) -> bool | Awaitable[bool]; use for a Redis replay cache
    allowed_domains=None,                   # enforced only by the FastAPI middleware (Host header)
    allow_http_signatures=True, allow_legacy_didwba=True,
    emit_authentication_info_header=True, emit_legacy_authorization_header=True,
    require_nonce_for_http_signatures=True,
))
result = await verifier.verify_request(method, url, headers, body, domain=None)
# result = {"did", "auth_scheme": "http_signatures"|"legacy_didwba"|"bearer", "response_headers": {...},
#           "access_token"?, "token_type"?}
# Failure: DidWbaVerifierError(status_code, headers)  (WWW-Authenticate: DIDWba realm=…, error=…; Accept-Signature: …)
```

HTTP-signature verify flow: parse `keyid` → resolve DID (did:web via the generic resolver, did:wba via `resolve_did_wba_document`) → check binding → check `keyid` is in `authentication` (403 if not) → verify digest and signature → check the time window (created up to 60 s in the future, up to 5 min old, `expires` not passed) → require a nonce → single-use nonce cache → issue a JWT `{sub: did, iat, exp}`.

- A JWT is issued only when `jwt_private_key` is set; otherwise the call fails with 500.
- Bearer verification needs `jwt_public_key` and accepts only `did:wba:` / `did:web:` subjects.
- Federation: `verify_federated_http_request(sender_did=…, request_method, request_url, headers, body, …)` checks that the request was signed by the sender's `ANPMessageService.serviceDid`.

### 3.2 `anp.openanp` (recommended server and client framework)

```python
from anp.openanp import (anp_agent, interface, information, AgentConfig, Information, Context,
                         RemoteAgent, create_agent_router, generate_ad, generate_ad_document,
                         generate_rpc_interface, resolve_base_url, RPCError, ...)
```

- `AgentConfig(name, did, description="", prefix="", tags=None, url_config=None, auth_config=None)`. `auth_config` is stored but never used (`types.py:102`). It does not enable authentication.
- `@anp_agent(config)` on a class. `Cls.router()` works on the class (instantiates with no arguments) or on an instance (`Cls(dep).router()`, use this form when the constructor takes arguments).
- `@interface` or `@interface(name=, description=, protocol=, mode="content"|"link", params_schema=, result_schema=)`.
  - Schemas are generated from type hints and Pydantic models. The description comes from the docstring's first line.
  - `mode="link"` serves a separate `/interface/<name>.json`.
  - `protocol="AP2/ANP"` emits `x-protocol`.
  - Method names must be unique per class.
- `ctx: Context` (detected by the name `ctx`/`context` or the type annotation) is injected and excluded from the schema. It exposes `ctx.did`, `ctx.session.get/set`, `ctx.request` and `ctx.auth_result`.
  - Sessions live in one global in-memory `SessionManager` keyed by `sha256(did)`, with a 60 min timeout.
  - Without auth middleware every caller gets `did="anonymous"` and therefore **the same session** (`autogen.py:165`).
- `@information(type, description, path=None, mode="url"|"content")` on methods, or a class attribute `informations = [Information(type, description, mode, path|url|file|content)]`.
- Optional `customize_ad(self, doc, base_url)` hook (sync or async) post-processes `ad.json`.

Generated routes under `prefix`:

- `GET /ad.json`
- `GET /interface.json` (content-mode methods)
- `GET /interface/{name}.json` (link-mode methods)
- `GET {info_path}` (information endpoints)
- `POST /rpc` (JSON-RPC 2.0, single and batch; notifications get no response)

`ad.json` (OpenANP, `utils.generate_ad_document`):

```json
{"protocolType":"ANP","protocolVersion":"1.0.0","type":"Product","url":"<base>/<prefix>/ad.json",
 "identifier":"<did>","name":"…","description":"…",
 "security":{"didwba":{"scheme":"didwba","in":"header","name":"Authorization"}},
 "brand":{"type":"Brand","name":"…"},"category":"Agent Service","sku":"<did>","created":"…Z",
 "interfaces":[{"type":"StructuredInterface","protocol":"openrpc","url":"<base>/<prefix>/interface.json","description":"…"}],
 "Infomations":[...]}
```

`interface.json`:

```json
{"openrpc":"1.3.2","info":{...},"methods":[{"name","description","params":[...],"result":{...},"x-protocol"?}],
 "servers":[{"name":"… Server","url":"<base>/<prefix>/rpc"}],
 "securityDefinitions":{"didwba_sc":{...}},"security":"didwba_sc"}
```

Note that FastANP emits a **different** AD shape: `"type":"AgentDescription"`, a `did` field, and `securityDefinitions` + `"security":"didwba_sc"`. The SDK has no single canonical ADP shape. Check against the ADP spec before choosing one.

RPC error mapping (`autogen.py:214-280`):

| Condition | Code |
|---|---|
| Unknown method | -32601 |
| `ValueError` (including from business code) | -32600 "Invalid Request" |
| `TypeError` | -32602 |
| Any other exception | -32603 with `str(e)` returned to the caller |
| Bad JSON | -32700 |

All responses use HTTP 200.

**Auth middleware** (`anp/openanp/middleware.py`), wired manually:

```python
from anp.openanp.middleware import create_auth_middleware
app.middleware("http")(create_auth_middleware(DidWbaVerifierConfig(...), exempt_paths=[...]))
```

- Default `EXEMPT_PATHS = ["/favicon.ico","/health","/docs","*/ad.json","/info/*","*/interface/*.json"]`. It does **not** exempt `*/interface.json`, so the content-mode interface doc requires auth. `RemoteAgent` signs every request anyway, so discovery still works for ANP clients.
- Behaviour: Host must be in `allowed_domains` → `verifier.verify_request(method, str(request.url), headers, body)` → sets `request.state.auth_result` and `request.state.did` → copies `response_headers` (token) onto the response.

**Client**

```python
agent = await RemoteAgent.discover("https://host/agent/ad.json", auth)   # auth: DIDWbaAuthHeader
agent.name, agent.method_names, agent.tools   # OpenAI function-tool format
await agent.add(a=1, b=2)                     # or await agent.call("add", a=1, b=2)
```

- Discovery reads embedded `StructuredInterface`+`content` from `ad.json`. Otherwise it fetches each `StructuredInterface`/`openrpc` `url`.
- The RPC URL is `servers[0].url` of the OpenRPC method or document.
- Raises `HttpError`, `RpcError`, `KeyError`, `ValueError` or `TypeError`.

### 3.3 `anp.anp_crawler`

- `ANPClient(did_document_path, private_key_path)`
  - `fetch_url(url, method, headers, params, body)` returns `{success, status_code, text, content_type, encoding, url, error?}`.
  - On a 401 it does one retry: it clears the Bearer token, or re-signs using the server's `WWW-Authenticate` nonce and `Accept-Signature` components.
  - `fetch(url)` returns `{success, data, error}`.
  - `call_jsonrpc(server_url, method, params, request_id=None)` returns `{success, result, error, request_id}`.
  - Bodies are serialised as compact JSON (`separators=(",",":")`), so the digest matches the bytes sent.
- `ANPCrawler(did_document_path, private_key_path, cache_enabled=True)`
  - `fetch_text`, `fetch_auto`, `fetch_image`, `fetch_video` and `fetch_audio` each return `(content_dict, interfaces_list)`.
  - `list_available_tools()`, `execute_tool_call(tool_name, args)` and `execute_json_rpc(endpoint, method, params)`.
  - Visited/cache helpers.
  - Converts OpenRPC (and embedded OpenRPC) into OpenAI tools. Meant for LLM tool use; it calls no LLM itself.
- `ANPInterface`, `ANPInterfaceConverter`, `ANPDocumentParser`.

### 3.4 `anp.fastanp` (older framework, still works)

`FastANP(app, name, description, agent_domain, did, owner=None, jsonrpc_server_path="/rpc", ..., enable_auth_middleware=False, auth_config=DidWbaVerifierConfig)`.

- `@anp.interface("/info/x.json", description=…)` registers a function.
- `anp.get_common_header(agent_description_path=…)` builds the AD header.
- `anp.interfaces[func].link_summary` and `.content` give interface entries.
- Context injection works as in OpenANP.
- Unlike OpenANP, FastANP wires the auth middleware itself when `enable_auth_middleware=True`.

### 3.5 `anp.proof`

- `generate_w3c_proof(document, private_key, verification_method, proof_purpose, proof_type, cryptosuite, domain, challenge, created)` and `verify_w3c_proof(document, public_key, expected_purpose=None)`.
  - Types: `EcdsaSecp256k1Signature2019`, `Ed25519Signature2020`, `DataIntegrityProof` with `eddsa-jcs-2022` / `didwba-jcs-ecdsa-secp256k1-2025`.
- `generate_object_proof` / `verify_object_proof` (Appendix-B, multibase `proofValue`).
- `generate_group_receipt_proof` / `verify_group_receipt_proof`.
- `generate_did_wba_binding` / `verify_did_wba_binding`.
- IM proofs: `generate_im_proof`, `verify_im_proof`, content-digest and signature-input helpers.
- RFC 9421 origin proof: `build_signed_request_object`, `generate_rfc9421_origin_proof`, `verify_rfc9421_origin_proof`, `TARGET_KIND_AGENT/GROUP/SERVICE`.

### 3.6 `anp.wns`

- `validate_handle`, `normalize_handle`, `parse_wba_uri`, `build_wba_uri`, `build_resolution_url`.
- `await resolve_handle(handle, timeout_seconds=10, verify_ssl=True)` returns a `HandleResolutionDocument` (`did`, `status`, `binding_generation`, `updated`). It raises `HandleNotFoundError` (404), `HandleGoneError` (410), `HandleMovedError` (301) or `HandleResolutionError`.
- `resolve_handle_from_uri`.
- `await verify_handle_binding(...)` returns a `BindingVerificationResult` (bidirectional handle↔DID check via the `ANPHandleService` service entry).
- `build_handle_service_entry`, `canonicalize_binding_generation`, `compare_binding_generations` (WNS 1.1 `binding_generation` is required).

### 3.7 `anp.ap2`

- Core: `build_mandate(contents, headers, iss, sub, aud, private_key, algorithm="ES256K", ttl_seconds=900, hash_field_name="content_hash")` returns `{"contents", "auth": <JWT>}`. `validate_mandate(mandate, public_key, algorithm, expected_audience, verify_time)` checks it. The content hash is JCS + SHA-256, base64url.
- Higher level: `build_cart_mandate` / `validate_cart_mandate`, `build_payment_mandate` / `validate_payment_mandate`, `build_payment_receipt`, `build_fulfillment_receipt`, `validate_credential`.
- Pydantic models: `CartMandate`, `PaymentMandate`, `PaymentRequest`, `QRCodePaymentData`, etc.
- Spec: `docs/ap2/ap2-flow.md`.

### 3.8 E2EE modules

- `anp.direct_e2ee` (current ANP-P5):
  - v1 runtime: `DirectE2eeSession` (X3DH-like setup with optional OPK, HKDF-SHA256, ChaCha20-Poly1305, `MAX_SKIP=1000`), `PrekeyManager`, `FileSessionStore`, `FileSignedPrekeyStore`.
  - `MessageServiceDirectE2eeClient(local_did, signing_private_key, signing_verification_method, static_key_agreement_private_key, static_key_agreement_id, rpc_client, did_document_resolver, session_store, signed_prekey_store)` with `publish_prekey_bundle`, `get_verified_prekey_bundle`, `send_text`, `send_json`, `process_incoming`, `decrypt_history_page`. It is synchronous; `rpc_client(method, params) -> dict` is supplied by you.
  - v2: wire models and builders only (`V2*`, `build_prekey_bundle_v2`, `verify_prekey_bundle_v2`, `*_request_v2` / `parse_*_v2`).
- `anp.e2e_encryption_hpke`: older HPKE (RFC 9180) private chat plus Sender-Key group chat (`GroupE2eeSession`). The DID helpers in `direct_e2ee` still import its `key_pair`.
- `anp.e2e_encryption_v2`: legacy ECDHE + AES-GCM handshake state machine. "Do not use for new P5."
- `anp.e2e_encryption`: legacy WebSocket, `did:anp:` format.

### 3.9 `anp.meta_protocol`

`MetaProtocol` and `ProtocolType`: LLM-driven protocol negotiation that generates requester/provider Python code. Needs Azure OpenAI settings in `.env` (see `.env.example`). Several TODOs remain unimplemented (test-case negotiation, error-fix negotiation, natural-language channel). Treat it as experimental.

### 3.10 `anp.utils`

`crypto_tool.py` (key generation, ECDH, AES), `did_generate.py` / `did_verify.py` (legacy), `llm/base_llm.py`, `llm_output_processer.py`, `log_base.py`.

---

## 4. Minimal agent server and DID-authenticated client

### 4.1 Identities

```python
# make_identity.py: run once per agent
import json, pathlib
from anp.authentication import create_did_wba_document

doc, keys = create_did_wba_document(
    hostname="client.example.com", path_segments=["agents", "alice"], enable_e2ee=False)
out = pathlib.Path("identity"); out.mkdir(exist_ok=True)
(out / "did.json").write_text(json.dumps(doc, indent=2))
(out / "key-1_private.pem").write_bytes(keys["key-1"][0])     # protect: chmod 600, or move to KMS
print(doc["id"])   # did:wba:client.example.com:agents:alice:e1_<fp>
# Publish did.json at https://client.example.com/agents/alice/e1_<fp>/did.json
```

For quick tests against the internet, the repo ships a public identity whose DID document is live at `https://didhost.cc/public/did.json` (HTTP 200 on 2026-10-30): `docs/did_public/public-did-doc.json` + `public-private-key.pem` (`did:wba:didhost.cc:public`). Everyone has that private key, so use it only for demos.

### 4.2 Server (OpenANP + DID-WBA middleware)

```python
# server.py   run: uvicorn server:app --host 0.0.0.0 --port 8000 --proxy-headers
import os
from fastapi import FastAPI
from anp.authentication import DidWbaVerifierConfig
from anp.openanp import AgentConfig, Context, anp_agent, interface
from anp.openanp.middleware import create_auth_middleware

@anp_agent(AgentConfig(
    name="Calculator",
    did="did:wba:agent.example.com:calculator",
    prefix="/agent",
    description="Adds two numbers",
))
class CalculatorAgent:
    @interface
    async def add(self, a: int, b: int, ctx: Context) -> dict:
        """Add two integers."""
        return {"sum": a + b, "caller": ctx.did}

app = FastAPI()
app.middleware("http")(create_auth_middleware(
    DidWbaVerifierConfig(
        jwt_private_key=open(os.environ["JWT_PRIVATE_KEY_PEM"]).read(),   # RS256 key pair
        jwt_public_key=open(os.environ["JWT_PUBLIC_KEY_PEM"]).read(),
        allow_legacy_didwba=False,
        emit_legacy_authorization_header=False,   # ANP-02: token only in Authentication-Info
        allowed_domains=["agent.example.com"],
    ),
    exempt_paths=["/health", "*/ad.json", "*/interface.json", "*/interface/*.json"],
))
app.include_router(CalculatorAgent.router())
```

### 4.3 Client

```python
# client.py
import asyncio
from anp.authentication import DIDWbaAuthHeader
from anp.openanp import RemoteAgent

async def main() -> None:
    auth = DIDWbaAuthHeader(did_document_path="identity/did.json",
                            private_key_path="identity/key-1_private.pem")
    agent = await RemoteAgent.discover("https://agent.example.com/agent/ad.json", auth)
    print(agent.method_names)              # ('add',)
    print(await agent.add(a=2, b=3))       # {'sum': 5, 'caller': 'did:wba:client.example.com:agents:alice:e1_…'}

asyncio.run(main())
```

### 4.4 Gotchas for this setup

- **HTTPS only for DID resolution.** The verifier resolves the caller's DID with `https://` hard-coded (`did_wba.py:1100`), and `DidWbaVerifierConfig` has no resolver option. For localhost tests the repo examples monkeypatch it:
  ```python
  import anp.authentication.did_wba_verifier as vm
  async def local_resolver(did): return KNOWN_DOCS.get(did)
  vm.resolve_did_wba_document = local_resolver
  ```
  (see `examples/python/did_wba_examples/e1_authenticate_and_verify.py` and `examples/python/rust_interop_examples/python_auth_server.py`).
- **Proxies.** Signature verification rebuilds `@target-uri` from `str(request.url)`, and `ad.json`/`interface.json` URLs come from `request.base_url`. Behind a TLS-terminating proxy, run uvicorn with `--proxy-headers --forwarded-allow-ips=…`. Otherwise `http://` vs `https://` breaks every signature and the published URLs.
- **Body reads in middleware.** The middleware reads `await request.body()` before `/rpc` reads `request.json()`. Starlette ≥0.28 caches the body so this works with the locked versions, but no repo test POSTs through the OpenANP auth middleware.
- **No token reuse in `RemoteAgent`.** `RemoteAgent.call` creates a new `ANPClient`, and so a new `DIDWbaAuthHeader`, on every call (`client/agent.py:99,234`). The issued Bearer token is never reused. Every call does a full signature, a server-side DID fetch with no cache, and a new aiohttp session. For throughput, keep one `ANPClient` and call `call_jsonrpc` directly, or wrap your own client around `DIDWbaAuthHeader`.

---

## 5. Python examples catalog (`examples/python/`)

| Folder | Files | Shows |
|---|---|---|
| `openanp_examples/` | `minimal_server.py` (74 lines), `minimal_client.py` (61), `advanced_server.py` (442), `advanced_client.py` (170), `chat_a.py`/`chat_b.py` (~440 each) | Minimal: Calculator `add`/`multiply` under `/agent`, no auth. Advanced: content and link modes, `Context`/session, static and dynamic `Information`, constructor DI, `customize_ad`. Chat: two LLM agents that are each both server and client (P2P). |
| `did_wba_examples/` | `create_did_document.py`, `validate_did_document.py`, `e1_authenticate_and_verify.py`, `DID_WBA_AUTH_GUIDE(.en).md` | Offline e1 identity → HTTP signature → verifier (local resolver patch) → JWT issued → Bearer reuse. This is the best auth reference. |
| `fastanp_examples/` | `simple_agent.py`, `simple_agent_with_context.py`, `hotel_booking_agent.py`, `config_example.py`, `test_hotel_booking_client.py`, shell scripts | FastANP plugin with `enable_auth_middleware=True` and a `DidWbaVerifierConfig` (RS256 keys from `docs/jwt_rs256/`), custom ad.json routes, Pydantic params. |
| `minimal_example/` | `minimal_anp_server.py`, `minimal_anp_client.py`, `minimal_anp_agent.py` | FastANP server; `ANPClient.fetch()` client; pydantic_ai agent using `ANPClient` as tools. |
| `anp_crawler_examples/` | `simple_amap_example.py`, `amap_crawler_example.py` | Crawl the live `https://agent-connect.ai/mcp/agents/amap/ad.json` with the public DID, list tools, `execute_tool_call`. |
| `ap2_examples/` | `ap2_complete_flow.py` (675), merchant agent/server, shopper agent/client | Full AP2 flow: CartMandate (merchant ES256K) → PaymentMandate (user) → receipts, over HTTP with DID auth. |
| `proof_examples/` | `proof_example.py` | W3C Data Integrity proofs (Chinese comments). |
| `wns_examples/` | `resolve_handle.py`, `verify_binding.py` | Handle normalisation, `wba://` parsing, resolution (needs a live provider). |
| `e2e_encryption_hpke_examples/` | basic private chat, group chat, key manager, error handling | Legacy HPKE module. |
| `e2e_encryption_v2_examples/` | basic handshake, key manager, error handling | Legacy v2 module. |
| `rust_interop_examples/` | `python_auth_server.py`, `verify_rust_fixture.py` | Stdlib HTTP server around `DidWbaVerifier` (HS256), used by Rust tests. |
| `negotiation_mode/` | `negotiation_alice.py`, `negotiation_bob.py`, `config.py`, `utils.py` | Meta-protocol with Azure OpenAI. |

Representative snippet (verbatim, `examples/python/did_wba_examples/e1_authenticate_and_verify.py`):

```python
        authenticator = DIDWbaAuthHeader(
            did_document_path=str(did_document_path),
            private_key_path=str(private_key_path),
        )
        signature_headers = authenticator.get_auth_header(
            REQUEST_URL,
            force_new=True,
            method=REQUEST_METHOD,
            headers=REQUEST_HEADERS,
            body=REQUEST_BODY,
        )
        ...
            first_result = await verifier.verify_request(
                method=REQUEST_METHOD,
                url=REQUEST_URL,
                headers={**REQUEST_HEADERS, **signature_headers},
                body=REQUEST_BODY,
            )
        ...
        access_token = authenticator.update_token(
            REQUEST_URL,
            first_result["response_headers"],
        )
        bearer_headers = authenticator.get_auth_header(REQUEST_URL)
```

Verbatim from `examples/python/fastanp_examples/hotel_booking_agent.py`:

```python
auth_config = DidWbaVerifierConfig(
    jwt_private_key=jwt_private_key,
    jwt_public_key=jwt_public_key,
    jwt_algorithm="RS256",
    allowed_domains=["localhost", "0.0.0.0", "127.0.0.1"]
)
anp = FastANP(
    app=app,
    name="Hotel Booking Assistant",
    ...
    did="did:wba:hotel.example.com:service:booking",
    ...
    enable_auth_middleware=True,  # Enable auth for demo
    auth_config=auth_config
)
```

Verbatim from `examples/python/anp_crawler_examples/simple_amap_example.py`:

```python
    crawler = ANPCrawler(
        did_document_path=str(project_root / "docs" / "did_public" / "public-did-doc.json"),
        private_key_path=str(project_root / "docs" / "did_public" / "public-private-key.pem")
    )
    url = "https://agent-connect.ai/mcp/agents/amap/ad.json"
    content_json, interfaces_list = await crawler.fetch_text(url)
    tools = crawler.list_available_tools()
    result = await crawler.execute_tool_call(tool_name, test_arguments)
```

Other-language examples: `golang/examples/{create_did_document,direct_e2ee,proof,wns}`; `rust/examples/{create_did_document,external_signer_e1,interop_cli,interop_server,proof_example,wns_example,direct_e2ee_*}.rs`; `typescript/ts_sdk/examples/{authentication,did-wba-http-server,did-wba-http-client,proof,wns}.mjs` plus `python_to_ts_did_wba_client.py`; `dart/example/*`; `java/anp-examples/...` (calculator, hotel, Spring Boot, crawler, AP2/negotiation concept classes). `docs/examples.md` has the run commands.

---

## 6. Other language SDKs

### Go (`golang/`, `github.com/agent-network-protocol/anp/golang`, v1.0.7)

- Pure Go (btcec secp256k1, gowebpki/jcs, x/crypto); no cgo, by policy.
- `authentication`:
  - `CreateDidWBADocument(hostname, DidDocumentOptions{PathSegments,…})` returns a `DidDocumentBundle` (`.DidDocument`, `.Keys[VMKeyAuth].PrivateKeyPEM`).
  - `GenerateHTTPSignatureHeaders`, `VerifyHTTPMessageSignature`, `GenerateAuthHeader`, `VerifyAuthHeaderSignature`.
  - `ResolveDidDocument(WithOptions)` (with `BaseURLOverride`).
  - `NewDidWbaVerifier(DidWbaVerifierConfig{JWTPrivateKey,…, DidResolutionOptions, ExternalNonceValidator})` with `VerifyRequest(ctx, …)` and `VerifyRequestWithDidDocument` (pre-resolved document).
  - `NewDIDWbaAuthHeader(docPath, keyPath, authMode)` with `GetAuthHeader`, `UpdateToken`, `ShouldRetryAfter401`, `GetChallengeAuthHeader`.
  - Device Manifest, DID transitions, did:web lifecycle, `VerifyFederatedHTTPRequest`.
- `proof`: all proof types.
- `wns`: validate, resolve, binding.
- `direct_e2ee`: v1 runtime + v2 wire.
- `group_e2ee`: P6 v2 wire models and AAD, plus an `exec_provider` contract. No in-process MLS.
- There is no HTTP server middleware. You write a `net/http` handler around `VerifyRequest`.
- No ADP/OpenRPC/crawler.
- 108 `func Test…`; integration tests run Rust fixtures through `cargo` (skipped if cargo is missing). Docs: `golang/docs/api.md`, `direct_e2ee-guide.md`, `release-notes.md`.

### Rust (`rust/`, crate `anp`, v1.0.7)

- Most complete cryptographically. Same auth surface as Go, plus:
  - external-signer two-phase APIs (`build_unsigned_e1_did_document`, `prepare_legacy_did_wba_auth_header` / `complete_…`);
  - `DidWbaVerifier::new(DidWbaVerifierConfig{… did_resolution_options, external_nonce_validator})` with `verify_request` (async; the `network` feature uses reqwest + rustls).
- Direct E2EE v2 runtime `V2DirectE2eeSession` (exact-device binding, persisted state, redacted `Debug`).
- Group E2EE via OpenMLS 0.8 (`operations::typed` v1, `operations::v2` persistent with a write-ahead journal and `reconcile_pending_v2`, SQLite stores `CompatDataDirStore` / `ImCoreSqliteGroupMlsStore`). Docs label P6 "hidden/test-only" and say the v2 draft codepoint is release-blocked.
- `examples/interop_server.rs` is a minimal `tiny_http` server around the verifier. There is no axum/actix middleware.
- No ADP/OpenRPC/crawler.
- 243 test attributes, including Python interop: `python_interop_tests.rs`, and `python_network_interop_tests.rs`, which spawns the Python auth server.

### TypeScript (`typescript/ts_sdk/`, `@awiki/anp-typescript-sdk` 0.9.5)

- Node ≥20. Dependencies: `@noble/curves`, `bs58`, `canonicalize`, `jose`.
- Modules:
  - `authentication`: `createDidWbaDocument` / `createDidDocument`, `generateHttpSignatureHeaders` / `createSignatureHeaders`, `verifyHttpMessageSignature`, `DIDWbaAuthHeader`, `DidWbaVerifier({jwtPrivateKey, jwtPublicKey, jwtAlgorithm, didResolver, …})`, device manifest, federation.
  - `proof`: W3C, IM, RFC 9421 origin. No object, group-receipt or did_wba_binding exports.
  - `wns`.
  - `im`: `createAwikiImClient`, AWiki-specific registration, messaging and attachments.
- The example `did-wba-http-server.mjs` uses `node:http` with the verifier and an injected `didResolver`.
- No ADP/OpenRPC/crawler.
- 71 vitest cases including `rust-interop.test.ts`.

### Dart (`dart/`, pub `anp` 0.8.7)

- Pure Dart (`crypto`, `pointycastle`, `pinenacl`, `http`), Flutter-compatible.
- Covers codecs, keys, authentication (create, sign, verify), proofs, WNS, and Direct E2EE v2 wire only. Its README says X3DH is "intentionally not exported".
- `DidWbaVerifier` (25 lines) only checks the signature against a DID document you pass in. It has no resolution, JWT, nonce or time-window checks. `DidWbaAuthenticator` (23 lines) only signs. Dart works as a client signer, not as a server verifier.
- Interop is checked against Go through `tool/interop.dart` plus `go run ./cmd/anp-interop`.
- 51 tests.

### Java (`java/`, local 1.0.0, not published)

- `anp4j`:
  - `DIDWBA.createDIDWBADocument` (plain secp256k1);
  - `generateAuthHeader` / `verifyAuthHeaderSignature` (legacy `DIDWba` header only);
  - `DIDWbaAuthHeader` (legacy header + Bearer cache);
  - `RemoteAgent.discover/call(Async)`, `ANPClient`, `ANPCrawler`, `OpenRpcGenerator`, `AgentDescription`, `JsonRpc`.
- `anp-spring-boot-starter`: `@AnpAgent`, `@Interface`, `@Information`, `@Param`, `AnpEndpointController` (ad.json / interface / rpc), `DidWbaAuthFilter`. The filter parses exactly 5 comma-separated parts of a legacy header and does not issue tokens.
- **No RFC 9421 HTTP Message Signatures, no e1/k1 binding, no proofs, no WNS.** Not interoperable with current-default Python/Go/Rust/TS clients and servers (`http_signatures` mode and `allow_legacy_didwba=False` deployments).
- 106 `@Test`.

---

## 7. Tests and conformance

| Area | Location | Static count | Notes |
|---|---|---|---|
| Python unit tests | `anp/unittest/*` | authentication 100, wns 88, proof 79, e2e_hpke 148, e2e_v2 62, openanp 60, fastanp 54, ap2 29, direct_e2ee 14, anp_crawler 14, rust_interop 5, release_tools 10 | Plus `anp/anp_crawler/test` (21). Total ~690 `def test_`. |
| Python system/e2e | `tests/system/test_e1_authentication_example.py`, `tests/e2e/test_e1_authentication_example_cli.py` | 1 + 2 | Run the e1 examples in-process and via `uv run`. |
| PyPI back-compat | `anp/unittest/authentication/test_pypi_client_compat.py` | — | Older client shapes (baseline 0.7.1 in `tests/rust_interop_config.json`). |
| OpenANP auth | `anp/unittest/openanp/test_auth_middleware_compat.py` | 1 | Legacy k1 header + Bearer follow-up through the middleware (GET only). No RFC 9421 POST through the middleware. |
| Cross-language shared vectors | `testdata/*` | — | Device Manifest (Rust, Python, Go, Dart, TS), DID transition (Python, Go, Rust), P5 v1 (Go, Rust), P5 v2 wire (Rust, Python, Go, Dart), P6 did_wba_binding golden (Go, Rust), P6 v2 wire (Rust, Go), WNS binding_generation (all five that have WNS). |
| Live interop | Rust `python_network_interop_tests.rs` + Python `test_network_interop.py`; Go `integration/` (Rust fixtures, Python direct-E2EE fixtures); TS `rust-interop.test.ts`; Dart↔Go `anp-interop` CLI | — | Python↔Rust is a real HTTP round trip (client↔server, both directions). |
| Go | 108 tests | | |
| Rust | 243 tests | | Including real-OpenMLS multi-device gates. |
| TS | 71 tests | | |
| Dart | 51 tests | | |
| Java | 106 tests | | No shared-vector participation. |

Not covered by tests:

- No test runs the ANP-02 test vectors in `01-identity-auth.md` §7 (`examples/did-authentication-vnext/` in the protocol repo) against the SDK verifiers.
- No tests for ADP/OpenRPC document conformance against a schema.
- No load or concurrency tests for the replay cache.
- CI runs only the manual Rust↔Python interop workflow. Release tooling skips tests by default (AGENTS.md: "Publication does not run test suites by default").

---

## 8. `skills/anp-agent`

A Claude Code style skill (Chinese `SKILL.md`, triggered by "ANP / call Agent / hotel / courier / maps").

- `scripts/anp_cli.py` (259 lines) uses `ANPCrawler` and offers `connect <ad_url>`, `call <id|ad_url> <method> '<json>'`, `list`, `add`, `remove`.
- `config/agents.json` registers live agents:
  - amap: `https://agent-connect.ai/mcp/agents/amap/ad.json`
  - kuaidi, hotel and juhe on `agent-connect.ai`
  - navigation: `https://agent-search.ai/agents/navigation/ad.json`
- `setup.sh` installs `anp` and creates a throwaway `did:wba:local:user:<rand>` secp256k1 identity with openssl. That DID cannot be resolved, so strict servers reject it; the script suggests registering at didhost.cc.
- `requirements.txt` pins `anp>=0.6.1`.
- Useful as a live smoke target list and as a pattern for an LLM-tool wrapper around ANP. Not production code.

---

## 9. Gaps, bugs and deviations from ANP-02

File:line references are against repo HEAD `bab0a0e` (1.0.6). Several items apply to every SDK, because Go, Rust and TS mirror the Python logic.

### Spec conformance (ANP-02 HTTP auth; see `01-identity-auth.md` §3)

1. **Token in the `Authorization` response header by default.** `DidWbaVerifierConfig.emit_legacy_authorization_header=True` (`did_wba_verifier.py:67`) puts `Authorization: Bearer …` on responses. ANP-02 §3.2.3 says MUST use `Authentication-Info` and MUST NOT use an `Authorization` response header. Set it to `False`. Go, Rust and TS have the same default.
2. **`@signature-params` is re-serialised, not taken verbatim.** The verifier rebuilds the params in a fixed order `created;expires;nonce;keyid` (`http_signatures.py:115`; same in Go `http_signatures.go:194`, Rust `:386`, TS `:190`). A signer from another stack that orders params differently or adds `alg` or `tag` fails verification. This violates RFC 9421 §2.3.
3. **Covered-component policy is not enforced.** The verifier accepts any component list. ANP-02 requires `@method`, `@target-uri`, and `content-digest` when there is a body. If a signer leaves `content-digest` uncovered, an attacker can swap the body and recompute the unsigned digest. The SDK's own signer covers these components by default.
4. **Single-signature parsing only.** The regexes accept one `label=(…)` entry, so multiple signatures in one header are not supported.
5. **Server-issued challenge nonce is not implemented server-side.** The `WWW-Authenticate` challenge has no `nonce`. Only client-chosen nonce replay is supported. `require_nonce_for_http_signatures=True` rejects nonce-less requests, which is stricter than ANP-02's MAY.
6. **The replay cache is a per-process dict** (`did_wba_verifier.py:76`), keyed `did:nonce`. It is not shared across workers or pods. Use `external_nonce_validator` with Redis `SET NX EX`.
7. **Error codes differ from the spec.**
   - A digest mismatch is reported as `invalid_signature`, where the spec says `invalid_content_digest`.
   - A key that is not in `authentication` returns **403** with no challenge headers (`:370`), where the spec says 401 `invalid_verification_method`.
   - The legacy invalid-signature path also returns 403.
8. **No `deactivated` / `successorDid` → 409 `did_superseded` handling** in any SDK verifier, even though `did_transition` helpers exist.
9. **Legacy `DIDWba` header accepted by default** (`allow_legacy_didwba=True`). Disable it in production.
10. **The `ad.json` `security` block** advertises `{"scheme":"didwba","in":"header","name":"Authorization"}`, while the actual default scheme is RFC 9421 `Signature-Input`/`Signature`. That is misleading for third-party clients.

### Python implementation issues

11. **OpenANP never wires auth.** `AgentConfig.auth_config` is unused (`types.py:102`; only `refactor-plan.md` mentions wiring it). An `@anp_agent` server is **unauthenticated** unless you add `create_auth_middleware` yourself.
12. **Shared anonymous session.** Without the middleware, every caller's `ctx.did` is `"anonymous"` and they all share one `Session` (`autogen.py:165`). Session data can leak between callers.
13. **Default `EXEMPT_PATHS` miss `*/interface.json`** (`openanp/middleware.py:24-31`), while `*/interface/*.json` (link mode) is exempt.
14. **Silent fallback to unauthenticated requests in `ANPClient`.** If DID or key loading fails in `ANPClient.__init__`, `auth_client` becomes `None` (`anp_client.py:105`). Signing errors are logged and swallowed (`:168`). In both cases requests go out **unauthenticated** with no exception.
15. **`ANPClient` treats only HTTP 200 as success** (`anp_client.py:281`); 201 and 204 count as failures.
16. **Import-time `sys.path` hack** in `anp_client.py:20`.
17. **No token reuse in `RemoteAgent`**: a new `ANPClient` per call (`client/agent.py:99,234`), as described in §4.4.
18. **`DIDWbaAuthHeader` limitations.** It re-reads the private key from disk on every signature. It accepts only file paths: no in-memory key object, KMS, or HSM unless you drop down to `generate_http_signature_headers` with a callback. It caches tokens by hostname without port (`did_wba_authenticator.py:48-51`), so two services on one host share a cache slot.
19. **DID resolution limits.** No DID-document cache. HTTPS is hard-coded in `resolve_did_wba_document` (`did_wba.py:1100`). The verifier has no resolver injection, so the examples monkeypatch a module global. It returns `None` instead of raising, which loses the error cause. `# TODO: Add DNS-over-HTTPS support` at `did_wba.py:1108`.
20. **Information disclosure in RPC errors.** Any unexpected exception returns `str(e)` as -32603 (`autogen.py:277`). Business `ValueError`s are reported as -32600 "Invalid Request" (`:264`).
21. **Inline AD interfaces cannot be read by the SDK's own client.** `generate_ad_document(inline_methods=…)` emits `{"type":"InlineOpenRPC","definition":…}` (`utils.py:91`). `RemoteAgent`'s `parse_agent_document` only understands `StructuredInterface` + `content` or `url` (`client/openrpc.py:97-101`).
22. **Two AD shapes in one SDK** (OpenANP `type:"Product"` vs FastANP `type:"AgentDescription"`). Both use the `"Infomations"` key; FastANP's model comments that the ANP spec itself has this typo.
23. **Proxy-unaware URL building.** `resolve_base_url` uses `request.base_url` and only rewrites `0.0.0.0`. Generated URLs are wrong behind proxies without `--proxy-headers`.
24. **Python floor overstated**: declared ≥3.8, effectively ≥3.9/3.10 (`types.py:481`).
25. **TODO/FIXME inventory:**
    - `e2e_encryption/wss_message_sdk.py:20,187,207,243`, `short_term_key_generater.py:404` (legacy E2EE error handling);
    - `meta_protocol/meta_protocol.py:318,329,341` (unimplemented negotiation branches);
    - `protocol_negotiator.py:372,399`;
    - `code_generator.py:139-141` (hard-coded versions);
    - `utils/llm/base_llm.py:28`;
    - `did_wba.py:1108`.
    - `NotImplementedError` appears only in X25519 `verify_signature` / `encode_signature`, which is expected.

### Documentation drift

26. Documentation drift:
    - README says registry status was "checked 2026-09-24 … 1.0.5", but registries are at 1.0.7.
    - `CLAUDE.md` describes `DidWbaVerifier` as "RS256 JWT signature verification" and the auth flow as "generate JWT auth headers". Neither is accurate.
    - `AGENTS.md` references non-existent `examples/ping_pong.py` and `anp.meta_protocol.cli`.
    - NOTICE has a likely year typo (2025 vs 2026).

---

## 10. Release and version status

- Fast-moving. 1.0.x shipped 7 times between 2026-09-07 and 2026-10-22. Breaking-ish behaviour changes land in patch releases, for example "authentication relationship now required" and "WNS `binding_generation` now required" (README capability table).
- Python, Go and Rust are coordinated (same `X.Y.Z`; Go tag `golang/vX.Y.Z`). TS 0.9.5 and Dart 0.8.7 lag and use separate versions. Java is unpublished.
- Group E2EE (P6 v2) is explicitly release-blocked and "hidden/test-only". Direct E2EE public discovery is "off until a separate discovery/security decision".
- `anp.openanp.__version__ = "0.0.2"` and `anp.fastanp.__version__ = "0.2.0"` are internal sub-versions that signal OpenANP's relative immaturity next to the core.

---

## 11. Recommendations

1. **Use the Python SDK (`anp[api]==1.0.7`, pinned) for the application layer.** It is the only SDK with ADP `ad.json`, OpenRPC generation, a JSON-RPC server, a remote-agent client and crawler, and AP2. Its identity and auth core (`anp.authentication`, `anp.proof`, `anp.wns`) is mature and vector-tested against Go and Rust.
2. **Treat OpenANP as scaffolding, not a hardened framework.** Use the decorators for schema, AD and RPC generation. Own these pieces yourself:
   - a thin ASGI auth middleware around `DidWbaVerifier`, with legacy off, `emit_legacy_authorization_header=False`, an enforced coverage policy, a Redis nonce store via `external_nonce_validator`, and correct proxy/base-URL handling;
   - a cached, injectable DID resolver (wrap `resolve_did_document` with `base_url_override` for dev, plus a TTL cache);
   - an RPC error mapper that doesn't leak `str(e)`;
   - a pooled client that reuses Bearer tokens (wrap `DIDWbaAuthHeader` + one `aiohttp.ClientSession`, or use `generate_http_signature_headers` with a KMS-backed `sign_callback`).
3. **Choose Rust for crypto-heavy or E2EE components.** It is the most rigorous SDK (external signer, Direct E2EE v2 runtime, OpenMLS). Go is the best fit for a lightweight pure-Go verifier or sidecar. Neither offers an agent framework.
4. **TS** is fine for Node identity, signing, verification and WNS. **Dart** is fine for mobile signing and WNS, but its verifier is only a facade. **Avoid Java** for anything that must interoperate with current defaults (no RFC 9421).
5. **Add conformance gates the SDK lacks.** Run the ANP-02 vectors from the protocol repo (`01-identity-auth.md` §7) against whichever verifier you deploy. Add tests for signature-params ordering, covered components, replay under concurrency, 401/403 codes, and `Authentication-Info`-only token delivery.
6. **Decide the ADP shape explicitly** against the ADP spec instead of inheriting OpenANP's `Product` shape or FastANP's `AgentDescription` shape. Use `customize_ad` or your own route to emit it.
