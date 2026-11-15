#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

./scripts/gen_certs.sh
python3 scripts/gen_keys.py

if ! grep -q 'buyer.test' /etc/hosts 2>/dev/null; then
  echo "Add this line to /etc/hosts (once):"
  echo "127.0.0.1 buyer.test market.test s1.test s2.test s3.test app.test"
  echo "Then trust certs/ca.crt in your OS keychain."
fi

docker compose up --build "$@"
