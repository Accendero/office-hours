"""Validate the EXPERIMENT, not the hypothesis.

I cannot test whether real NYC weather improves the duration model -- that needs real TLC
and real GHCN. What I CAN do is prove the measurement apparatus works: inject a known
weather effect, confirm the pipeline detects it, then confirm it reports ~zero when the
effect is absent. That way a null result on real data means "no real effect", not "my code
is broken" -- which is the only way the decision rule in the plan is trustworthy.
"""
import duckdb, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

BASE = ["trip_distance_mi","pickup_hour","pickup_dow","is_weekend",
        "passenger_count","pickup_location_id","dropoff_location_id"]
WX   = ["precip_mm","snow_mm","tmax_c","avg_wind_ms","is_wet_day","is_snow_day"]

def evaluate(df, feats, label):
    X, y = df[feats], df["trip_duration_min"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    m = HistGradientBoostingRegressor(max_depth=6, learning_rate=0.1, max_iter=200).fit(Xtr, ytr)
    p = m.predict(Xte)
    return mean_absolute_error(yte, p), r2_score(yte, p), label

def run(effect_strength, tag):
    con = duckdb.connect("/tmp/proto.duckdb", read_only=True)
    con.execute("attach '/tmp/weather.duckdb' as w (read_only)")
    df = con.sql(f"""
      select t.{', t.'.join(BASE)}, t.trip_duration_min,
             w.precip_mm, w.snow_mm, w.tmax_c, w.avg_wind_ms, w.is_wet_day, w.is_snow_day
      from gold.fct_trips t
      join w.silver.weather_daily w on cast(t.pickup_at as date) = w.obs_date
    """).df()
    con.close()

    # inject a KNOWN effect: rain slows trips proportionally to intensity
    rng = np.random.default_rng(3)
    slowdown = 1.0 + effect_strength * (df.precip_mm / 20.0).clip(0, 1.5) \
                   + effect_strength * 1.6 * (df.snow_mm / 100.0).clip(0, 1.5)
    df = df.copy()
    df["trip_duration_min"] = df.trip_duration_min * slowdown * rng.normal(1.0, 0.02, len(df))

    mae_b, r2_b, _ = evaluate(df, BASE, "base")
    mae_w, r2_w, _ = evaluate(df, BASE + WX, "base+weather")
    print(f"\n--- {tag} (injected effect strength = {effect_strength}) ---")
    print(f"  base            MAE {mae_b:6.3f} min   R2 {r2_b:.4f}")
    print(f"  base + weather  MAE {mae_w:6.3f} min   R2 {r2_w:.4f}")
    print(f"  LIFT            MAE {mae_b-mae_w:+.3f} min ({100*(mae_b-mae_w)/mae_b:+.1f}%)   R2 {r2_w-r2_b:+.4f}")
    return mae_b - mae_w

null_lift = run(0.0,  "CONTROL: no weather effect present")
real_lift = run(0.35, "TREATMENT: known weather effect present")

print("\n=== apparatus verdict ===")
print(f"  control lift   {null_lift:+.3f} min  (want ~0)")
print(f"  treatment lift {real_lift:+.3f} min  (want clearly > 0)")
ok = abs(null_lift) < 0.15 and real_lift > 0.30
print(f"  {'PASS' if ok else 'FAIL'}: the experiment can distinguish signal from no-signal.")
