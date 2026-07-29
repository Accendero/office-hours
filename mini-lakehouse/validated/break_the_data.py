"""Workshop moment: bad data ARRIVES FROM UPSTREAM as a new file, the way it really does.
Writing to the bronze table instead would be erased on the next pipeline run --
a mistake worth making out loud in the guide.
Defect chosen deliberately: it passes every silver WHERE clause, so only the gate stops it."""
import duckdb, pathlib
src = "data/yellow_tripdata_2025-01.parquet"
out = pathlib.Path("data/yellow_tripdata_2025-01-CORRUPT.parquet")
con = duckdb.connect()
con.execute(f"""
  copy (
    select * replace (fare_amount * 12 as tip_amount)
    from read_parquet('{src}')
    where fare_amount > 5 and trip_distance between 1 and 5
    limit 900
  ) to '{out}' (format parquet)
""")
print(f"landed {out.name}: 900 rows, tip_amount = 12x fare -- passes all silver filters")
con.close()
