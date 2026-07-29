# office-hours
A repository for our office hours shared projects.

## Projects

- [`mini-lakehouse/`](mini-lakehouse/) — A laptop-only teaching rig for a mini data
  lakehouse: object storage (SeaweedFS) → Apache Iceberg → medallion architecture
  (bronze/silver/gold) → a dbt-based quality gate that actually stops bad data → a
  trained model with reproducible lineage via Iceberg snapshot IDs. Built on three real
  public datasets (NYC TLC taxi trips, NOAA weather, TLC zone lookup) — no synthetic
  data, no cloud account required. Verified end-to-end on Docker + WSL2; see
  `mini-lakehouse/README.md` for the walkthrough and `mini-lakehouse/CLAUDE.md` for the
  full testing history and known environment gotchas.
