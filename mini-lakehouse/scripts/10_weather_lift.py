"""THE OPEN EXPERIMENT. Decides whether the weather source stays in the tutorial.

The rule was fixed IN ADVANCE, before seeing real data: keep the weather features if
they improve test MAE by >= 2%. The apparatus was validated offline first
(validated/weather_lift_test.py): control run 0.1%, treatment run 36.5%. So a null
result here means "no real effect", not "broken code".

Do not move the threshold to save the feature. A documented negative result is a
better lesson than a feature that quietly does nothing.
"""
import os, trino, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

THRESHOLD_PCT = 2.0

BASE = ["trip_distance_mi", "pickup_hour", "pickup_dow", "is_weekend",
        "passenger_count", "pickup_location_id", "dropoff_location_id"]
WX = ["precip_mm", "snow_mm", "tmax_c", "avg_wind_ms", "is_wet_day", "is_snow_day"]

conn = trino.dbapi.connect(host=os.getenv("TRINO_HOST", "localhost"),
                           port=int(os.getenv("TRINO_PORT", 8080)),
                           user="experiment", catalog="iceberg", schema="gold")
df = pd.read_sql(
    f"SELECT {', '.join(BASE + WX)}, trip_duration_min FROM iceberg.gold.fct_trips "
    f"WHERE {' AND '.join(f'{c} IS NOT NULL' for c in WX)}", conn)
conn.close()
print(f"rows with complete weather: {len(df):,}")


def score(feats):
    X, y = df[feats], df["trip_duration_min"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    m = HistGradientBoostingRegressor(max_depth=6, learning_rate=0.1, max_iter=200).fit(Xtr, ytr)
    p = m.predict(Xte)
    return mean_absolute_error(yte, p), r2_score(yte, p)


mae_b, r2_b = score(BASE)
mae_w, r2_w = score(BASE + WX)
lift_pct = 100 * (mae_b - mae_w) / mae_b

print(f"\n  base            MAE {mae_b:6.3f} min   R2 {r2_b:.4f}")
print(f"  base + weather  MAE {mae_w:6.3f} min   R2 {r2_w:.4f}")
print(f"  LIFT            {lift_pct:+.2f}%  (threshold {THRESHOLD_PCT}%)")

if lift_pct >= THRESHOLD_PCT:
    print(f"\n  VERDICT: KEEP the weather source. It earns its place ({lift_pct:.2f}% >= {THRESHOLD_PCT}%).")
else:
    print(f"\n  VERDICT: CUT the weather source ({lift_pct:.2f}% < {THRESHOLD_PCT}%).")
    print("  Document the negative result in the README. Do not move the threshold.")
