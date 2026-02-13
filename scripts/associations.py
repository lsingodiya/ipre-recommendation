import pandas as pd
import boto3
import io
from itertools import combinations

BUCKET = "ipre-poc"
s3 = boto3.client("s3")


def read_csv_s3(key):
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return pd.read_csv(obj["Body"])


def write_csv_s3(df, key):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())


def main():

    basket = read_csv_s3("processed/market_basket/market_basket.csv")
    clusters = read_csv_s3("models/clustering/customer_clusters.csv")

    df = basket.merge(clusters, on="customer_id")

    rows = []

    # --------------------------------------------------
    # SEGMENT AWARE PAIRS (CRITICAL FIX)
    # --------------------------------------------------
    for (segment, cluster, cust), g in df.groupby(["segment", "cluster_id", "customer_id"]):

        prods = list(set(g["product_id"]))

        for a, b in combinations(prods, 2):
            rows.append((segment, cluster, a, b))
            rows.append((segment, cluster, b, a))

    pairs = pd.DataFrame(
        rows,
        columns=["segment", "cluster_id", "product_a", "product_b"]
    )

    pair_counts = (
        pairs.groupby(["segment", "cluster_id", "product_a", "product_b"])
        .size()
        .reset_index(name="pair_freq")
    )

    cluster_sizes = df.groupby(["segment", "cluster_id"])["customer_id"].nunique()

    pair_counts["support"] = pair_counts.apply(
        lambda r: r.pair_freq / cluster_sizes[(r.segment, r.cluster_id)],
        axis=1
    )

    pair_counts["confidence"] = pair_counts["support"]

    write_csv_s3(pair_counts, "models/associations/associations.csv")

    print("✅ Segment-aware associations created:", len(pair_counts))


if __name__ == "__main__":
    main()
