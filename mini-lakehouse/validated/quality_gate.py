"""The promotion gate. These assertions are the SAME logic that becomes dbt tests
(schema.yml) in the real repo; this script is what CI/the DAG runs to halt promotion.
Each check returns (name, failing_row_count, severity)."""
import duckdb, sys

CHECKS = [
  # (name, sql returning failing rows, severity)
  ("silver: no null order key",      "select 1 from silver.stg_trips where pickup_at is null or vendor_id is null", "error"),
  ("silver: fare strictly positive", "select 1 from silver.stg_trips where fare_amount <= 0", "error"),
  ("silver: duration in range",      "select 1 from silver.stg_trips where trip_duration_s not between 60 and 10800", "error"),
  ("silver: no exact duplicates",    """select 1 from (
        select count(*) c from silver.stg_trips
        group by vendor_id, pickup_at, dropoff_at, pickup_location_id, dropoff_location_id, total_amount
        having count(*) > 1)""", "error"),
  ("silver: total >= fare",          "select 1 from silver.stg_trips where total_amount < fare_amount - 0.01", "warn"),
  ("gold: speed plausible",          "select 1 from gold.fct_trips where avg_speed_mph >= 80 or avg_speed_mph <= 0", "error"),
  ("gold: tip_rate bounded",         "select 1 from gold.fct_trips where tip_rate < 0 or tip_rate > 3", "error"),
  ("gold: row count not collapsed",  "select 1 from gold.fct_trips having count(*) < 50000", "error"),
  ("gold: pickup_hour valid",        "select 1 from gold.fct_trips where pickup_hour not between 0 and 23", "error"),
]

def run(db="/tmp/proto.duckdb"):
    con = duckdb.connect(db, read_only=True)
    failed_err = 0
    print(f"{'CHECK':<34} {'FAILING':>9}  RESULT")
    print("-" * 60)
    for name, sql, sev in CHECKS:
        n = con.sql(f"select count(*) from ({sql}) x").fetchone()[0]
        if n == 0:            status = "PASS"
        elif sev == "warn":   status = f"WARN({sev})"
        else:                 status = "FAIL"; failed_err += 1
        print(f"{name:<34} {n:>9,}  {status}")
    con.close()
    print("-" * 60)
    if failed_err:
        print(f"GATE CLOSED: {failed_err} error-severity check(s) failed. Promotion halted.")
        return 1
    print("GATE OPEN: silver+gold passed. Safe to train.")
    return 0

if __name__ == "__main__":
    sys.exit(run())
