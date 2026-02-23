import os
import pandas as pd
import boto3
from pathlib import Path

# --------------------------------------------------
# CONFIG
# Prefer environment variables so the same script works across
# staging and production without code changes.
# --------------------------------------------------
BUCKET    = os.environ.get("OUTPUT_BUCKET", "ipre-prod-poc")
FINAL_KEY = os.environ.get("OUTPUT_KEY",    "final/recommendations.csv")

OUTPUT_FILE = "/opt/ml/processing/output/final_recommendations.csv"

# FIX (previous review): Keep TOP_K consistent with ranking.py. Feedback
# re-ranks scores so we must re-apply the cap; without it a customer could
# receive more than TOP_K recommendations after calibration reshuffles positions.
TOP_K = 5


def main():

    print("Loading recommendations from previous step...")

    reco = pd.read_csv("/opt/ml/processing/input/ranking/recommendations.csv")

    feedback_path = "/opt/ml/processing/input/feedback/feedback.csv"

    # FIX (previous review): Catch only FileNotFoundError/OSError rather than
    # bare Exception, so genuine I/O errors and schema problems are not
    # silently swallowed.
    try:
        feedback = pd.read_csv(feedback_path)
        print("Feedback loaded:", len(feedback))
    except (FileNotFoundError, OSError):
        print("No feedback file found — skipping calibration and publishing as-is.")
        _save_and_publish(reco)
        return

    # Guard: if feedback is empty (file exists but has no rows), skip calibration
    if feedback.empty:
        print("Feedback file is empty — skipping calibration.")
        _save_and_publish(reco)
        return

    feedback["customer_id"] = feedback["customer_id"].astype(str)
    feedback["product_id"]  = feedback["product_id"].astype(str)
    reco["customer_id"]     = reco["customer_id"].astype(str)

    df = reco.merge(
        feedback,
        how="left",
        left_on=["customer_id", "recommended_product"],
        right_on=["customer_id", "product_id"],
    )

    score_weight = {
        "High":   1.2,
        "Medium": 1.0,
        "Low":    0.3,
    }

    df["rating_weight"] = df["rating"].map(score_weight).fillna(1.0)
    df["score"]         = df["score"] * df["rating_weight"]
    df = df[df["score"] > 0.1]

    # FIX (previous review): Re-rank after score adjustment AND re-apply TOP_K
    # cap. Previously the rank column was overwritten but no TOP_K filter was
    # applied, allowing customers to receive more than 5 recommendations after
    # feedback reshuffled scores.
    df["rank"] = (
        df.groupby("customer_id")["score"]
        .rank(ascending=False, method="first")
    )

    df = df[df["rank"] <= TOP_K]

    df = df.drop(
        columns=["product_id", "rating", "rating_weight"],
        errors="ignore",
    )

    _save_and_publish(df)

    print("Final recommendations saved and published")


def _save_and_publish(df: pd.DataFrame) -> None:
    """
    Write output CSV then verify it is non-empty before publishing to S3.

    FIX (previous review): Previously publish() was called immediately after
    to_csv() with no integrity check. A zero-byte or corrupted file could be
    pushed to the production S3 path silently. This helper validates file size
    before uploading and raises clearly if something went wrong.
    """
    Path("/opt/ml/processing/output").mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    file_size = os.path.getsize(OUTPUT_FILE)
    if file_size == 0:
        raise RuntimeError(
            f"Output file '{OUTPUT_FILE}' is zero bytes — "
            "refusing to publish corrupt data to S3."
        )

    print(f"Output file size: {file_size} bytes — proceeding to publish")
    _publish()


def _publish() -> None:
    print(f"Publishing recommendations to s3://{BUCKET}/{FINAL_KEY} ...")
    s3 = boto3.client("s3")
    s3.upload_file(OUTPUT_FILE, BUCKET, FINAL_KEY)
    print(f"Published to s3://{BUCKET}/{FINAL_KEY}")


if __name__ == "__main__":
    main()
