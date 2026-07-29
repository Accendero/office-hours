"""Generate TLC-yellow-shaped Parquet with the *real* defect classes TLC exhibits.
Used only to validate pipeline logic offline; the tutorial itself uses real TLC data.
"""
import numpy as np, pandas as pd, pathlib

rng = np.random.default_rng(7)
N = 200_000

base = pd.Timestamp("2025-01-01")
pick = base + pd.to_timedelta(rng.integers(0, 31*24*3600, N), unit="s")
# distance first, THEN duration derived from it -- real TLC has this signal and a
# tutorial whose model scores R2~0 teaches the wrong lesson.
dist = np.abs(rng.lognormal(mean=0.9, sigma=0.8, size=N)).round(2)
hour = pick.hour.values
rush = np.isin(hour, [7,8,9,16,17,18,19]).astype(float)
speed_mph = 13.5 - 3.2*rush + rng.normal(0, 2.0, N)        # rush hour slows you down
speed_mph = np.clip(speed_mph, 3.5, 45.0)
dur = (dist / speed_mph * 3600) + rng.normal(90, 45, N)    # + fixed overhead/noise
dur = np.clip(dur, 45, 3*3600)
drop = pick + pd.to_timedelta(dur, unit="s")
fare = (2.5 + dist * 2.8 + dur/60 * 0.35).round(2)

df = pd.DataFrame({
    "VendorID": rng.choice([1,2,6], N),
    "tpep_pickup_datetime": pick,
    "tpep_dropoff_datetime": drop,
    "passenger_count": rng.choice([1,1,1,2,2,3,4,5,6,None], N).astype("float64"),
    "trip_distance": dist,
    "RatecodeID": rng.choice([1,1,1,2,3,4,5,99,None], N).astype("float64"),
    "store_and_fwd_flag": rng.choice(["N","N","N","Y",None], N),
    "PULocationID": rng.integers(1, 266, N),
    "DOLocationID": rng.integers(1, 266, N),
    "payment_type": rng.choice([1,1,1,2,2,3,4,0], N),
    "fare_amount": fare,
    "extra": rng.choice([0.0,0.5,1.0,2.5,3.5], N),
    "mta_tax": np.full(N, 0.5),
    "tip_amount": (fare * rng.choice([0.0,0.0,0.15,0.18,0.2,0.25,0.3], N)).round(2),
    "tolls_amount": rng.choice([0.0]*20 + [6.94, 6.55], N),
    "improvement_surcharge": np.full(N, 1.0),
    "congestion_surcharge": rng.choice([0.0, 2.5, 2.5], N),
    "Airport_fee": rng.choice([0.0]*10 + [1.75], N),
    "cbd_congestion_fee": rng.choice([0.0, 0.75], N),   # new in 2025 -> schema drift lesson
})
df["total_amount"] = (df.fare_amount + df.extra + df.mta_tax + df.tip_amount
                      + df.tolls_amount + df.improvement_surcharge
                      + df.congestion_surcharge + df.Airport_fee
                      + df.cbd_congestion_fee).round(2)

# ---- inject the defect classes real TLC data actually contains ----
def idx(frac): return rng.choice(N, int(N*frac), replace=False)

i = idx(0.004); df.loc[i, "fare_amount"] *= -1; df.loc[i, "total_amount"] *= -1   # refunds/negatives
i = idx(0.003); df.loc[i, "tpep_dropoff_datetime"] = df.loc[i, "tpep_pickup_datetime"] - pd.Timedelta(minutes=4)  # dropoff<pickup
i = idx(0.002); df.loc[i, "trip_distance"] = 0.0                                  # zero-distance w/ fare
i = idx(0.001); df.loc[i, "trip_distance"] = rng.uniform(900, 6000, len(i))       # impossible distance
i = idx(0.002); df.loc[i, "passenger_count"] = 0                                  # zero passengers
i = idx(0.001); df.loc[i, "tpep_pickup_datetime"] = pd.Timestamp("2002-06-14")    # out-of-range dates
i = idx(0.0015); df.loc[i, "total_amount"] = df.loc[i, "total_amount"] + 4200      # fare outliers
dup = df.sample(400, random_state=3)                                              # exact dupes
df = pd.concat([df, dup], ignore_index=True)

out = pathlib.Path("/sessions/exciting-busy-maxwell/mnt/outputs/proto/data/yellow_tripdata_2025-01.parquet")
df.to_parquet(out, index=False)
print("rows:", len(df), "cols:", len(df.columns))
print("size MB:", round(out.stat().st_size/1e6, 2))
