# Troubleshooting

Numbered to match the hints printed by `scripts/smoke.sh`. Work the hops in order — the
smoke test is designed to fail at the *right* hop so you know which config to touch.

---

## 0. Python environment — `make deps`

**`pip install -r requirements.txt` fails with `externally-managed-environment`**

Debian/Ubuntu 24.04+ blocks system-wide pip installs (PEP 668). Do not pass
`--break-system-packages` — it installs the pinned versions here straight into the system
Python and can break Ubuntu's own tooling. Use a venv instead:
```bash
python3 -m venv .venv
source .venv/bin/activate
make deps
```
`make` inherits the activated shell's `PATH`, so every later target (`bronze`, `gate`,
`train`, ...) keeps using `.venv` automatically as long as it's activated in whatever shell
runs `make`.

**`pip install -r requirements.txt` fails with `ResolutionImpossible` mentioning `fsspec`,
`s3fs`, or `botocore`**

This is not a real conflict in the versions pinned in `requirements.txt` today, but if you
bump `boto3` or the `pyiceberg` version, you can reintroduce it, so it's worth understanding.
The actual cause: `aiobotocore` (pulled in transitively by `s3fs`, which `pyiceberg[s3fs]`
depends on) always trails `boto3`/`botocore`'s release cadence by weeks to months, and pins
`botocore` to a narrow window per release. Two ways this bites:

- The pip-installed **`awscli` v1 package hard-pins an exact `botocore`** version (it does
  not use a range). If that exact version isn't inside whatever window the current
  `aiobotocore` supports, resolution is impossible *no matter what `boto3` version you pick*
  — which is why `awscli` is deliberately not in `requirements.txt`. Install the standalone
  **AWS CLI v2** binary instead (not via pip) for the `aws` calls in `smoke.sh` and
  `00_init_object_store.sh`:
  ```bash
  curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  unzip -q /tmp/awscliv2.zip -d /tmp && sudo /tmp/aws/install
  ```
- If you bump `boto3`, its pinned `botocore` range must land inside the range the resolved
  `aiobotocore`/`s3fs` version supports. Check what's currently installed with
  `pip show boto3 botocore aiobotocore s3fs`, and cross-check the `boto3` release you want
  against `aiobotocore`'s supported `botocore` window on PyPI before pinning it.

---

## 0.5 Windows/WSL2 — the whole stack disappears mid-session

**Symptom:** all five containers show `Exited (255)` simultaneously, `docker compose ps`
comes back empty until you `docker compose up -d` again, and Nessie has forgotten every
schema/table (`SCHEMA_NOT_FOUND` on things you loaded minutes ago).

**Cause:** the WSL2 lightweight VM itself restarted out from under Docker — `uptime` shows
something like `up 1 min` right after the failure, confirming it, and `dmesg` may show
`journal corrupted or uncleanly shut down` (an unclean kill, not a graceful shutdown). This
took the whole stack down at once, which is why it looks different from a single service
crashing.

We tried the standard fix — add to `C:\Users\<you>\.wslconfig`:
```
[wsl2]
vmIdleTimeout=-1
```
then `wsl --shutdown` to reload it. **This did not reliably prevent the restarts on this
machine** — the VM went down again afterward, uncleanly, which points at something at the
Windows-host level (sleep, a corporate power/security policy, Windows Update, antivirus)
rather than WSL2's own idle-timeout. It's still worth leaving the setting in place (harmless,
and it does correctly disable idle-shutdown as a *contributing* cause), but don't assume it
alone solves this on a managed/corporate laptop.

**Recovery is cheap, which is why this is a nuisance rather than a blocker:** Nessie's
`IN_MEMORY` catalog (see the `# RISK:` comment in `docker-compose.yml`) is what's actually
being lost — the downloaded files in `data/` and the raw bytes in the `seaweedfs_data` volume
survive the restart. Bring the stack back and reload:
```bash
docker compose up -d   # wait for all five healthy
make bronze             # source files are already on disk -- this is fast
make silver-gold
```
If you hit this constantly and want the catalog to survive host restarts, the real fix is
giving Nessie a durable backend (JDBC + Postgres — there's already a Postgres container in
this stack for MLflow that a second database could sit beside) instead of `IN_MEMORY`. Not
done here; flagging it as the actual long-term fix if the in-memory losses become disruptive.

---

## 1. Object storage — SeaweedFS

**`make smoke` hop 1 fails: nothing on :8333**

```bash
docker compose logs seaweedfs | tail -40
```
`server -s3` starts master + volume + filer + S3 gateway in one process; if the volume
directory is unwritable it dies quietly. `make reset` then `make up` clears a corrupt volume.

**hop 2 fails: bucket missing**

SeaweedFS does not auto-create buckets. Run `make init`. It is idempotent.

**Unsigned requests return 403 and that is fine.** The healthcheck deliberately hits the
master status endpoint on :9333 rather than the S3 port, because an unauthenticated list
against :8333 correctly returns 403 and that would look like a failure.

**Why not MinIO?** Community Edition was archived on 12 February 2026 — no patches, no
binaries. If you find a tutorial using it, that tutorial is stale.

---

## 2. Catalog — Nessie, and the Iceberg REST path

**This is the single most likely thing to be wrong in the whole stack.** Property names for
Nessie's S3 and warehouse configuration have moved across releases.

**hop 4 fails: Iceberg REST endpoint not responding**

Check the exact path — the branch name is part of the URI:
```bash
curl -v http://localhost:19120/iceberg/main/v1/config
curl -s  http://localhost:19120/api/v2/config | head
```
If `/iceberg/main/v1/config` 404s, the REST path shape has changed for the pinned Nessie
version. Check that version's docs, then fix `iceberg.rest-catalog.uri` in
`trino/etc/catalog/iceberg.properties`.

**hop 6 fails: Trino doesn't list the iceberg catalog**

Trino reads catalogs only at startup, and a malformed properties file is skipped **silently**:
```bash
docker compose logs trino | grep -i -A5 "catalog\|iceberg"
docker compose exec trino ls -la /etc/trino/catalog/     # confirm the mount landed
docker compose restart trino
```

**hop 7 fails: table creates but writes 403 or lands nowhere**

Nessie hands Trino the warehouse location; Trino does the object IO with its own keys
(**Trino does not support S3 request signing**, which is why credential vending is disabled).
So a write failure means either the warehouse location Nessie returned is wrong, or Trino's
own S3 credentials are.
```bash
docker compose logs nessie | grep -i "warehouse\|s3\|secret"
aws --endpoint-url http://localhost:8333 s3 ls --recursive s3://lakehouse/ | head
```

### Fallback: the older `nessie` catalog type

If the REST path keeps fighting, fall back to the classic connector config. You lose the
shared-catalog-with-PyIceberg benefit but the tutorial works. Replace the catalog block in
`trino/etc/catalog/iceberg.properties` with:

```properties
connector.name=iceberg
iceberg.catalog.type=nessie
iceberg.nessie-catalog.uri=http://nessie:19120/api/v2
iceberg.nessie-catalog.ref=main
iceberg.nessie-catalog.default-warehouse-dir=s3://lakehouse/warehouse
fs.native-s3.enabled=true
s3.endpoint=http://seaweedfs:8333
s3.region=us-east-1
s3.path-style-access=true
s3.aws-access-key=lakehouse
s3.aws-secret-key=lakehouse-local-secret
```
Then `docker compose restart trino && make smoke`.

---

## 3. Engine — Trino

**Trino never becomes healthy / container restarts**

Almost always memory. The heap is set through `JAVA_TOOL_OPTIONS` in `.env` rather than by
replacing Trino's own tuned `jvm.config`, which is deliberate — replacing that file requires
getting a dozen JVM flags right for the exact JDK the image ships.

On an 8 GB machine, edit `.env`:
```
TRINO_HEAP=-Xmx1500m
```
Then `docker compose up -d trino`. If it still dies, give Docker Desktop more RAM before
tuning further.

**Queries fail with memory errors on the full dataset**

Load one month instead of two: drop the 2024 file and skip the schema-drift lesson for now.

---

## 4. Loading and transforms

**`make bronze` — "no TLC parquet in data/"**

Run `make data` first. The repo intentionally ships no data.

**GHCN file is much larger than expected**

Expected, and harmless. `03b_load_weather.py` prints the real size and filters to the
canonical years at landing, so nothing downstream cares. Narrow it further with
`GHCN_YEARS=2025 make bronze`.

**`dbt build` fails on a column that doesn't exist**

Most likely `cbd_congestion_fee` — it exists in the 2025 file and not in 2024. That is the
point of the lesson: bronze absorbs the drift, and `stg_trips.sql` resolves it with an
explicit `coalesce`. If you changed the bronze schema, the coalesce is what to check.

**`SELECT * EXCLUDE` or an alias in `WHERE` fails**

DuckDB allows both; **Trino allows neither**. The models are written Trino-first for this
reason. See `validated/shim.py` for the full list of dialect gaps.

**A CSV read is unexpectedly slow / won't parallelize**

A quoted newline inside a field makes a CSV non-splittable — true of Trino and Spark as well
as DuckDB. `03c_load_zone_lookup.py` sets `parallel=false` deliberately.

---

## 5. Quality gate

**`make gate` fails on a clean run**

Read which test failed; that is the diagnosis. Check the quarantine tables first — rows are
set aside with a reason rather than dropped:
```sql
SELECT _reject_reason, count(*) FROM iceberg.silver.qtn_zone_lookup GROUP BY 1;
SELECT _reject_reason, count(*) FROM iceberg.silver.qtn_ghcn        GROUP BY 1;
```

**`make break` runs but the gate stays OPEN**

The corrupt file must be picked up by the loader and reach gold. Re-run the full chain:
```bash
make break && make bronze && make silver-gold && make gate
```
If it still passes, confirm `data/yellow_tripdata_2025-01-CORRUPT.parquet` exists and that
`03a_load_trips.py` globbed it. **Note:** corrupting the bronze *table* directly does not
work — the next load rebuilds it from source and silently erases your defect. Bad data has to
arrive as a file.

---

## 6. MLflow

**`MlflowException: The filesystem tracking backend ... is in maintenance mode`**

You have pointed MLflow at a file path. MLflow 3.x **refuses** the file store. Use the
Postgres-backed server (`http://localhost:5000`) — already configured. Every older tutorial
showing `file:./mlruns` is now wrong.

**MLflow container exits immediately**

The official image ships without `psycopg2`/`boto3`, so the entrypoint pip-installs them
before serving. First start is therefore slow, and fails entirely with no network. Check:
```bash
docker compose logs mlflow | tail -30
```

**Artifacts fail to log**

MLflow writes artifacts to `s3://lakehouse/mlflow-artifacts` via SeaweedFS. Confirm the
bucket exists (`make init`) and that `MLFLOW_S3_ENDPOINT_URL` is set in the container.

---

## 7. Moving to AWS

The trap that catches almost everyone: **`s3.path-style-access=true` is required locally and
wrong on real S3**, which wants virtual-hosted addressing. It fails with a misleading
DNS-style error.
