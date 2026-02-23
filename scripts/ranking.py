import tarfile
import pandas as pd
from pathlib import Path


def extract_clustering_output(clustering_dir: str) -> Path:
    """
    The Ranking step receives ModelArtifacts.S3ModelArtifacts as input,
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
    model_tar = clustering_path / "model.tar.gz"
    if not model_tar.exists():
        candidates = list(clustering_path.rglob("model.tar.gz"))
        if not candidates:
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

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
MIN_SUPPORT    = 0.01   # lowered from 0.03 — original was too tight for small datasets,
MIN_CONFIDENCE = 0.05   # lowered from 0.10   causing 62.5% of segment customers to get nothing
TOP_K          = 5

# Scoring weights (must sum to 1.0)
W_CONF    = 0.60
W_SUPP    = 0.25
W_RECENCY = 0.15


def build_quantity_lookup(basket: pd.DataFrame) -> dict:
    """
    Pre-compute per-order quantity estimates for every (customer_id, product_id)
    pair as a dict for O(1) lookup during recommendation generation.

    FIX (previous review): Previously estimate_quantity() filtered the basket
    DataFrame inside the inner recommendation loop, performing up to
    customers*rules individual masking operations. Pre-building a dict cuts
    this to a single pass.
    """
    qty_map = {}
    for (cust, prod), g in basket.groupby(["customer_id", "product_id"]):
        per_order = g["total_quantity"] / g["purchase_frequency"]
        qty_map[(cust, prod)] = int(max(1, round(per_order.median())))
    return qty_map


def fallback_recommendations(
    df: pd.DataFrame,
    basket: pd.DataFrame,
    cust_products,
    already_bought_map: dict,
) -> list:
    """
    Segment popularity fallback for customers who received zero association-based
    recommendations. Excludes products the customer already bought.

    FIX (previous review): Previously returned 11-element tuples (with a
    pre-baked rank) while the main loop returned 10-element tuples, causing
    pd.DataFrame to crash with a column count mismatch. Rank removed here;
    applied uniformly downstream.

    FIX (validation): Added already_bought_map so fallback products are also
    filtered against purchase history — previously the fallback skipped this
    check entirely.

    FIX (runtime): basket does not contain a 'segment' column — segment is
    only created in clustering.py and exists in df (basket merged with clusters).
    Popularity must be computed from df, not basket.
    """
    print("Applying per-customer fallback recommendations...")

    popularity = (
        df.groupby(["segment", "product_id"])["purchase_frequency"]
        .sum()
        .reset_index()
        .sort_values("purchase_frequency", ascending=False)
    )

    rows = []

    for cust in cust_products.index:

        cust_rows = df[df.customer_id == cust]
        if cust_rows.empty:
            continue

        segment = cust_rows["segment"].iloc[0]
        cluster = cust_rows["cluster_id"].iloc[0]
        bought  = already_bought_map.get(cust, set())

        # Top popular products in segment that the customer hasn't bought yet
        segment_popular = popularity[
            (popularity.segment == segment) &
            (~popularity.product_id.isin(bought))
        ].head(TOP_K)

        for _, p in segment_popular.iterrows():
            rows.append((
                cust,
                p.product_id,
                cluster,
                segment,
                "popular_product",
                0.0,
                0.0,
                0.1,
                1,
                "Popular product in your segment",
            ))

    return rows


def main():

    print("Loading pipeline inputs...")

    # FIX (runtime): The clustering input directory contains output.tar.gz from
    # the Training Job — SageMaker does not auto-extract tars in Processing
    # containers so we do it here before reading customer_clusters.csv.
    clustering_dir = extract_clustering_output("/opt/ml/processing/input/clustering")
    clusters_csv   = clustering_dir / "customer_clusters.csv"

    basket   = pd.read_csv("/opt/ml/processing/input/market_basket/market_basket.csv")
    clusters = pd.read_csv(clusters_csv)
    assoc    = pd.read_csv("/opt/ml/processing/input/associations/associations.csv")

    basket["customer_id"]   = basket["customer_id"].astype(str)
    basket["product_id"]    = basket["product_id"].astype(str)
    clusters["customer_id"] = clusters["customer_id"].astype(str)

    # FIX (previous review): Use left join so customers in the basket but absent
    # from clusters are logged rather than silently dropped.
    df = basket.merge(clusters, on="customer_id", how="left")

    unmatched = df["cluster_id"].isna().sum()
    if unmatched:
        print(f"WARNING: {unmatched} basket rows have no cluster — those customers may miss recommendations")

    df = df.dropna(subset=["cluster_id"])

    # FIX (previous review): Pre-build quantity lookup dict — avoids
    # O(customers*rules) DataFrame mask operations inside the inner loop.
    qty_lookup = build_quantity_lookup(basket)

    cust_products     = df.groupby("customer_id")["product_id"].apply(set)
    bought_map        = cust_products.to_dict()  # plain dict for fallback lookup
    customers_with_recs = set()

    rows = []

    # --------------------------------------------------
    # MAIN RECOMMENDER
    # --------------------------------------------------
    for cust, bought in cust_products.items():

        cust_rows = df[df.customer_id == cust]

        # FIX (previous review): Validate single cluster+segment per customer.
        if cust_rows["cluster_id"].nunique() > 1:
            print(f"WARNING: customer {cust} maps to multiple clusters — using first")
        if cust_rows["segment"].nunique() > 1:
            print(f"WARNING: customer {cust} maps to multiple segments — using first")

        cluster = cust_rows["cluster_id"].iloc[0]
        segment = cust_rows["segment"].iloc[0]

        rules = assoc[
            (assoc.cluster_id == cluster) &
            (assoc.segment    == segment)
        ]

        recency_score = 1 / (1 + cust_rows["recency_days"].mean())

        rows_before = len(rows)

        for _, r in rules.iterrows():

            # Filter out already-purchased recommendation targets
            if r.product_b in bought:
                continue

            # FIX (validation): Filter out rules where the customer never
            # purchased the trigger product. Previously this check was missing,
            # causing customers to receive recommendations driven by a product
            # they never bought. An association rule A->B is only valid for a
            # customer if they have actually purchased A.
            if r.product_a not in bought:
                continue

            if r.support < MIN_SUPPORT or r.confidence < MIN_CONFIDENCE:
                continue

            qty = qty_lookup.get((cust, r.product_a), 1)

            score = (
                W_CONF    * r.confidence +
                W_SUPP    * r.support +
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
                f"{r.product_a} -> {r.product_b} "
                f"(support={round(r.support, 2)}, confidence={round(r.confidence, 2)})",
            ))

        if len(rows) > rows_before:
            customers_with_recs.add(cust)

    # --------------------------------------------------
    # FIX (validation): Per-customer fallback instead of global fallback.
    # Previously the fallback only triggered when rows was completely empty,
    # meaning customers with no qualifying rules were silently skipped as long
    # as any other customer had recommendations. In the validation run, 10 of
    # 16 segment customers received nothing. Now we identify specifically which
    # customers have zero rows and apply the fallback only to them, guaranteeing
    # every customer gets up to TOP_K recommendations.
    # --------------------------------------------------
    uncovered = [c for c in cust_products.index if c not in customers_with_recs]

    if uncovered:
        print(f"{len(uncovered)} customers had no association-based recs — applying fallback")
        fallback_series = pd.Series({c: cust_products[c] for c in uncovered})
        rows += fallback_recommendations(df, basket, fallback_series, bought_map)
    else:
        print("All customers covered by association rules — no fallback needed")

    # --------------------------------------------------
    # FORMAT OUTPUT
    # --------------------------------------------------
    # 10 columns — matches both main loop (10-tuple) and fallback (10-tuple)
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
        "reason",
    ])

    out["rank"] = (
        out.groupby("customer_id")["score"]
        .rank(ascending=False, method="first")
    )

    out = out[out["rank"] <= TOP_K]
    out = out.sort_values(["customer_id", "rank"])

    # --------------------------------------------------
    # SAVE
    # --------------------------------------------------
    Path("/opt/ml/processing/output").mkdir(parents=True, exist_ok=True)
    out.to_csv("/opt/ml/processing/output/recommendations.csv", index=False)

    print("Recommendations generated:", len(out))
    print("Customers covered:", out.customer_id.nunique())
    print(
        "Via fallback:",
        out[out["trigger_product"] == "popular_product"]["customer_id"].nunique(),
    )


if __name__ == "__main__":
    main()
