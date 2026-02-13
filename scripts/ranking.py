import pandas as pd
import boto3
import io

# ==================================================
# CONFIG (tune for business)
# ==================================================
BUCKET = "ipre-poc"

MIN_SUPPORT = 0.05       # remove weak rules
MIN_CONFIDENCE = 0.05
TOP_K = 5                # max recommendations per customer

# scoring weights
W_CONF = 0.5
W_SUPP = 0.3
W_RECENCY = 0.2
# ==================================================

s3 = boto3.client("s3")


# --------------------------------------------------
# S3 helpers
# --------------------------------------------------
def read_csv_s3(key):
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return pd.read_csv(obj["Body"])


def write_csv_s3(df, key):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())


# --------------------------------------------------
# Main ranking logic
# --------------------------------------------------
def main():

    print("Loading inputs...")

    basket = read_csv_s3("processed/market_basket/market_basket.csv")
    clusters = read_csv_s3("models/clustering/customer_clusters.csv")
    assoc = read_csv_s3("models/associations/associations.csv")

    df = basket.merge(clusters, on="customer_id")

    print("Customers:", df.customer_id.nunique())
    print("Association rules:", len(assoc))

    # --------------------------------------------------
    # Precompute customer purchases
    # --------------------------------------------------
    cust_products = df.groupby("customer_id")["product_id"].apply(set)

    rows = []

    # --------------------------------------------------
    # Generate candidate recommendations
    # --------------------------------------------------
    for cust, bought in cust_products.items():

        cust_rows = df[df.customer_id == cust]

        cluster = cust_rows["cluster_id"].iloc[0]
        segment = cust_rows["segment"].iloc[0]

        rules = assoc[
            (assoc.cluster_id == cluster) &
            (assoc.segment == segment)
        ]

        avg_qty = cust_rows["total_quantity"].mean()
        qty = max(1, int(round(avg_qty)))

        recency_score = 1 / (1 + cust_rows["recency_days"].mean())

        for _, r in rules.iterrows():

            # skip already purchased
            if r.product_b in bought:
                continue

            # skip weak rules
            if r.support < MIN_SUPPORT or r.confidence < MIN_CONFIDENCE:
                continue

            score = (
                W_CONF * r.confidence +
                W_SUPP * r.support +
                W_RECENCY * recency_score
            )

            rows.append((
                cust,
                r.product_b,
                cluster,
                segment,
                r.product_a,
                r.support,
                r.confidence,
                score,
                qty,
                f"{r.product_a} → {r.product_b} "
                f"(support={round(r.support,2)}, confidence={round(r.confidence,2)})"
            ))

    if not rows:
        print("No recommendations generated")
        return

    out = pd.DataFrame(rows, columns=[
        "customer_id",
        "recommended_product",
        "cluster_id",
        "segment",
        "trigger_product",
        "support",
        "confidence",
        "score",
        "recommended_qty",
        "reason"
    ])

    # --------------------------------------------------
    # Rank + Top-K filtering
    # --------------------------------------------------
    out["rank"] = (
        out.groupby("customer_id")["score"]
        .rank(ascending=False, method="first")
    )

    out = out[out["rank"] <= TOP_K]

    out = out.sort_values(["customer_id", "rank"])

    # --------------------------------------------------
    # Save
    # --------------------------------------------------
    write_csv_s3(out, "outputs/recommendations/recommendations.csv")

    print("✅ Final recommendations:", len(out))
    print("Coverage:", out.customer_id.nunique())


# --------------------------------------------------
if __name__ == "__main__":
    main()
