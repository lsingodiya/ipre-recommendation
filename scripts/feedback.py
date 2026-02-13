import pandas as pd
import boto3
import io

BUCKET = "ipre-poc"
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
# Main
# --------------------------------------------------
def main():

    print("Loading recommendations...")

    reco = read_csv_s3("outputs/recommendations/recommendations.csv")

    # feedback file may or may not exist (safe handling)
    try:
        feedback = read_csv_s3("feedback/feedback.csv")
        print("Feedback loaded:", len(feedback))
    except Exception:
        print("No feedback found. Skipping calibration.")

        write_csv_s3(
            reco,
            "outputs/recommendations/final_recommendations.csv"
        )
        return

    # --------------------------------------------------
    # Merge feedback
    # --------------------------------------------------
    df = reco.merge(
        feedback,
        how="left",
        left_on=["customer_id", "recommended_product"],
        right_on=["customer_id", "product_id"]
    )

    # --------------------------------------------------
    # Simple business rules (NOT ML)
    # --------------------------------------------------
    score_weight = {
        "High": 1.2,
        "Medium": 1.0,
        "Low": 0.3
    }

    df["rating_weight"] = df["rating"].map(score_weight).fillna(1.0)

    df["score"] = df["score"] * df["rating_weight"]

    # Remove very low scored items
    df = df[df["score"] > 0.1]

    # Re-rank
    df["rank"] = df.groupby("customer_id")["score"] \
                   .rank(ascending=False, method="first")

    # Clean columns
    df = df.drop(columns=["product_id", "rating", "rating_weight"], errors="ignore")

    # --------------------------------------------------
    # Save final output
    # --------------------------------------------------
    write_csv_s3(
        df,
        "outputs/recommendations/final_recommendations.csv"
    )

    print("✅ Final recommendations saved")


# --------------------------------------------------
if __name__ == "__main__":
    main()
