# Handoff brief — mini-lakehouse tutorial

Read this first. It tells you what is already proven, what has never run, and the order to
test in. The full design rationale lives in `../mini-lakehouse-tutorial-plan.md`; this file is
the operational summary.

## What this is

A laptop-only teaching rig for a mini lakehouse: object storage → Iceberg → medallion
(bronze/silver/gold) → quality gate → trained model with tracked lineage. It is NOT a
production architecture. In a real environment the object store is S3.

Stack: SeaweedFS (S3) + Nessie (Iceberg REST catalog) + Trino (engine) + dbt-trino
(transforms) + MLflow + Postgres (tracking).

## Status — read carefully

| Component | State |
|---|---|
| Medallion SQL, quality gate, training logic | **Validated** offline against synthetic data (`validated/`). R² 0.923, gate opens and closes correctly. |
| Weather landing → QC filter → pivot → rescale | **Validated** offline (`validated/messy/weather/`). |
| Lift experiment apparatus | **Validated** — control 0.1%, treatment 36.5% (`validated/weather_lift_test.py`). |
| **Docker compose stack** | **Proven on WSL2/Ubuntu** — `make smoke` 7/7 after fixing `smoke.sh`'s result parser and the mlflow healthcheck. See `docs/TROUBLESHOOTING.md` #0. |
| dbt project | **Proven against real data** — `make bronze && make silver-gold && make gate` all green (23/23 tests), `make break` confirmed the gate catches injected corruption, `make train` confirmed end-to-end (model artifact verified in S3). Required: writing bronze via `pyiceberg` directly (Trino has no path to land local files -- see `scripts/_iceberg.py`), `TRINO_HEAP` raised to 6g for the trips dedup window function, a new `qtn_trips` quarantine model for real (non-injected) tip_rate/avg_speed_mph outliers, a `generate_schema_name` macro override (dbt's default concatenated `silver_gold`/`silver_silver` instead of clean schema names), and host-side S3 credentials for the MLflow client in `08_train.py`. `make lift` not yet run. |

The SQL in `validated/sql/` is written in **Trino dialect** and was tested in DuckDB via the
shims in `validated/shim.py`. Known dialect gaps already handled: no `SELECT * EXCLUDE`, no
select-alias in `WHERE`, `day_of_week` not `isodow`.

## Test in this order. Do not skip ahead.

The failure surface is concentrated in stage 1. Stage 2 is mostly ported, already-validated
logic. Debugging both at once wastes time.

### Stage 1 — infrastructure (the risky part)
```
make up
make smoke        # tests each hop independently, stops at the first failure
```
`make smoke` walks seven hops: SeaweedFS S3 → bucket → Nessie health → Nessie Iceberg REST →
Trino up → Trino sees the catalog → Trino creates/queries/drops a real Iceberg table and the
objects appear in S3. **Do not proceed until all seven pass.**

Highest-risk area: the Trino ↔ Nessie ↔ SeaweedFS wiring in
`trino/etc/catalog/iceberg.properties` and the Nessie env block in `docker-compose.yml`.
Property names have shifted across versions. Both files carry `# RISK:` comments on the lines
most likely to be wrong, and `docs/TROUBLESHOOTING.md` has a fallback config using the older
`iceberg.catalog.type=nessie` style if the REST path fights back.

### Stage 2 — data and transforms
```
make data         # download the four real files (~150 MB)
make bronze       # three loaders, three shapes, one landing pattern
make silver-gold  # dbt build
make gate         # dbt test -- the promotion gate
make break        # land corrupt data upstream; gate MUST close
make train        # train + log to MLflow
make lift         # the weather decision rule (see below)
```

### Stage 3 — the open experiment
`make lift` runs the decision rule that was fixed in advance: **keep the weather source if it
improves test MAE by ≥2% over the base features.** Control noise was measured at 0.1%, so 2%
is comfortably outside it. If real data comes in under 2%, cut the weather source from the
tutorial and document the negative result — that is a better lesson than a feature that
quietly does nothing. Do not move the threshold to save the feature.

## Non-negotiables — these will bite you

1. **MLflow's file store is dead.** `file:./mlruns` raises on MLflow 3.x. A DB backend is
   mandatory. Already configured to Postgres; do not "simplify" it back.
2. **Land text as text.** Every CSV column lands as VARCHAR. A cast that fails in bronze
   destroys data you cannot re-fetch. Casting is silver's job.
3. **Quarantine, don't drop.** Every silver model has a paired quarantine model with a
   `_reject_reason`. "We dropped 11%" is only defensible if you can show the 11%.
4. **Domain checks, not just type checks.** A thousands separator in a CSV shifts every field
   right and still passes type validation. `accepted_values` tests are the only thing that
   catches structural corruption. See the field-shift finding in the plan (§7.4).
5. **Corrupt the source, not the table.** `07_break_the_data.py` lands a new file in `data/`.
   Writing to the bronze table instead gets erased on the next run and the demo silently fails.
6. **Never commit data.** `.gitignore` excludes `data/` and the warehouse. The repo ships
   download scripts only — that is what keeps licensing simple.

## If you change the SQL

`validated/` is the reference implementation and it passes. If you change a dbt model, re-run
the offline validation to confirm the logic still holds before blaming the stack:
```
cd validated && python3 run_pipeline.py && python3 quality_gate.py
```

## Pinned versions

Everything is pinned on purpose. MinIO was archived in February 2026 mid-design; pinning is not
paranoia. See `requirements.txt` and the image tags in `docker-compose.yml`. If you must bump
something, bump one thing at a time and re-run `make smoke`.
