# Mini-lakehouse on a laptop

A working lakehouse you can run in an afternoon: object storage → Apache Iceberg →
medallion (bronze/silver/gold) → a quality gate that actually stops bad data → a trained
model whose exact input data you can identify six months later.

Three real public datasets, three real file formats. No synthetic data, no cloud account,
no API keys.

**This is a teaching rig, not a production architecture.** In a real environment the object
store is Amazon S3 and the engine is managed. The whole thing is built so that swap is a
config change, not a rewrite — [`docs/AWS.md`](docs/AWS.md) shows exactly what changes and
what stays byte-identical (spoiler: about 90% stays).

## Prerequisites

- Docker Desktop or equivalent, ~7 GB RAM available to it
- Python 3.11+, `make`, `curl`
- AWS CLI **v2**, installed as the [standalone binary](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) —
  not `pip install awscli` (v1's exact `botocore` pin conflicts with `pyiceberg[s3fs]`; see
  `docs/TROUBLESHOOTING.md` #0)
- ~10 GB free disk

## Quickstart

```bash
cp .env.example .env
make deps          # python + dbt packages
make up            # start SeaweedFS, Nessie, Trino, Postgres, MLflow
make smoke         # STOP HERE until all seven hops pass
make data          # download ~150 MB of real data
make bronze        # land three sources through one pattern
make silver-gold   # dbt build
make gate          # dbt test -- the promotion gate
make train         # train + log to MLflow at localhost:5000
```

Then the two moments that matter most:

```bash
make break && make bronze && make silver-gold && make gate   # gate MUST close
make lift                                                     # keep or cut the weather source
```

`make help` lists everything.

## The stack, and why

| Layer | Choice | Why this one |
|---|---|---|
| Object storage | **SeaweedFS** | MinIO's community edition was **archived in February 2026**. Most lakehouse tutorials online still use it. |
| Table format | **Apache Iceberg** | Vendor-neutral, broadest engine support, time travel gives you an undo button. |
| Catalog | **Nessie** (Iceberg REST) | Git-like branching; the REST endpoint means one catalog serves Trino *and* PyIceberg. |
| Engine | **Trino** | Same SQL engine as Amazon Athena, so the SQL transfers unchanged. |
| Transforms | **dbt-trino** | Tests live beside the models and are version-controlled with them. |
| Quality gate | **dbt tests** | Great Expectations 1.x removed the API most tutorials still show — and a second framework before dbt's tests are exhausted is premature complexity. |
| Tracking | **MLflow + Postgres** | MLflow 3.x **raises** on the filesystem store. A database backend is mandatory now. |

## The data

| Source | Format | What it teaches |
|---|---|---|
| NYC TLC yellow taxi, Jan 2025 | Parquet | The fact table. Real defects: negative fares, dropoff before pickup, impossible distances. |
| NYC TLC yellow taxi, Jan 2024 | Parquet | **Real schema drift** — TLC added `cbd_congestion_fee` in 2025. Bronze absorbs it; silver resolves it. |
| NOAA GHCN-Daily, Central Park | CSV, long/narrow | Three real traps: one row per element per day, inconsistent unit scaling *within one file*, and rows NOAA itself flags as bad. |
| TLC taxi zone lookup | CSV dimension | Borough names — and why domain checks catch what type checks miss. |

Attribution and citation requirements: [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).
**The repo ships no data**, only the download script.

## Six ideas worth taking away

1. **Bronze's contract is not a file format.** Arrival fidelity, provenance columns, and no
   business logic. Given those, silver is where every shape converges — and nothing
   downstream can tell whether the source was Parquet, a log file, or free text.
2. **Land text as text.** A cast that fails in bronze destroys data you cannot re-fetch.
3. **Quarantine, don't drop.** "We dropped 11% of rows" is only defensible if you can show
   the 11%.
4. **Domain checks catch what type checks can't.** A thousands separator in an unquoted CSV
   field shifts every column right and still passes type validation. The row arrives fully
   typed, fully "valid", and completely wrong.
5. **A gate only earns its keep against a defect the filters miss.** Hence `make break`.
6. **Cost is driven by what you leave running, not what you store.** See `docs/AWS.md` — at
   this scale storage and queries run about $6/month while an always-on tracking server runs
   $96–438.

## What you should see

Numbers from an actual run against the real datasets (Jan 2024 + Jan 2025 TLC, NOAA GHCN
Central Park). Exact figures will drift slightly as NOAA's period-of-record file grows and
TLC revises historical months, but should land close to these:

| Stage | Result |
|---|---|
| `make smoke` | 7/7 hops pass |
| `make bronze` | ~6.44M trip rows (two months), 265 zones, ~10.4K weather element-days |
| `make gate` | 23/23 dbt tests pass. ~760 trips land in `gold.qtn_trips`, quarantined for real (not injected) tip_rate/avg_speed_mph outliers — e.g. a $3 fare with a $126 tip. That's expected, not a failure: see "Quarantine, don't drop" above. |
| `make break` → `make gate` | still 0 test failures. The 900 injected 12x-tip rows join the quarantine (`qtn_trips` grows by ~891, not the full 900 — the rest collide on `stg_trips`'s dedup key with their unmodified originals and lose the tie). The gate closes by keeping bad rows out of `fct_trips`, not by failing a test. |
| `make train` | MAE ≈ 3.0 min, R² ≈ 0.82 on ~5.5M rows. Snapshot id logged alongside the run — that's the point of step 4. |
| `make lift` | **CUT.** Weather features improved test MAE by **1.49%**, short of the 2% keep threshold fixed in advance (`validated/weather_lift_test.py`: 0.1% control noise, 36.5% treatment effect offline). |

**The weather source does not earn its place on real data.** `fct_trips` still carries the
weather columns so you can reproduce the comparison yourself, but a production version of
this pipeline would drop the join to `stg_weather_daily` and the source B ingestion
entirely. The keep/cut threshold was fixed *before* looking at real data for exactly this
reason: a marginal miss (1.49% isn't nothing — it's just not enough) can't be rescued by
moving the goalposts after the fact. A negative result, tested honestly, is a better lesson
than a feature kept only because removing it felt like wasted code.

## When it breaks

[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md). Start there rather than guessing —
the failures in this stack are concentrated in a handful of config properties.

## Layout

```
CLAUDE.md            handoff brief: what's proven, what isn't, what order to test in
docker-compose.yml   five services, pinned tags
trino/etc/catalog/   the Iceberg ↔ Nessie ↔ S3 wiring (highest-risk config)
scripts/             numbered: what you actually run
dbt/                 models + the tests that ARE the gate
validated/           offline reference implementation, proven before any container existed
docs/                AWS mapping, messy sources, troubleshooting, data attribution
```

## Licence

Code: see `LICENSE`. Data: not redistributed — see `docs/DATA_SOURCES.md`.
