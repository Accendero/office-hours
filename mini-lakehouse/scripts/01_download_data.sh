#!/usr/bin/env bash
# The repo ships NO data -- only this script. That is what keeps licensing simple.
# Attribution requirements: see docs/DATA_SOURCES.md (NOAA has a formal citation requirement).
set -euo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)/data"
mkdir -p "$D"

get () { # url, filename, description
  if [ -s "$D/$2" ]; then
    echo "  have    $2  ($(du -h "$D/$2" | cut -f1))"
  else
    echo "  fetch   $2  -- $3"
    curl -fsSL --retry 3 -o "$D/$2.part" "$1" && mv "$D/$2.part" "$D/$2"
    echo "          got $(du -h "$D/$2" | cut -f1)"
  fi
}

TLC=https://d37ci6vzurychx.cloudfront.net
echo "=== source A: TLC yellow taxi trips (Parquet) ==="
get "$TLC/trip-data/yellow_tripdata_2025-01.parquet" yellow_tripdata_2025-01.parquet "fact table"
echo "=== source A': one year earlier -- lacks cbd_congestion_fee (schema drift) ==="
get "$TLC/trip-data/yellow_tripdata_2024-01.parquet" yellow_tripdata_2024-01.parquet "real schema drift"
echo "=== source C: taxi zone lookup (CSV dimension) ==="
get "$TLC/misc/taxi_zone_lookup.csv" taxi_zone_lookup.csv "borough names"

echo "=== source B: NOAA GHCN-Daily, NYC Central Park (long/narrow CSV) ==="
# Period-of-record file: exact size unknown and liable to grow, so we print it and
# filter at landing rather than pinning a number that will rot.
# NOAA serves by_station files gzip-only as of 2026 (plain .csv now 404s) -- fetch
# compressed, decompress once. 03b_load_weather.py still reads the plain .csv.
if [ -s "$D/USW00094728.csv" ]; then
  echo "  have    USW00094728.csv  ($(du -h "$D/USW00094728.csv" | cut -f1))"
else
  echo "  fetch   USW00094728.csv.gz  -- weather -- one row PER ELEMENT per day"
  curl -fsSL --retry 3 -o "$D/USW00094728.csv.gz.part" \
    "https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/USW00094728.csv.gz" \
    && mv "$D/USW00094728.csv.gz.part" "$D/USW00094728.csv.gz"
  gunzip "$D/USW00094728.csv.gz"
  echo "          got $(du -h "$D/USW00094728.csv" | cut -f1)"
fi

echo
echo "downloaded:"; ls -lh "$D" | tail -n +2 | awk '{printf "  %-42s %s\n", $9, $5}'
