"""Trino->DuckDB shims so the SAME model SQL can be validated offline before Docker.
Each entry is a real dialect difference the tutorial must warn about."""
SHIMS = [
    ("day_of_week(", "isodow("),   # Trino day_of_week == ISO dow (1=Mon..7=Sun)
]
def to_duckdb(sql: str) -> str:
    for a, b in SHIMS: sql = sql.replace(a, b)
    return sql
