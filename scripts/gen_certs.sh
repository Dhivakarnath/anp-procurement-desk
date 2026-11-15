#!/usr/bin/env bash
# Local CA + HTTPS certs for *.test hosts. Certificate checks stay on.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="${CERT_DIR:-$ROOT/certs}"
mkdir -p "$CERT_DIR"
CA_KEY="$CERT_DIR/ca.key"
CA_CRT="$CERT_DIR/ca.crt"
SRV_KEY="$CERT_DIR/server.key"
SRV_CRT="$CERT_DIR/server.crt"

if [[ -f "$CA_CRT" && -f "$SRV_CRT" ]]; then
  echo "certs already present in $CERT_DIR"
  exit 0
fi

openssl genrsa -out "$CA_KEY" 4096
openssl req -x509 -new -nodes -key "$CA_KEY" -sha256 -days 3650 \
  -out "$CA_CRT" -subj "/CN=ANP Desk Local CA"

openssl genrsa -out "$SRV_KEY" 2048
openssl req -new -key "$SRV_KEY" -out "$CERT_DIR/server.csr" \
  -subj "/CN=anp.desk.local"

cat > "$CERT_DIR/san.cnf" <<'EOF'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = buyer.test
DNS.2 = market.test
DNS.3 = s1.test
DNS.4 = s2.test
DNS.5 = s3.test
DNS.6 = app.test
DNS.7 = localhost
EOF

openssl x509 -req -in "$CERT_DIR/server.csr" -CA "$CA_CRT" -CAkey "$CA_KEY" \
  -CAcreateserial -out "$SRV_CRT" -days 825 -sha256 -extfile "$CERT_DIR/san.cnf"

chmod 600 "$CA_KEY" "$SRV_KEY"
chmod 644 "$CA_CRT" "$SRV_CRT"
echo "wrote CA and server cert to $CERT_DIR"
