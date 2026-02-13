import pandas as pd
import boto3, io

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
    assoc = read_csv_s3("models/associations/cluster_product_associations.csv")

    df = basket.merge(clusters, on="customer_id")

    cust_products = df.groupby("customer_id")["product_id"].apply(set)

    rows = []

    for cust, bought in cust_products.items():
        cluster = clusters.loc[clusters.customer_id == cust, "cluster_id"].iloc[0]
        cluster_assoc = assoc[assoc.cluster_id == cluster]

        for _, r in cluster_assoc.iterrows():
            if r.product_a in bought and r.product_b not in bought:
                rows.append((cust, r.product_b, r.confidence))

    out = pd.DataFrame(rows, columns=["customer_id","recommended_product","confidence"])

    write_csv_s3(out, "outputs/recommendations/customer_recommendations.csv")
    print("Recommendations saved")


if __name__ == "__main__":
    main()
