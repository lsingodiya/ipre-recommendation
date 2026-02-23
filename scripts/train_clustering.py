"""
train_clustering.py — SageMaker Training Job script for customer clustering.

SageMaker Training Job path contract:
  Input channel 'market_basket' : /opt/ml/input/data/market_basket/
  Model artifacts               : /opt/ml/model/          (tarred → model.tar.gz)
  Non-model outputs             : /opt/ml/output/data/    (customer_clusters.csv)

What this script does:
  1. Reads market_basket.csv from the 'market_basket' input channel.
  2. Trains one KMeans + StandardScaler per segment.
  3. Saves every model/scaler/feature-columns to /opt/ml/model/ so SageMaker
     packages them into model.tar.gz for Model Registry and endpoint serving.
  4. Writes customer_clusters.csv to /opt/ml/output/data/ so downstream
     Processing Jobs (Associations, Ranking) can consume it from S3.
"""

import json
import os
import pickle
from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# --------------------------------------------------
# SageMaker Training Job path constants
# --------------------------------------------------
INPUT_DIR  = Path(os.environ.get("SM_CHANNEL_MARKET_BASKET", "/opt/ml/input/data/market_basket"))
MODEL_DIR  = Path(os.environ.get("SM_MODEL_DIR",             "/opt/ml/model"))
OUTPUT_DIR = Path("/opt/ml/output/data")


def build_features(sdf: pd.DataFrame):
    """
    Pivot market basket rows into a customer x l2_category quantity matrix.
    Drops zero-variance columns before returning — StandardScaler divides by
    std so zero-variance columns produce NaN and silently corrupt KMeans.
    Returns (customer_ids, X_dataframe).
    """
    pivot = sdf.pivot_table(
        index="customer_id",
        columns="l2_category",
        values="total_quantity",
        aggfunc="sum",
        fill_value=0,
    )

    features     = pivot.reset_index()
    customer_ids = features["customer_id"].tolist()
    X            = features.drop(columns=["customer_id"])

    zero_var = X.columns[X.std() == 0]
    if len(zero_var):
        print(f"    Dropping {len(zero_var)} zero-variance columns: {list(zero_var)}")
        X = X.drop(columns=zero_var)

    return customer_ids, X


def choose_k(n: int) -> int:
    """Heuristic k selection — matches original pipeline logic."""
    if n < 6:
        return 1
    return min(4, int(n ** 0.5))


def main():
    print("=== IPRE Clustering Training Job ===")

    # Locate market_basket.csv — SageMaker may place it directly in the channel
    # dir or in a subdirectory depending on how the S3 URI was specified.
    candidates = list(INPUT_DIR.rglob("market_basket.csv"))
    if not candidates:
        raise FileNotFoundError(f"market_basket.csv not found under {INPUT_DIR}")
    basket_path = candidates[0]

    print(f"Loading: {basket_path}")
    df = pd.read_csv(basket_path)
    df["customer_id"] = df["customer_id"].astype(str)
    df["segment"]     = df["region"] + "_" + df["end_use"]

    print(f"Rows={len(df)}  Segments={df['segment'].nunique()}  Customers={df['customer_id'].nunique()}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cluster_outputs = []
    model_registry  = {}

    # --------------------------------------------------
    # Train one KMeans per segment
    # --------------------------------------------------
    for segment, sdf in df.groupby("segment"):
        print(f"\nSegment: {segment}")

        customer_ids, X = build_features(sdf)

        if X.empty:
            print(f"  WARNING: No usable features — skipping")
            continue

        n = len(customer_ids)
        k = choose_k(n)
        print(f"  Customers={n}  k={k}  Features={X.shape[1]}")

        scaler   = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        # Globally unique cluster IDs — raw 0..k-1 labels repeat across
        # segments and cause ambiguous joins in downstream steps.
        prefixed_labels = [f"{segment}_{lbl}" for lbl in labels]

        # Sanitize segment name for use as filename
        safe_seg = segment.replace(" ", "_").replace("/", "-")

        model_path  = MODEL_DIR / f"{safe_seg}_kmeans.pkl"
        scaler_path = MODEL_DIR / f"{safe_seg}_scaler.pkl"
        cols_path   = MODEL_DIR / f"{safe_seg}_columns.json"

        with open(model_path,  "wb") as f: pickle.dump(kmeans, f)
        with open(scaler_path, "wb") as f: pickle.dump(scaler, f)
        with open(cols_path,   "w")  as f: json.dump(X.columns.tolist(), f)

        print(f"  Saved: {model_path.name}  inertia={round(kmeans.inertia_, 2)}")

        model_registry[segment] = {
            "segment":      segment,
            "n_customers":  n,
            "k":            k,
            "inertia":      round(kmeans.inertia_, 4),
            "feature_cols": X.columns.tolist(),
            "model_file":   model_path.name,
            "scaler_file":  scaler_path.name,
            "cols_file":    cols_path.name,
        }

        cluster_outputs.append(pd.DataFrame({
            "customer_id": customer_ids,
            "cluster_id":  prefixed_labels,
            "segment":     segment,
        }))

    if not cluster_outputs:
        raise ValueError(
            "Clustering produced no output — all segments were skipped. "
            "Check that the market basket has valid l2_category data."
        )

    # Save model manifest — inference.py loads this at endpoint startup
    manifest_path = MODEL_DIR / "model_registry.json"
    with open(manifest_path, "w") as f:
        json.dump(model_registry, f, indent=2)
    print(f"\nModel manifest: {manifest_path}")

    # FIX: Write customer_clusters.csv into MODEL_DIR (/opt/ml/model/) rather
    # than OUTPUT_DIR (/opt/ml/output/data/). SageMaker packages /opt/ml/model/
    # into model.tar.gz which is the artifact referenced by
    # ModelArtifacts.S3ModelArtifacts and passed as ProcessingInput to
    # Associations and Ranking. Writing to /opt/ml/output/data/ produces a
    # separate output.tar.gz at a different S3 path that downstream steps
    # don't reliably receive. Keeping everything in model.tar.gz means the
    # CSV is always co-located with the pkl files in whatever tar is mounted.
    final = pd.concat(cluster_outputs, ignore_index=True)
    clusters_csv = MODEL_DIR / "customer_clusters.csv"
    final.to_csv(clusters_csv, index=False)

    print(f"Customer clusters: {clusters_csv}  ({len(final)} rows)")

    print("\n=== Coherence Summary ===")
    for seg, meta in model_registry.items():
        print(f"  {seg}: k={meta['k']}  inertia={meta['inertia']}  customers={meta['n_customers']}")

    print("\nTraining complete.")


if __name__ == "__main__":
    main()
