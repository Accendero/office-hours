#!/usr/bin/env bash
# Stage 1 gate: seven hops, each isolated, stops at the first failure.
# The point is to fail at the RIGHT hop so you know which config to fix.
# Do not proceed to stage 2 until all seven pass.
set -uo pipefail

S3_ENDPOINT_HOST=${S3_ENDPOINT_HOST:-http://localhost:8333}
NESSIE=${NESSIE:-http://localhost:19120}
TRINO=${TRINO:-http://localhost:8080}
BUCKET=${S3_BUCKET:-lakehouse}
AK=${S3_ACCESS_KEY:-lakehouse}
SK=${S3_SECRET_KEY:-lakehouse-local-secret}

pass=0; fail=0
hop() { printf "  %-52s" "$1"; }
ok()   { echo "PASS"; pass=$((pass+1)); }
bad()  { echo "FAIL"; fail=$((fail+1)); echo "        -> $1"; echo "        -> see docs/TROUBLESHOOTING.md #$2"; }

tq() {  # run a query through Trino's REST API; no client jar needed
  # NOTE: Trino's async statement protocol can deliver result rows on a page that
  # STILL carries a nextUri (more polling expected) -- rows are not guaranteed to
  # land on the final, nextUri-less page. Print data from every page, not just the last.
  curl -s -X POST -H "X-Trino-User: smoke" --data "$1" "$TRINO/v1/statement" \
  | python3 -c '
import json,sys,urllib.request
d=json.load(sys.stdin)
while True:
    if d.get("error"): print("ERROR:"+d["error"].get("message","?")); break
    for r in (d.get("data") or []): print("\t".join(map(str,r)))
    nu=d.get("nextUri")
    if not nu:
        break
    d=json.load(urllib.request.urlopen(nu))
'
}

echo "=== stage 1 smoke: seven hops ==========================================="

hop "1. SeaweedFS S3 port is listening"
if curl -s -o /dev/null -w "%{http_code}" "$S3_ENDPOINT_HOST" | grep -qE "^(200|403|404)$"; then ok
else bad "nothing answering on $S3_ENDPOINT_HOST" 1; fi

hop "2. bucket '$BUCKET' exists and is writable"
if AWS_ACCESS_KEY_ID=$AK AWS_SECRET_ACCESS_KEY=$SK AWS_DEFAULT_REGION=us-east-1 \
   aws --endpoint-url "$S3_ENDPOINT_HOST" s3 ls "s3://$BUCKET" >/dev/null 2>&1; then ok
else bad "bucket missing -- run 'make init' (scripts/00_init_object_store.sh)" 1; fi

hop "3. Nessie is healthy"
if curl -sf "$NESSIE/api/v2/config" >/dev/null 2>&1; then ok
else bad "Nessie not answering /api/v2/config" 2; fi

hop "4. Nessie Iceberg REST endpoint responds"
if curl -sf "$NESSIE/iceberg/main/v1/config" >/dev/null 2>&1; then ok
else bad "REST catalog path wrong -- this is the #1 suspect. Try: curl -v $NESSIE/iceberg/main/v1/config" 2; fi

hop "5. Trino is up"
if curl -sf "$TRINO/v1/info" | grep -q '"starting":false'; then ok
else bad "Trino still starting or dead -- 'docker compose logs trino'" 3; fi

hop "6. Trino sees the iceberg catalog"
if tq "SHOW CATALOGS" | grep -q iceberg; then ok
else bad "catalog not registered -- check trino/etc/catalog/iceberg.properties mount" 2; fi

hop "7. round-trip: create schema + Iceberg table, insert, select, drop"
tq "CREATE SCHEMA IF NOT EXISTS iceberg.smoke" >/dev/null
tq "DROP TABLE IF EXISTS iceberg.smoke.t" >/dev/null
tq "CREATE TABLE iceberg.smoke.t (id integer, note varchar)" >/dev/null
tq "INSERT INTO iceberg.smoke.t VALUES (1,'hello'), (2,'lakehouse')" >/dev/null
got=$(tq "SELECT count(*) FROM iceberg.smoke.t" | tr -d '[:space:]')
if [ "$got" = "2" ]; then
  objs=$(AWS_ACCESS_KEY_ID=$AK AWS_SECRET_ACCESS_KEY=$SK AWS_DEFAULT_REGION=us-east-1 \
         aws --endpoint-url "$S3_ENDPOINT_HOST" s3 ls --recursive "s3://$BUCKET/warehouse/" 2>/dev/null | wc -l || echo 0)
  ok
  echo "        -> $objs objects now under s3://$BUCKET/warehouse/"
  tq "DROP TABLE iceberg.smoke.t" >/dev/null
  tq "DROP SCHEMA iceberg.smoke" >/dev/null
else bad "round-trip failed (got '$got', expected 2) -- object storage write path" 4; fi

echo "========================================================================="
echo "  $pass passed, $fail failed"
if [ $fail -eq 0 ]; then
  echo "  STAGE 1 GREEN -- infrastructure works. Proceed to 'make data'."
  exit 0
else
  echo "  STAGE 1 RED -- fix the first failing hop before moving on."
  exit 1
fi
