"""Train on gold, log to MLflow with the DATA VERSION that produced the run.

The point is not the model. It is that six months from now you can answer
"which data produced this number?" -- so the Iceberg snapshot id is logged as a
first-class parameter. That is the whole reason step 4 exists.
"""
import os, mlflow, trino, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

# This script runs on the host, not in the compose network -- the mlflow SERVER logs
# artifacts to S3 using the creds/endpoint docker-compose.yml gives its own container,
# but the mlflow CLIENT here (this process) uploads the model itself and needs its own
# boto3-visible credentials. .env's S3_ENDPOINT is the docker-internal hostname
# (unreachable from the host); MLFLOW_S3_ENDPOINT_URL/AWS_* are the names boto3 actually
# reads, not S3_ENDPOINT/S3_ACCESS_KEY/S3_SECRET_KEY.
os.environ.setdefault("AWS_ACCESS_KEY_ID", os.getenv("S3_ACCESS_KEY", "lakehouse"))
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", os.getenv("S3_SECRET_KEY", "lakehouse-local-secret"))
os.environ.setdefault("MLFLOW_S3_ENDPOINT_URL", os.getenv("S3_ENDPOINT_HOST", "http://localhost:8333"))

TRACKING = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
mlflow.set_tracking_uri(TRACKING)          # a DB-backed server; the file store now RAISES
mlflow.set_experiment("taxi-trip-duration")

conn = trino.dbapi.connect(host=os.getenv("TRINO_HOST", "localhost"),
                           port=int(os.getenv("TRINO_PORT", 8080)),
                           user="trainer", catalog="iceberg", schema="gold")

FEATURES = ["trip_distance_mi", "pickup_hour", "pickup_dow", "is_weekend",
            "passenger_count", "pickup_location_id", "dropoff_location_id"]
TARGET = "trip_duration_min"

df = pd.read_sql(f"SELECT {', '.join(FEATURES)}, {TARGET} FROM iceberg.gold.fct_trips", conn)

# THE reproducibility hook: Iceberg's own snapshot id, not a hash of the data.
cur = conn.cursor()
cur.execute('SELECT snapshot_id FROM iceberg.gold."fct_trips$snapshots" '
            'ORDER BY committed_at DESC LIMIT 1')
snapshot_id = cur.fetchone()[0]
conn.close()

X, y = df[FEATURES], df[TARGET]
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
params = {"max_depth": 6, "learning_rate": 0.1, "max_iter": 200}

with mlflow.start_run() as run:
    mlflow.log_params(params)
    mlflow.log_param("iceberg_snapshot_id", snapshot_id)   # <-- the data version
    mlflow.log_param("n_rows", len(df))
    mlflow.set_tag("gold_table", "iceberg.gold.fct_trips")

    model = HistGradientBoostingRegressor(**params).fit(Xtr, ytr)
    pred = model.predict(Xte)
    mae, r2 = mean_absolute_error(yte, pred), r2_score(yte, pred)
    mlflow.log_metric("mae_min", mae)
    mlflow.log_metric("r2", r2)
    mlflow.sklearn.log_model(model, name="model", input_example=Xte.head(3))

    print(f"run_id      : {run.info.run_id}")
    print(f"snapshot_id : {snapshot_id}")
    print(f"rows        : {len(df):,}")
    print(f"MAE         : {mae:.3f} min")
    print(f"R2          : {r2:.4f}")
    print(f"\nMLflow UI: {TRACKING}")
