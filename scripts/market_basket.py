import pandas as pd
from pathlib import Path

# --------------------------------------------------
# Local SageMaker Processing Paths
# --------------------------------------------------
CUSTOMERS_PATH = "/opt/ml/processing/input/customers/customer.csv"
PRODUCTS_PATH  = "/opt/ml/processing/input/products/product.csv"
INVOICES_PATH  = "/opt/ml/processing/input/invoices/invoice.csv"

OUTPUT_PATH = "/opt/ml/processing/output/market_basket.csv"


def main():

    print("Loading input datasets from Processing container...")

    customers = pd.read_csv(CUSTOMERS_PATH)
    products  = pd.read_csv(PRODUCTS_PATH)
    invoices  = pd.read_csv(INVOICES_PATH)

    print("Invoices:", len(invoices))
    print("Products:", len(products))
    print("Customers:", len(customers))

    # --------------------------------------------------
    # Normalize key types
    # --------------------------------------------------
    invoices["customer_id"] = invoices["customer_id"].astype(str)
    invoices["product_id"]  = invoices["product_id"].astype(str)

    products["product_id"]  = products["product_id"].astype(str)
    customers["customer_id"] = customers["customer_id"].astype(str)

    # --------------------------------------------------
    # Joins
    # --------------------------------------------------
    df = (
        invoices
        .merge(products,   on="product_id",  how="left")
        .merge(customers,  on="customer_id", how="left")
    )

    print("After joins:", len(df))

    # Log join match rates to surface data quality issues early
    unmatched_products  = df["brand"].isna().sum()
    unmatched_customers = df["region"].isna().sum()
    if unmatched_products:
        print(f"WARNING: {unmatched_products} invoice rows had no matching product")
    if unmatched_customers:
        print(f"WARNING: {unmatched_customers} invoice rows had no matching customer")

    # --------------------------------------------------
    # Categorical cleanup
    # FIX: fillna BEFORE astype(str) — astype converts NaN to literal "nan"
    # which then doesn't match fillna's NaN sentinel.
    # --------------------------------------------------
    cat_cols = [
        "region",
        "end_use",
        "brand",
        "l2_category",
        "l3_category",
        "functionality",
    ]

    for c in cat_cols:
        if c not in df.columns:
            df[c] = "Unknown"
        df[c] = df[c].fillna("Unknown").astype(str)

    # --------------------------------------------------
    # Numeric cleanup
    # --------------------------------------------------
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)

    # --------------------------------------------------
    # Date parsing
    # FIX: use dt.tz_convert(None) to safely strip timezone info whether
    # timestamps are tz-aware or tz-naive, avoiding TypeError on mixed columns.
    # --------------------------------------------------
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce", utc=True)
    df["invoice_date"] = df["invoice_date"].dt.tz_convert(None)

    # --------------------------------------------------
    # Recency calculation
    # FIX: use dataset max date instead of wall-clock now() so that
    # recency_days is reproducible across pipeline reruns and backfills.
    # --------------------------------------------------
    latest_date = df["invoice_date"].max()
    if pd.isnull(latest_date):
        print("WARNING: No valid invoice dates found; recency_days will be 0")
        latest_date = pd.Timestamp.now()

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
                "functionality",
            ],
            dropna=False,
        )
        .agg(
            purchase_frequency=("product_id", "count"),
            total_quantity=("quantity", "sum"),
            recency_days=(
                "invoice_date",
                lambda x: int((latest_date - x.max()).days)
                if pd.notnull(x.max()) else 0,
            ),
        )
        .reset_index()
    )

    if grouped.empty:
        raise ValueError("Market basket is empty after aggregation")

    # --------------------------------------------------
    # Save output
    # --------------------------------------------------
    Path("/opt/ml/processing/output").mkdir(parents=True, exist_ok=True)
    grouped.to_csv(OUTPUT_PATH, index=False)

    print("Market basket created:", len(grouped))


if __name__ == "__main__":
    main()
