"""Step 4: train + track. The point of this script is NOT the model -- it's that the
run records the exact DATA VERSION it read, so the result is reproducible later.
In the real repo the version is the Iceberg snapshot id; here it's a content hash
standing in for it (same role, same logging call).
"""
import duckdb, mlflow, hashlib, json, os
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

# NOTE: MLflow 3.x put the FILE store in maintenance mode -- it now raises unless
# MLFLOW_ALLOW_FILE_STORE=true. A DB backend is mandatory. sqlite locally, Postgres in compose.
mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "sqlite:////tmp/mlflow.db"))
mlflow.set_experiment("taxi-trip-duration")

con = duckdb.connect("/tmp/proto.duckdb", read_only=True)
FEATURES = ["trip_distance_mi","pickup_hour","pickup_dow","is_weekend",
            "passenger_count","pickup_location_id","dropoff_location_id"]
TARGET = "trip_duration_min"

df = con.sql(f"select {','.join(FEATURES)}, {TARGET} from gold.fct_trips").df()

# --- data version: in the real repo, replace with the Iceberg snapshot id ---
# SELECT snapshot_id FROM iceberg.gold."fct_trips$snapshots" ORDER BY committed_at DESC LIMIT 1
snap = con.sql("select count(*) c, round(sum(trip_duration_min),2) s from gold.fct_trips").fetchone()
data_version = hashlib.sha256(json.dumps(snap).encode()).hexdigest()[:16]
con.close()

X, y = df[FEATURES], df[TARGET]
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)

params = {"max_depth": 6, "learning_rate": 0.1, "max_iter": 200}
with mlflow.start_run() as run:
    mlflow.log_params(params)
    mlflow.log_param("data_version", data_version)       # <-- the reproducibility hook
    mlflow.log_param("n_rows", len(df))
    mlflow.set_tag("gold_table", "gold.fct_trips")

    model = HistGradientBoostingRegressor(**params).fit(Xtr, ytr)
    pred = model.predict(Xte)
    mae, r2 = mean_absolute_error(yte, pred), r2_score(yte, pred)
    mlflow.log_metric("mae_min", mae)
    mlflow.log_metric("r2", r2)
    mlflow.sklearn.log_model(model, name="model", input_example=Xte.head(3))

    print(f"run_id      : {run.info.run_id}")
    print(f"data_version: {data_version}")
    print(f"rows        : {len(df):,}")
    print(f"MAE         : {mae:.3f} min")
    print(f"R2          : {r2:.4f}")
