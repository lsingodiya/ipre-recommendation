import pandas as pd
import boto3
import io

# --------------------------------------------------
# Config
# --------------------------------------------------
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

    print("Loading raw data...")

    invoices = read_csv_s3("raw/invoices/invoices.csv")
    products = read_csv_s3("raw/products/products.csv")
    customers = read_csv_s3("raw/customers/customers.csv")

    print("Invoices:", len(invoices))
    print("Products:", len(products))
    print("Customers:", len(customers))

    # --------------------------------------------------
    # 1. Normalize key types (VERY IMPORTANT)
    # --------------------------------------------------
    invoices["customer_id"] = invoices["customer_id"].astype(str)
    invoices["product_id"] = invoices["product_id"].astype(str)

    products["product_id"] = products["product_id"].astype(str)
    customers["customer_id"] = customers["customer_id"].astype(str)

    # --------------------------------------------------
    # 2. Safe joins (LEFT ONLY)
    # --------------------------------------------------
    df = (
        invoices
        .merge(products, on="product_id", how="left")
        .merge(customers, on="customer_id", how="left")
    )

    print("After joins:", len(df))

    # --------------------------------------------------
    # 3. Fix categorical columns
    # --------------------------------------------------
    cat_cols = [
        "region",
        "end_use",
        "brand",
        "l2_category",
        "l3_category",
        "functionality"
    ]

    for c in cat_cols:
        if c not in df.columns:
            df[c] = "Unknown"

        df[c] = df[c].astype(str).fillna("Unknown")

    # --------------------------------------------------
    # 4. Fix numeric columns
    # --------------------------------------------------
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)

    # --------------------------------------------------
    # 🔥 5. SAFE DATETIME HANDLING (FIXES YOUR ERROR)
    # --------------------------------------------------
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")

    # Remove timezone completely (critical fix)
    df["invoice_date"] = df["invoice_date"].dt.tz_localize(None)

    # Use current time for recency
    latest_date = pd.Timestamp.now().tz_localize(None)

    # --------------------------------------------------
    # 6. Build market basket features
    # --------------------------------------------------
    print("Building market basket...")

    grouped = (
        df.groupby(
            [
                "customer_id",
                "region",
                "end_use",
                "product_id",
                "brand",
                "l2_category",
                "l3_category",
                "functionality"
            ],
            dropna=False
        )
        .agg(
            purchase_frequency=("product_id", "count"),
            total_quantity=("quantity", "sum"),
            recency_days=(
                "invoice_date",
                lambda x: int((latest_date - x.max()).days)
                if pd.notnull(x.max()) else 0
            )
        )
        .reset_index()
    )

    print("Market basket rows:", len(grouped))

    # --------------------------------------------------
    # Safety check
    # --------------------------------------------------
    if grouped.empty:
        raise ValueError("Market basket is empty. Check raw data or joins.")

    # --------------------------------------------------
    # 7. Save output
    # --------------------------------------------------
    write_csv_s3(grouped, "processed/market_basket/market_basket.csv")

    print("✅ Market basket saved successfully")


# --------------------------------------------------
if __name__ == "__main__":
    main()
