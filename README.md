# IPRE — Intelligent Product Recommendation Engine
## Technical Documentation

**Version:** 1.0 (POC)
**Platform:** AWS SageMaker
**Last Updated:** February 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Data Sources & Schema](#3-data-sources--schema)
4. [Pipeline Steps — Detailed Walkthrough](#4-pipeline-steps--detailed-walkthrough)
   - 4.1 [Step 1 — Market Basket Creation](#41-step-1--market-basket-creation)
   - 4.2 [Step 2 — Customer Clustering](#42-step-2--customer-clustering)
   - 4.3 [Step 3 — Model Registry](#43-step-3--model-registry)
   - 4.4 [Step 4 — Association Mining](#44-step-4--association-mining)
   - 4.5 [Step 5 — Ranking](#45-step-5--ranking)
   - 4.6 [Step 6 — Feedback Calibration](#46-step-6--feedback-calibration)
5. [Pipeline Parameters — Complete Reference](#5-pipeline-parameters--complete-reference)
6. [Output Schema](#6-output-schema)
7. [Key Algorithms & Design Decisions](#7-key-algorithms--design-decisions)
8. [Bugs Fixed During Development](#8-bugs-fixed-during-development)
9. [Endpoint & Salesforce Integration](#9-endpoint--salesforce-integration)
10. [How to Run](#10-how-to-run)
11. [Monitoring & Observability](#11-monitoring--observability)
12. [Validation Results (POC)](#12-validation-results-poc)
13. [Known Limitations & Next Steps](#13-known-limitations--next-steps)

---

## 1. Project Overview

IPRE (Intelligent Product Recommendation Engine) is an end-to-end machine learning pipeline built on AWS SageMaker that generates personalised product recommendations for Account Managers in a B2B distribution context.

### What It Does

Given a customer's historical purchase behaviour, IPRE recommends up to 5 products per customer that they have not yet purchased but are likely to need — ranked by a composite score based on association strength, lift, recency, and category affinity.

### Who Uses It

- **Account Managers** — receive recommendations in Salesforce CRM (via Einstein Co-Pilot) before customer visits
- **Sales Leaders** — monitor recommendation quality and acceptance rates
- **Data/ML Team** — run and tune the pipeline via SageMaker Studio

### POC Results (February 2026)

| Metric | Value |
|--------|-------|
| Customers covered | 477 |
| Total recommendations | 2,342 |
| Products recommended | 208 unique |
| Segments covered | 54 |
| Clusters discovered | 230 |
| Association rule rows | 662 |
| Customers with genuine association recs | 225 |
| Lift range | 1.33 – 31.0 |
| Confidence range | 0.14 – 0.75 |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        S3: ipre-prod-poc                        │
│  /raw/customers/    /raw/products/    /raw/invoices/            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Step 1         │
                    │  Market Basket  │  ProcessingJob (ml.t3.xlarge)
                    │  market_basket  │  → market_basket.csv
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Step 2         │
                    │  Clustering     │  TrainingJob (ml.m5.xlarge)
                    │  Train KMeans   │  → model.tar.gz
                    └────┬───────┬────┘     (KMeans pickles +
                         │       │           customer_clusters.csv)
                    ┌────▼──┐ ┌──▼───────────────┐
                    │Step 3 │ │  Step 4           │
                    │Model  │ │  Associations     │  ProcessingJob
                    │Registr│ │  associations.py  │  (ml.m5.xlarge)
                    └───────┘ └──────────┬────────┘
                                         │ associations.csv
                                ┌────────▼────────┐
                                │  Step 5         │
                                │  Ranking        │  ProcessingJob
                                │  ranking.py     │  (ml.m5.large)
                                └────────┬────────┘
                                         │ recommendations.csv
                                ┌────────▼────────┐
                                │  Step 6         │
                                │  Feedback       │  ProcessingJob
                                │  feedback.py    │  (ml.t3.xlarge)
                                └────────┬────────┘
                                         │
                              ┌──────────▼──────────┐
                              │  S3 Final Output    │
                              │  /final/            │
                              │  recommendations.csv│
                              │  + feedback_summary │
                              └──────────┬──────────┘
                                         │
                              ┌──────────▼──────────┐
                              │  SageMaker Endpoint │
                              │  inference.py       │
                              │  (REST API)         │
                              └──────────┬──────────┘
                                         │
                              ┌──────────▼──────────┐
                              │  Salesforce CRM     │
                              │  Einstein Co-Pilot  │
                              └─────────────────────┘
```

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Orchestration | AWS SageMaker Pipelines |
| Clustering | scikit-learn KMeans + StandardScaler |
| Association Mining | Custom Apriori implementation (pandas) |
| Scoring | Custom composite formula |
| Storage | Amazon S3 |
| Serving | SageMaker Endpoint (sklearn container) |
| CRM Integration | Salesforce Einstein Co-Pilot (Named Credential) |
| Monitoring | AWS CloudWatch |

---

## 3. Data Sources & Schema

All raw data lives in S3 under `s3://ipre-prod-poc/raw/`.

### 3.1 customers.csv

| Column | Type | Description |
|--------|------|-------------|
| `customer_id` | string | Unique customer identifier (e.g. C00001) |
| `region` | string | Geographic region (e.g. West, Southeast) |
| `end_use` | string | Industry/use-case (e.g. Plumbing, HVAC) |

### 3.2 products.csv

| Column | Type | Description |
|--------|------|-------------|
| `product_id` | string | Unique product identifier (e.g. P00001) |
| `brand` | string | Product brand |
| `l2_category` | string | Level-2 category (e.g. Fasteners, Plumbing) |
| `l3_category` | string | Level-3 sub-category (e.g. PVC Pipes) |
| `functionality` | string | Product function group |
| `in_stock` | boolean | Current stock availability |

### 3.3 invoices.csv

| Column | Type | Description |
|--------|------|-------------|
| `invoice_date` | datetime | Date of purchase |
| `customer_id` | string | FK → customers |
| `product_id` | string | FK → products |
| `quantity` | numeric | Units purchased |

### 3.4 feedback.csv (optional — at runtime)

| Column | Type | Description |
|--------|------|-------------|
| `customer_id` | string | FK → customers |
| `product_id` | string | Recommended product |
| `rating` | string | High / Medium / Low |
| `reason_code` | string | Mandatory for Medium/Low |
| `sentiment` | string | positive / negative (for Medium) |
| `feedback_date` | date | When feedback was given |

---

## 4. Pipeline Steps — Detailed Walkthrough

### 4.1 Step 1 — Market Basket Creation

**Script:** `market_basket.py`
**Job Type:** SageMaker Processing Job
**Instance:** `ml.t3.xlarge`

#### What It Does

Reads the three raw inputs (customers, products, invoices), joins them together, applies quality filters, and produces a single enriched `market_basket.csv` — one row per `customer_id × product_id` — that all downstream steps consume.

#### Key Processing Steps

**1. Date Parsing & Reference Date**
All invoice dates are parsed as UTC then converted to timezone-naive. The reference date is always `max(invoice_date)` — never wall clock time — ensuring reproducibility across reruns.

**2. Recency Cutoff**
Invoices older than `RECENCY_CUTOFF_DAYS` (default 730 = 2 years) are excluded before any computation. This prevents stale purchase patterns from dominating clustering features.

```
Before cutoff: 3,000 invoices
After cutoff:  1,961 invoices (34% of data was over 2 years old)
```

**3. Minimum Order Count Filter**
Customers with fewer than `MIN_ORDER_COUNT` invoices are excluded. One-time buyers have no meaningful pattern for clustering or association mining.

**4. Core Aggregation**
For each `customer_id × product_id` pair:
- `purchase_frequency` — number of distinct invoices
- `total_quantity` — sum of all units
- `total_spend` — quantity × unit_price (if price column available)
- `recency_days` — days since last purchase of this product

**5. RFM Scores**
Computed at customer level, then merged onto every row:

| Score | Formula | Meaning |
|-------|---------|---------|
| `rfm_recency_score` | `normalise(-days_since_last_purchase)` | 1.0 = most recent |
| `rfm_frequency_score` | `normalise(total_invoices)` | 1.0 = most frequent buyer |
| `rfm_monetary_score` | `normalise(total_spend)` | 1.0 = highest spender |

All scores are min-max normalised to [0, 1].

**6. Price Bands**
If a price column is found (`unit_price`, `price`, `list_price`, `unit_cost`, or `sale_price`), products are split into **Low / Mid / High** tertiles within each `region × end_use` segment. Uses local pricing context, not global.

**7. in_stock Pass-through**
The `in_stock` column from products is carried through so `ranking.py` can filter out-of-stock products in both the main and fallback paths.

#### Output Columns

```
customer_id, segment, product_id, brand, l2_category, l3_category,
functionality, in_stock, purchase_frequency, total_quantity, total_spend,
recency_days, rfm_recency, rfm_frequency, rfm_monetary,
rfm_recency_score, rfm_frequency_score, rfm_monetary_score, price_band
```

---

### 4.2 Step 2 — Customer Clustering

**Script:** `train_clustering.py`
**Job Type:** SageMaker Training Job
**Instance:** `ml.m5.xlarge`

#### What It Does

Trains one KMeans model per segment (`region_end_use`) using a rich feature matrix. Outputs model artifacts and `customer_clusters.csv` — the cluster assignment for every customer.

#### Feature Matrix

The clustering uses **4 feature groups** (all configurable via `FeatureGroups` parameter):

| Group | Features | Why Proportions Not Raw Counts |
|-------|---------|-------------------------------|
| `l2_qty` | Proportion of total_quantity per L2 category | Scale-invariant — 60% Valves looks the same whether buying 10 or 10,000 units |
| `brand` | Proportion of total_quantity per brand | Captures brand loyalty patterns |
| `functionality` | Proportion of total_quantity per functionality | Captures use-case patterns |
| `rfm` | rfm_recency_score, rfm_frequency_score, rfm_monetary_score | Captures engagement level |

Before clustering, all features are passed through `StandardScaler` so no single feature dominates due to scale differences.

**Why proportions instead of raw quantities?**
Raw quantities create outlier dominance — a customer buying 1,000 units looks like a different cluster from one buying 100 units even if their category mix is identical. Proportions capture *what* they buy, not *how much*.

#### k Selection — Elbow Method

Rather than using the arbitrary `sqrt(n)` heuristic (old approach, capped at 4), k is now selected per segment using the elbow method:

```
For k = 2 to MAX_K:
    Fit KMeans(k)
    Record inertia

Select first k where:
    (inertia[k-1] - inertia[k]) / inertia[k-1] < ELBOW_THRESHOLD%
```

This means larger, more diverse segments get more clusters. POC results: segments now have 1–8 clusters vs. the previous cap of 4.

#### Silhouette Scoring

After fitting, a silhouette score is logged for each segment:
- `> 0.5` = good cluster separation
- `0.2–0.5` = acceptable
- `< 0.2` = poor (warning logged — consider fewer feature groups or more data)

#### Model Artifacts (inside model.tar.gz)

```
model.tar.gz/
├── {segment}_kmeans.pkl      — trained KMeans per segment
├── {segment}_scaler.pkl      — fitted StandardScaler per segment
├── {segment}_columns.json    — feature column names
├── model_registry.json       — manifest with metadata for all segments
└── customer_clusters.csv     — customer → cluster assignment
```

> **Important design note:** `customer_clusters.csv` is written into `/opt/ml/model/` (not `/opt/ml/output/data/`) so it travels inside `model.tar.gz`. Downstream Processing Jobs receive this as `ModelArtifacts.S3ModelArtifacts` and extract it at runtime. SageMaker does not auto-extract tars in Processing containers — `associations.py` and `ranking.py` both handle extraction explicitly.

---

### 4.3 Step 3 — Model Registry

**Step Type:** ModelStep (SageMaker Model Registry)

Every pipeline run registers the new KMeans model into the `ipre-clustering-models` Model Package Group. This provides:
- Full version history with rollback capability
- A/B comparison between runs
- Approval gate (`ModelApprovalStatus` parameter — set to `PendingManualApproval` to require human sign-off before deployment)

---

### 4.4 Step 4 — Association Mining

**Script:** `associations.py`
**Job Type:** SageMaker Processing Job
**Instance:** `ml.m5.xlarge`

#### What It Does

Mines product co-occurrence rules within each cluster. For each cluster, computes which products tend to be purchased together and scores each pair with confidence, support, lift, and time-decayed support.

#### Basket Session Construction

Raw invoices do not come pre-sessionised. A basket is constructed by grouping consecutive purchases from the same customer within `WINDOW_DAYS` of each other.

**Data-driven window (default):** When `WINDOW_DAYS=0`, the window is computed from the data itself:
1. Per customer: compute median gap (days) between consecutive invoices
2. Dataset-wide: median of those per-customer medians
3. Clamped between 7 and 90 days

POC result: `median gap = 107.5 days → window capped at 90 days`.

#### Global Basket IDs

**Critical design point:** `basket_id` is a per-customer cumsum (1, 2, 3...). Customer A's basket 1 and Customer B's basket 1 are the same integer. Computing `nunique(basket_id)` at cluster level would undercount baskets, making `product_freq < pair_freq` which causes `confidence > 1.0`.

Fix: `global_basket_id = customer_id + "_" + basket_id` — unique across all customers.

#### Time-Decayed Support

Recent co-occurrences are weighted more heavily than old ones:

```
weight = exp(−λ × age_days)
```

With `DECAY_LAMBDA = 0.001`, the half-life is ≈ 693 days. Both raw and weighted support are computed.

#### Metrics

| Metric | Formula | Meaning |
|--------|---------|---------|
| `pair_freq` | count(baskets where A and B co-occur) | Raw co-occurrence count |
| `confidence` | pair_freq / product_a_freq | P(B \| A) — given customer bought A, probability they also buy B |
| `support` | pair_freq / total_cluster_baskets | P(A ∩ B) — how common the pair is overall |
| `weighted_support` | weighted_pair_freq / total_cluster_baskets | Support discounted for older baskets |
| `lift` | confidence / P(B) | Genuine affinity signal. Lift = 1 means B appears randomly, not associated with A |

#### Filtering

Rules are filtered by:
1. **Proportional frequency threshold:** `product_freq ≥ max(MIN_ABS_FREQ, MIN_FREQ_RATIO × total_baskets)` — adapts to cluster size
2. **Lift threshold:** `lift ≥ MIN_LIFT (default 1.2)` — removes rules where B is just universally popular

---

### 4.5 Step 5 — Ranking

**Script:** `ranking.py`
**Job Type:** SageMaker Processing Job
**Instance:** `ml.m5.large`

#### What It Does

For each customer, selects up to `TOP_K` product recommendations from the association rules mined for their cluster, scores and ranks them, then fills any remaining slots via category-aware fallback.

#### Score Formula

```
score = W_CONF    × confidence
      + W_SUPP    × weighted_support (or support if not available)
      + W_LIFT    × lift_normalised
      + W_RECENCY × recency_score

lift_normalised = clamp((lift − 1) / (MAX_LIFT_NORMALISE − 1), 0, 1)
recency_score   = 1 / (1 + mean_recency_days_for_customer)
```

Default weights: `W_CONF=0.45, W_SUPP=0.20, W_LIFT=0.20, W_RECENCY=0.15`

**Why normalise lift?** Raw lift can reach 31.0 in small clusters. Without normalisation, lift dominates the score and makes confidence and support irrelevant. Clamping to `[0, 1]` keeps all four components balanced.

#### L3 Prioritisation (PRD 5.4)

Within scoring ties (within `L3_TIEBREAK_MARGIN = 0.02`), products in the customer's most-purchased L3 category receive a small bonus:

```
l3_bonus = customer's L3 purchase proportion × L3_TIEBREAK_MARGIN
```

This ensures the engine prioritises sub-category relevance when two rules have similar strength.

#### Filters Applied Per Rule

For a rule to generate a recommendation, all of the following must pass:
- `product_b` not already purchased by customer
- `product_a` (trigger) was purchased by customer
- `product_b` is in-stock
- `support ≥ MIN_SUPPORT`
- `confidence ≥ MIN_CONFIDENCE`
- `lift ≥ MIN_LIFT`

#### Category-Aware Fallback

Customers with fewer than `TOP_K` recommendations from association rules get remaining slots filled via category-aware fallback:

1. Build candidate pool: segment products not yet purchased, in-stock, not already recommended
2. Score each candidate by **category affinity** — how closely the product's L2 category matches the customer's own purchase mix
3. Sort by affinity (desc) then segment popularity (desc) as tiebreaker

This ensures fallback recommendations are personalised to each customer's category interests rather than just returning the most popular products segment-wide.

The reason field explicitly records the affinity score:
```
"Category-affinity fallback: Plumbing affinity=0.72"
```

---

### 4.6 Step 6 — Feedback Calibration

**Script:** `feedback.py`
**Job Type:** SageMaker Processing Job
**Instance:** `ml.t3.xlarge`

#### What It Does

Reads Account Manager feedback from S3, applies score multipliers to each recommendation, removes low-scoring recommendations, re-ranks within each customer, and publishes the final output. Also generates a `feedback_summary.json` that the next pipeline run can read to auto-adjust thresholds.

#### Feedback Schema & Weight Resolution

| Rating | Sentiment | Weight | Effect |
|--------|-----------|--------|--------|
| High | any | 1.3 | Boosted |
| Medium | positive | 1.0 | Unchanged |
| Medium | negative | 0.4 | Suppressed |
| Medium | no signal | 1.0 | Unchanged (conservative default) |
| Low | any | 0.1 | Strongly suppressed |
| (none) | — | 1.0 | Unchanged |

**Medium sentiment resolution priority:**
1. Explicit `sentiment` column (`positive` / `negative`)
2. Infer from `reason_code` — known negative codes (e.g. `not_relevant`, `wrong_category`, `price_too_high`) → 0.4; known positive codes (e.g. `good_fit`, `customer_interested`) → 1.0
3. Default → 1.0

#### Score Cutoff

After weight adjustment, recommendations with `score < SCORE_CUTOFF (default 0.08)` are removed entirely. TOP_K is re-applied after re-ranking.

#### Feedback Summary

After each run, `feedback_summary.json` is written to `s3://ipre-prod-poc/feedback/`:

```json
{
  "generated_at": "2026-02-25T10:30:00",
  "overall": {
    "acceptance_rate": 0.72,
    "high_rate": 0.41,
    "medium_positive_rate": 0.31,
    "medium_negative_rate": 0.14,
    "low_rate": 0.14
  },
  "by_segment": { ... },
  "by_l2_category": { ... },
  "reason_code_distribution": { ... },
  "threshold_suggestions": {
    "MIN_CONFIDENCE": 0.05,
    "SCORE_CUTOFF": 0.08,
    "rationale": "Acceptance rate=0.72. Holding thresholds."
  }
}
```

The threshold suggestions implement a feedback learning loop — if acceptance rate drops below 50%, `MIN_CONFIDENCE` is automatically tightened on the next run.

#### Graceful No-Feedback Handling

If no feedback file exists in S3 (e.g. first run), the step logs a warning and publishes recommendations unchanged. The pipeline does not crash.

---

## 5. Pipeline Parameters — Complete Reference

All 32 parameters are exposed as SageMaker Pipeline Parameters and can be overridden per-run from Studio UI, AWS CLI, or EventBridge schedule without touching code.

### Group A — Data Inputs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `InputCustomers` | `s3://.../customer.csv` | S3 URI for customer master |
| `InputProducts` | `s3://.../product.csv` | S3 URI for product master |
| `InputInvoices` | `s3://.../invoice.csv` | S3 URI for invoice history |
| `ModelApprovalStatus` | `Approved` | Set to `PendingManualApproval` to gate deployment |

### Group B — Market Basket

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MinOrderCount` | `1` | Exclude customers with fewer invoices |
| `RecencyCutoffDays` | `730` | Ignore invoices older than N days |

### Group C — Clustering

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MaxK` | `8` | Maximum clusters per segment |
| `MinClusterCustomers` | `6` | Min customers to attempt clustering |
| `ElbowThreshold` | `10.0` | % inertia drop below which elbow is detected |
| `FeatureGroups` | `l2_qty,brand,functionality,rfm` | Feature groups to include |
| `RandomState` | `42` | KMeans random seed |
| `NInit` | `15` | KMeans n_init |

### Group D — Association Mining

| Parameter | Default | Description |
|-----------|---------|-------------|
| `WindowDays` | `0` | Basket window days (0 = auto-compute) |
| `MinLift` | `1.2` | Minimum lift to keep a rule |
| `MinAbsFreq` | `2` | Absolute minimum basket frequency floor |
| `MinFreqRatio` | `0.03` | Proportional minimum (3% of cluster baskets) |
| `DecayLambda` | `0.001` | Exponential decay rate (~693 day half-life) |

### Group E — Ranking & Scoring

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MinSupport` | `0.01` | Minimum support threshold |
| `MinConfidence` | `0.05` | Minimum confidence threshold |
| `TopK` | `5` | Max recommendations per customer |
| `WConf` | `0.45` | Confidence weight in score formula |
| `WSupp` | `0.20` | Support weight in score formula |
| `WLift` | `0.20` | Lift weight in score formula |
| `WRecency` | `0.15` | Recency weight in score formula |
| `MaxLiftNormalise` | `5.0` | Lift normalisation ceiling |
| `L3TiebreakMargin` | `0.02` | L3 affinity tiebreak bonus |

### Group F — Feedback Calibration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `WeightHigh` | `1.3` | Score multiplier for High rating |
| `WeightMedPos` | `1.0` | Multiplier for Medium + positive |
| `WeightMedNeg` | `0.4` | Multiplier for Medium + negative |
| `WeightLow` | `0.1` | Score multiplier for Low rating |
| `ScoreCutoff` | `0.08` | Minimum score after calibration |
| `FeedbackRecencyDays` | `365` | Only use feedback from last N days |

> **Note:** All parameters are `ParameterString` type (not `ParameterInteger`/`ParameterFloat`) because SageMaker's `ScriptProcessor(env=...)` only accepts string values. Scripts cast them at runtime via `int(os.environ.get(...))` and `float(os.environ.get(...))`.

---

## 6. Output Schema

### final/recommendations.csv

| Column | Type | Description |
|--------|------|-------------|
| `customer_id` | string | Customer identifier |
| `recommended_product` | string | Recommended product ID |
| `cluster_id` | string | Cluster the customer belongs to (e.g. `West_Plumbing_2`) |
| `segment` | string | Segment (region_end_use) |
| `l2_category` | string | L2 category of recommended product |
| `l3_category` | string | L3 sub-category of recommended product |
| `trigger_product` | string | Product that triggered this rule (or `fallback`) |
| `support` | float | Rule support score |
| `confidence` | float | Rule confidence P(B\|A) |
| `lift` | float | Rule lift — genuine affinity signal |
| `score` | float | Final composite score [0, 1] |
| `recommended_qty` | int | Suggested order quantity (customer's median order qty for trigger product) |
| `reason` | string | Human-readable explanation |
| `rank` | int | Rank within customer (1 = best) |

### feedback/feedback_summary.json

Written after each feedback calibration run. Contains overall and per-segment acceptance rates, reason code distribution, and suggested threshold adjustments for the next run.

---

## 7. Key Algorithms & Design Decisions

### 7.1 Why Proportions for Clustering Features

Raw quantity features make high-volume customers appear as outliers even when their category mix is identical to low-volume customers. By normalising each feature group to proportions (each row sums to 1.0), clustering captures *what* customers buy rather than *how much* — which is the right signal for segmentation.

### 7.2 Why the Elbow Method

The original implementation used `k = min(4, sqrt(n))` — an arbitrary heuristic. The elbow method is data-driven: it runs KMeans for all k from 2 to MAX_K and picks the point of diminishing returns. This produced segments with 1–8 clusters in the POC vs. a uniform cap of 4 previously.

### 7.3 Why Lift Matters

Without the lift metric, the engine would recommend bestsellers to everyone because bestsellers appear in many baskets alongside everything else — not because of genuine affinity. Lift normalises confidence by P(B), filtering rules where B is just universally popular.

Example: if P00085 appears in 80% of all baskets, confidence(A→P00085)=0.8 does not mean genuine affinity — lift(A→P00085) ≈ 1.0 indicates no real association.

### 7.4 Why Global Basket IDs

`basket_id` is a per-customer cumsum integer. Customer A's basket 1 and Customer B's basket 1 are the same integer. When computing `nunique(basket_id)` at cluster level, these collapse — undercounting total baskets and making `product_freq < pair_freq`, producing `confidence > 1.0`. The fix: `global_basket_id = customer_id + "_" + basket_id`.

### 7.5 Why All Parameters Are Strings

SageMaker `ScriptProcessor(env=...)` maps to OS environment variables which are always strings. Passing `ParameterInteger` objects causes a `ValidationException: Cannot assign property reference to argument of type String` at `CreatePipeline` time. All 30 numeric/float parameters are defined as `ParameterString` with string defaults.

### 7.6 Why Feedback Doesn't Crash Without a File

SageMaker validates all `ProcessingInput` S3 paths at job creation time — before any code runs. If the feedback file doesn't exist, the pipeline would crash before Step 1 runs. Feedback is instead read by `feedback.py` via `boto3` at runtime, where a missing file is handled with a graceful warning.

---

## 8. Bugs Fixed During Development

A complete record of every issue encountered and resolved during POC development.

| # | Step | Bug | Root Cause | Fix |
|---|------|-----|-----------|-----|
| 1 | Associations | `confidence > 1.0` assertion failure | `basket_id` is per-customer cumsum — different customers share the same integer, undercounting baskets at cluster level | Created `global_basket_id = customer_id + "_" + basket_id` |
| 2 | Market Basket | `KeyError: 'unit_price'` | `unit_price` column doesn't exist by that name in products.csv | Auto-detect price column from common aliases (`price`, `list_price`, `unit_cost`, `sale_price`) |
| 3 | Ranking | `NameError: prod_l2` | `prod_l2`/`prod_l3` dicts were only defined inside `category_aware_fallback()` but referenced in `main()` | Moved definition to `main()` before the recommendation loop |
| 4 | Ranking | `KeyError: 'segment'` | Both `market_basket.csv` and `customer_clusters.csv` have a `segment` column — merge produces `segment_x`/`segment_y` | Drop `segment` from clusters before merging since basket already has it |
| 5 | Pipeline | `TypeError: unsupported operand type(s) for \|: type and NoneType` | `pd.DataFrame \| None` type hint syntax requires Python 3.10+; SageMaker container runs Python 3.9 | Replace with `Optional[pd.DataFrame]` from `typing` |
| 6 | Pipeline | `TypeError: ProcessingStep got unexpected keyword argument 'environment'` | `ProcessingStep` does not accept `environment` kwarg | Move env vars to `ScriptProcessor(env={...})` |
| 7 | Pipeline | `ValidationException: Cannot assign property reference to argument of type String` | `ParameterInteger`/`ParameterFloat` objects can't be passed as env values to Processing Jobs | Convert all parameters to `ParameterString` with string defaults |
| 8 | Clustering | `customer_clusters.csv` not found | CSV written to `/opt/ml/output/data/` which goes into `output.tar.gz` — Processing containers can't reliably find it alongside `model.tar.gz` | Write CSV to `/opt/ml/model/` so it travels inside `model.tar.gz` |
| 9 | Ranking | Old fallback using `popular_product` trigger | `ranking.py` was not uploaded to S3 before pipeline re-run | Upload scripts to S3 before running |
| 10 | Ranking | `products` variable read twice, second read unused | Copy-paste error — `products = pd.read_csv(market_basket.csv)` on line 328 served no purpose | Removed redundant read |

---

## 9. Endpoint & Salesforce Integration

### SageMaker Endpoint

After the pipeline completes, `deploy_endpoint.py` deploys the clustering model to a SageMaker real-time endpoint:

- **Endpoint name:** `ipre-prod-poc-endpoint`
- **Instance:** `ml.m5.large`
- **Inference script:** `inference.py`

**How inference works:**
1. Request arrives with `customer_id`
2. `inference.py` reads `final/recommendations.csv` from S3 (cached at startup)
3. Filters rows for that customer
4. Returns JSON array of up to 5 recommendations

```json
{
  "customer_id": "C00052",
  "recommendations": [
    {
      "product_id": "P00136",
      "rank": 1,
      "score": 0.511,
      "confidence": 0.667,
      "lift": 8.67,
      "l2_category": "Plumbing",
      "reason": "P00153 → P00136 (support=0.077, confidence=0.667, lift=8.67)"
    }
  ]
}
```

### Salesforce Integration

The endpoint is exposed to Salesforce via a **Named Credential** pointing to the SageMaker endpoint URL. An Einstein Co-Pilot action is configured to call this API before Account Manager visits, surfacing recommendations directly in the CRM record.

---

## 10. How to Run

### Prerequisites

- AWS Account with SageMaker execution role
- S3 bucket `ipre-prod-poc` with raw data uploaded
- SageMaker Studio or CLI access

### Upload Scripts

```bash
aws s3 cp scripts/market_basket.py    s3://ipre-prod-poc/scripts/
aws s3 cp scripts/train_clustering.py s3://ipre-prod-poc/scripts/
aws s3 cp scripts/associations.py     s3://ipre-prod-poc/scripts/
aws s3 cp scripts/ranking.py          s3://ipre-prod-poc/scripts/
aws s3 cp scripts/feedback.py         s3://ipre-prod-poc/scripts/
aws s3 cp scripts/inference.py        s3://ipre-prod-poc/scripts/
```

### Register & Run Pipeline (Defaults)

```bash
python pipeline.py
```

### Run with Custom Parameters

```python
from sagemaker.workflow.pipeline import Pipeline

pipeline = Pipeline(name="ipre-prod-poc", ...)

execution = pipeline.start(
    parameters={
        "MinLift":        "1.0",   # Relax lift filter
        "MinFreqRatio":   "0.01",  # Relax frequency threshold
        "WindowDays":     "30",    # Override basket window
        "MinConfidence":  "0.03",  # Relax confidence threshold
        "TopK":           "10",    # More recommendations
    }
)
```

### Deploy Endpoint

```bash
python deploy_endpoint.py
```

### Monitoring Pipeline

After running:
- SageMaker Studio → Pipelines → `ipre-prod-poc` → Executions
- Each step shows logs, duration, and input/output URIs
- Model versions visible in Model Registry → `ipre-clustering-models`

---

## 11. Monitoring & Observability

### CloudWatch Logs

Every Processing Job and Training Job writes logs to CloudWatch automatically:
- **Log Group:** `/aws/sagemaker/ProcessingJobs`
- **Log Group:** `/aws/sagemaker/TrainingJobs`

### Key Metrics to Monitor

| Metric | Where | Healthy Range |
|--------|-------|--------------|
| Silhouette score per segment | Training Job logs | > 0.2 |
| Association rules generated | Associations logs | > 100 |
| Customers with <5 recs | Ranking logs | < 5% |
| Acceptance rate | feedback_summary.json | > 50% |
| Coverage (customers with any rec) | Ranking logs | 100% |

### Feedback Summary Dashboard

After each feedback cycle, `s3://ipre-prod-poc/feedback/feedback_summary.json` contains per-segment and per-category acceptance rates. This is the primary signal for tuning parameters on the next run.

---

## 12. Validation Results (POC)

### Pipeline Run: February 2026

**Parameters used:** All defaults as documented in Section 5.

| Step | Status | Key Output |
|------|--------|-----------|
| Market Basket | ✅ | 1,961 invoices after recency cutoff; 477 customers |
| Clustering | ✅ | 230 clusters across 54 segments; up to 8 clusters/segment |
| Associations | ✅ | Basket window auto-computed: 90 days; lift range 1.33–31.0 |
| Ranking | ✅ | 2,342 recommendations; 477 customers covered |
| Feedback | ✅ | No feedback on first run; output published unchanged |

### Recommendation Quality

| Metric | Value |
|--------|-------|
| Customers covered | 477 / 477 (100%) |
| Via association rules | 225 customers (47%) |
| Via category-aware fallback | 407 customers (85%) — includes customers who received both |
| Customers with exactly 5 recs | 460 (96%) |
| Customers with <5 recs | 17 (4%) — have bought nearly all products in segment |
| Score range | 0.10 – 1.10 |
| Distinct score values | 830 |
| Top trigger product | P00088, P00142, P00139 |

---

## 13. Known Limitations & Next Steps

### Current Limitations

| Item | Description |
|------|-------------|
| Small dataset | 3,000 invoices is a POC size. Association rules are sparse — only 225/477 customers have genuine association-based recs. More data will produce denser rule sets. |
| Score cap | Composite score can slightly exceed 1.0 when L3 tiebreak bonus is applied. Not functional issue but should be capped: `final_score = min(raw_score + l3_bonus, 1.0)` |
| `weighted_support` column | Computed in `associations.py` but not flowing through to final output — minor schema issue |
| CloudWatch alarms | No automated alerts configured for step failures or quality degradation |
| Einstein Co-Pilot action | Named Credential ready but the Salesforce action is not yet configured |
| Sales Leader dashboard | No reporting/visibility layer beyond raw CSV |

### Recommended Next Steps

1. **Tighten association thresholds as data grows** — with 50K+ invoices, set `MinLift=1.5`, `MinFreqRatio=0.05`
2. **Configure CloudWatch alarms** — alert on acceptance rate < 40%, coverage < 95%
3. **Complete Salesforce Einstein Co-Pilot action** configuration
4. **Add score cap fix** — `final_score = min(raw_score + l3_bonus, 1.0)`
5. **Schedule pipeline** — set up EventBridge rule to run weekly
6. **A/B test weight parameters** — run parallel executions with different W_CONF/W_LIFT ratios, compare acceptance rates in feedback_summary.json

---
