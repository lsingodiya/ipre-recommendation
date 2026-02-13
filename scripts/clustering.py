import pandas as pd
import boto3
import io
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

BUCKET = "ipre-poc"
s3 = boto3.client("s3")


# --------------------------------------------------
# S3 helpers
# --------------------------------------------------
def read_csv_s3(key: str) -> pd.DataFrame:
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return pd.read_csv(obj["Body"])


def write_csv_s3(df: pd.DataFrame, key: str):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())


# --------------------------------------------------
# Main
# --------------------------------------------------
def main():

    print("Loading market basket...")
    df = read_csv_s3("processed/market_basket/market_basket.csv")

    df["segment"] = df["region"] + "_" + df["end_use"]

    outputs = []

    for segment, sdf in df.groupby("segment"):

        print(f"Clustering segment: {segment}")

        pivot = sdf.pivot_table(
            index="customer_id",
            columns="l2_category",
            values="total_quantity",
            aggfunc="sum",
            fill_value=0
        )

        features = pivot.reset_index()

        X = features.drop(columns=["customer_id"])

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # --------------------------------------------------
        # SAFE cluster rule (NO silhouette for tiny data)
        # --------------------------------------------------
        n = len(X_scaled)

        if n < 6:
            k = 1
        else:
            k = min(4, int(n ** 0.5))

        print(f"Customers: {n} → clusters: {k}")

        kmeans = KMeans(
            n_clusters=k,
            random_state=42,
            n_init=10
        )

        labels = kmeans.fit_predict(X_scaled)

        out = pd.DataFrame({
            "customer_id": features["customer_id"],
            "cluster_id": labels,
            "segment": segment
        })

        outputs.append(out)

    final = pd.concat(outputs, ignore_index=True)

    write_csv_s3(final, "models/clustering/customer_clusters.csv")

    print("✅ Clustering complete")
    print(final.head())


# --------------------------------------------------
if __name__ == "__main__":
    main()