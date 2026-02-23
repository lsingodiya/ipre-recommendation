"""
inference.py — SageMaker endpoint inference script for IPRE.

Called by SageMaker serving container:
  model_fn(model_dir)            — once at container startup
  input_fn(request_body, ct)     — per request, parse body
  predict_fn(input_data, model)  — per request, run inference
  output_fn(prediction, accept)  — per request, serialize response

Request  (JSON from Salesforce Lambda):
  {"customer_id": "C00052"}
  or for net-new customers:
  {"customer_id": "C00999", "segment": "Southeast_Plumbing",
   "purchase_vector": {"Valves": 10, "Plumbing Tools": 5}}

Response:
  {
    "customer_id": "C00052",
    "segment": "Southeast_Plumbing",
    "cluster_id": "Southeast_Plumbing_2",
    "source": "precomputed",
    "recommendations": [
      {"rank": 1, "product_id": "P00144", "trigger_product": "P00142",
       "score": 0.1255, "recommended_qty": 24,
       "reason": "P00142 -> P00144 (support=0.1, confidence=0.17)"}
    ]
  }
"""

import io
import json
import os
import pickle
from pathlib import Path

import boto3
import numpy as np
import pandas as pd

RECO_BUCKET = os.environ.get("RECO_BUCKET", "ipre-prod-poc")
RECO_KEY    = os.environ.get("RECO_KEY",    "final/recommendations.csv")


# ==========================================================
# model_fn — called ONCE at container startup
# ==========================================================

def model_fn(model_dir: str) -> dict:
    """Load all KMeans models + precomputed recommendations table."""
    model_dir = Path(model_dir)
    print(f"Loading models from: {model_dir}")

    manifest_path = model_dir / "model_registry.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"model_registry.json not found in {model_dir}")

    with open(manifest_path) as f:
        registry = json.load(f)

    models = {}
    for segment, meta in registry.items():
        with open(model_dir / meta["model_file"],  "rb") as f: kmeans = pickle.load(f)
        with open(model_dir / meta["scaler_file"], "rb") as f: scaler = pickle.load(f)
        with open(model_dir / meta["cols_file"])         as f: cols   = json.load(f)

        models[segment] = {
            "kmeans":       kmeans,
            "scaler":       scaler,
            "feature_cols": cols,
        }

    print(f"Loaded {len(models)} segment models")

    reco_df = _load_recommendations()

    return {"models": models, "reco_df": reco_df, "registry": registry}


def _load_recommendations() -> pd.DataFrame:
    print(f"Loading recommendations from s3://{RECO_BUCKET}/{RECO_KEY}")
    try:
        s3  = boto3.client("s3")
        obj = s3.get_object(Bucket=RECO_BUCKET, Key=RECO_KEY)
        df  = pd.read_csv(io.BytesIO(obj["Body"].read()))
        df["customer_id"] = df["customer_id"].astype(str)
        print(f"Recommendations loaded: {len(df)} rows, {df['customer_id'].nunique()} customers")
        return df
    except Exception as e:
        print(f"WARNING: Could not load recommendations ({e}). Lookup unavailable.")
        return pd.DataFrame()


# ==========================================================
# input_fn
# ==========================================================

def input_fn(request_body: str, content_type: str = "application/json") -> dict:
    if content_type != "application/json":
        raise ValueError(f"Unsupported content type: {content_type}")
    return json.loads(request_body)


# ==========================================================
# predict_fn — called per request
# ==========================================================

def predict_fn(input_data: dict, model: dict) -> dict:
    customer_id     = str(input_data.get("customer_id", "")).strip()
    segment         = input_data.get("segment", "").strip()
    purchase_vector = input_data.get("purchase_vector", None)

    if not customer_id:
        raise ValueError("Request must include 'customer_id'")

    reco_df = model["reco_df"]

    # --------------------------------------------------
    # PATH 1: Precomputed lookup — primary path for existing customers
    # --------------------------------------------------
    if not reco_df.empty:
        cust_recs = reco_df[reco_df["customer_id"] == customer_id]
        if not cust_recs.empty:
            recs = (
                cust_recs
                .sort_values("rank")
                [["rank", "recommended_product", "trigger_product",
                  "score", "recommended_qty", "reason", "cluster_id", "segment"]]
                .rename(columns={"recommended_product": "product_id"})
                .to_dict(orient="records")
            )
            return {
                "customer_id":     customer_id,
                "segment":         cust_recs["segment"].iloc[0],
                "cluster_id":      cust_recs["cluster_id"].iloc[0],
                "source":          "precomputed",
                "recommendations": recs,
            }

    # --------------------------------------------------
    # PATH 2: Real-time cluster assignment for net-new customers
    # Requires 'segment' + 'purchase_vector' in the request
    # --------------------------------------------------
    if not segment:
        return {
            "customer_id": customer_id,
            "error": (
                "Customer not found in precomputed recommendations. "
                "Provide 'segment' and 'purchase_vector' for real-time assignment."
            ),
        }

    if not purchase_vector:
        return {
            "customer_id": customer_id,
            "segment": segment,
            "error": "Provide 'purchase_vector' for real-time cluster assignment.",
        }

    seg_model = model["models"].get(segment)
    if seg_model is None:
        return {
            "customer_id": customer_id,
            "segment":     segment,
            "error": (
                f"No trained model for segment '{segment}'. "
                f"Available: {list(model['models'].keys())}"
            ),
        }

    feature_cols  = seg_model["feature_cols"]
    vector        = np.array([[purchase_vector.get(col, 0) for col in feature_cols]], dtype=float)
    vector_scaled = seg_model["scaler"].transform(vector)
    label         = int(seg_model["kmeans"].predict(vector_scaled)[0])
    cluster_id    = f"{segment}_{label}"

    return {
        "customer_id":     customer_id,
        "segment":         segment,
        "cluster_id":      cluster_id,
        "source":          "realtime_assignment",
        "recommendations": [],
        "message": (
            f"Customer assigned to cluster {cluster_id}. "
            "Precomputed recommendations available after next pipeline run."
        ),
    }


# ==========================================================
# output_fn
# ==========================================================

def output_fn(prediction: dict, accept: str = "application/json") -> str:
    return json.dumps(prediction, default=str)
