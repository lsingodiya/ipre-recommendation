import tarfile
import pandas as pd
from itertools import combinations
from pathlib import Path

WINDOW_DAYS = 7


def extract_clustering_output(clustering_dir: str) -> Path:
    """
    The Associations step receives ModelArtifacts.S3ModelArtifacts as input,
    which points to model.tar.gz. This contains the KMeans pkl files,
    model_registry.json, AND customer_clusters.csv (all written to
    /opt/ml/model/ by train_clustering.py).

    SageMaker does NOT auto-extract tars in Processing containers — we do it here.
    Returns the Path to the directory containing customer_clusters.csv.
    """
    clustering_path = Path(clustering_dir)

    # Fast path — already extracted or bare CSV
    csv_direct = clustering_path / "customer_clusters.csv"
    if csv_direct.exists():
        return clustering_path

    # Target model.tar.gz specifically — this is what ModelArtifacts points to.
    # Avoid output.tar.gz which only contains /opt/ml/output/data/ contents.
    model_tar = clustering_path / "model.tar.gz"
    if not model_tar.exists():
        # Fallback: search recursively in case SageMaker placed it in a subdir
        candidates = list(clustering_path.rglob("model.tar.gz"))
        if not candidates:
            # Last resort: any tar.gz
            candidates = list(clustering_path.rglob("*.tar.gz"))
        if not candidates:
            raise FileNotFoundError(
                f"No model.tar.gz found under {clustering_dir}.\n"
                f"Contents: {list(clustering_path.rglob('*'))}"
            )
        model_tar = candidates[0]

    print(f"Extracting {model_tar} ...")
    with tarfile.open(model_tar, "r:gz") as tar:
        tar.extractall(path=clustering_path)

    csv_files = list(clustering_path.rglob("customer_clusters.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"customer_clusters.csv not found after extracting {model_tar}.\n"
            f"Contents: {list(clustering_path.rglob('*'))}"
        )

    print(f"Extracted: {csv_files[0]}")
    return csv_files[0].parent


def main():

    # FIX (runtime): The clustering input directory contains output.tar.gz from
    # the Training Job — SageMaker does not auto-extract tars in Processing
    # containers so we do it here before reading customer_clusters.csv.
    clustering_dir = extract_clustering_output("/opt/ml/processing/input/clustering")
    clusters_csv   = clustering_dir / "customer_clusters.csv"

    invoices = pd.read_csv("/opt/ml/processing/input/invoices/invoice.csv")
    clusters = pd.read_csv(clusters_csv)

    invoices["invoice_date"] = pd.to_datetime(invoices["invoice_date"], utc=True)
    invoices["invoice_date"] = invoices["invoice_date"].dt.tz_convert(None)

    invoices["customer_id"] = invoices["customer_id"].astype(str)
    invoices["product_id"]  = invoices["product_id"].astype(str)
    clusters["customer_id"] = clusters["customer_id"].astype(str)

    # --------------------------------------------------
    # CREATE TRUE BASKETS (PURCHASE SESSIONS)
    # --------------------------------------------------
    invoices = invoices.sort_values(["customer_id", "invoice_date"])

    invoices["prev_date"]   = invoices.groupby("customer_id")["invoice_date"].shift(1)
    invoices["gap"]         = (invoices["invoice_date"] - invoices["prev_date"]).dt.days
    invoices["new_basket"]  = (invoices["gap"] > WINDOW_DAYS) | invoices["gap"].isna()
    invoices["basket_id"]   = invoices.groupby("customer_id")["new_basket"].cumsum()

    # Left join so customers absent from clusters are logged, not silently dropped
    df = invoices.merge(clusters, on="customer_id", how="left")

    unmatched = df["cluster_id"].isna().sum()
    if unmatched:
        print(f"WARNING: {unmatched} invoice rows have no cluster assignment — excluded from association mining")

    df = df.dropna(subset=["cluster_id"])

    rows = []

    # --------------------------------------------------
    # BUILD CO-OCCURRENCE PAIRS PER BASKET SESSION
    # --------------------------------------------------
    for (segment, cluster, cust, basket), g in df.groupby(
        ["segment", "cluster_id", "customer_id", "basket_id"]
    ):
        products = list(set(g["product_id"]))

        if len(products) < 2:
            continue

        for a, b in combinations(products, 2):
            rows.append((segment, cluster, a, b))
            rows.append((segment, cluster, b, a))

    if not rows:
        print("WARNING: No co-occurrence pairs found. Association rules will be empty.")
        Path("/opt/ml/processing/output").mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            columns=["segment", "cluster_id", "product_a", "product_b",
                     "pair_freq", "product_freq", "confidence", "support"]
        ).to_csv("/opt/ml/processing/output/associations.csv", index=False)
        return

    pairs = pd.DataFrame(rows, columns=["segment", "cluster_id", "product_a", "product_b"])

    # pair_freq = number of baskets in which A and B co-occurred
    pair_counts = (
        pairs.groupby(["segment", "cluster_id", "product_a", "product_b"])
        .size()
        .reset_index(name="pair_freq")
    )

    # product_freq = number of unique baskets containing product_a
    product_counts = (
        df.groupby(["segment", "cluster_id", "product_id"])["basket_id"]
        .nunique()
        .reset_index(name="product_freq")
        .rename(columns={"product_id": "product_a"})
    )

    pair_counts = pair_counts.merge(
        product_counts,
        on=["segment", "cluster_id", "product_a"],
        how="left",
    )

    pair_counts["confidence"] = pair_counts["pair_freq"] / pair_counts["product_freq"]

    # Vectorized support — avoids slow row-wise apply
    total_baskets = (
        df.groupby(["segment", "cluster_id"])["basket_id"]
        .nunique()
        .reset_index(name="total_baskets")
    )

    pair_counts = pair_counts.merge(
        total_baskets,
        on=["segment", "cluster_id"],
        how="left",
    )

    pair_counts["support"] = pair_counts["pair_freq"] / pair_counts["total_baskets"]

    assert (pair_counts["confidence"] <= 1.0 + 1e-9).all(), \
        "confidence > 1.0 — check pair_freq vs product_freq"
    assert (pair_counts["support"] <= 1.0 + 1e-9).all(), \
        "support > 1.0 — check pair_freq vs total_baskets"

    pair_counts = pair_counts.drop(columns=["total_baskets"])
    pair_counts = pair_counts[pair_counts["product_freq"] >= 5]

    Path("/opt/ml/processing/output").mkdir(parents=True, exist_ok=True)
    pair_counts.to_csv("/opt/ml/processing/output/associations.csv", index=False)

    print("Final association rules:", len(pair_counts))


if __name__ == "__main__":
    main()
