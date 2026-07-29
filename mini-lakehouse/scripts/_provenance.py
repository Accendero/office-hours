"""One provenance helper, applied by every loader.

Bronze's contract is not a file format -- it is these three properties:
  1. arrival fidelity  (original payload recoverable, so a bad parse is replayable)
  2. provenance        (identical columns on EVERY bronze table, whatever the shape)
  3. no business logic (no filters, no joins, no cast that can fail)
Given those, silver is where every shape converges.
"""
import datetime, pathlib

COLUMNS = ["_source", "_source_file", "_ingested_at", "_record_no"]  # + _raw when non-columnar


def sql_prefix(source: str, path: str) -> str:
    """SQL fragment adding provenance to a SELECT. _record_no added by the caller."""
    ts = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)
    return (
        f"    '{source}' as _source,\n"
        f"    '{pathlib.Path(path).name}' as _source_file,\n"
        f"    timestamp '{ts.isoformat(sep=' ')}' as _ingested_at,\n"
        f"    row_number() over () as _record_no,\n"
    )
