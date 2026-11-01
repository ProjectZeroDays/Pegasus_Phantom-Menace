#!/usr/bin/env bash
set -euo pipefail
BASE="http://127.0.0.1:${PEGASUS_PORT:-5001}"

curl -sf "$BASE/api/health"
curl -sf "$BASE/api/setup/state" >/dev/null
curl -sf "$BASE/api/ai/status" >/dev/null
curl -sf "$BASE/api/delivery/health" >/dev/null

# unsigned beacon must be rejected
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/beacon/beacon" -H 'X-Dna: t')
[ "$code" = "401" ] || { echo "beacon accepted unsigned ($code)"; exit 1; }

python scripts/verify.py
echo "smoke ok"
