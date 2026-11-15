# ANP procurement desk

**Repo:** [github.com/Dhivakarnath/anp-procurement-desk](https://github.com/Dhivakarnath/anp-procurement-desk)

One Buyer, a marketplace, and three suppliers (S1, S2, S3). Bedrock phrases language only. Code owns price, lead time, signatures, ranking, and whether an order may be sent.

## Prerequisites

- Docker and Docker Compose
- OpenSSL and Python 3.12+ (for key/cert generation)
- AWS credentials in your shell for Bedrock in `us-east-1` (never written into this repo)
- Local DNS: add to `/etc/hosts`:

```
127.0.0.1 buyer.test market.test s1.test s2.test s3.test app.test
```

Trust `certs/ca.crt` in your OS/browser keychain so HTTPS checks stay on.

## Start

```bash
chmod +x scripts/gen_certs.sh
./scripts/gen_certs.sh
python3 scripts/gen_keys.py
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080). The page talks to the Buyer at `http://localhost:8001`. Agents still sign and verify each other over `https://*.test` inside Docker, so the browser does not need a hosts entry or a trusted certificate.

## Expected flows

1. **10-day bolts** — S1 offers a contract price that meets the date; S2 refuses on lead time; ranking keeps S1.
2. **30-day bolts** — change need-by to 30 days and re-run; S2 can meet the date and may rank if cheaper on list/volume terms that still lose to S1’s contract, or compete when quantity/terms change.
3. **Unmatched part** — search something nobody sells; marketplace returns nobody.

## Roles

| Host | Role |
|------|------|
| `buyer.test` | Buyer session API + Haiku extract/rank phrasing |
| `market.test` | Catalog search only |
| `s1.test` | Existing supplier · contract book · stock for short lead |
| `s2.test` | List price · longer lead |
| `s3.test` | Shaft seal · requires `compound` before pricing |
| `app.test` | Story UI |

Credentials for Bedrock come from the process environment via `boto3.client("bedrock-runtime", region_name="us-east-1")`. They are not in source, images, or Compose values.
